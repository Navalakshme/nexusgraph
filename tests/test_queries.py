"""Test all 6 canonical Cypher queries directly against FalkorDB Cloud."""

import unittest
from src.db.falkor_client import get_db_manager
from src.db.seed_company_brain import seed_tenant_graph


class TestCanonicalCypherQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager = get_db_manager()
        cls.tenant_id = "test_sandbox"
        cls.conn = cls.manager.check_connection()
        if cls.conn.get("connected"):
            seed_tenant_graph(manager=cls.manager, tenant_id=cls.tenant_id, reset=True)

    @classmethod
    def tearDownClass(cls):
        # Clean up sandbox graph so evaluation graphs remain pristine
        if hasattr(cls, "conn") and cls.conn.get("connected"):
            cls.manager.run_cypher(cls.tenant_id, "MATCH (n) DETACH DELETE n", read_only=False)

    def test_query_1_multihop_root_cause(self):
        """Test Query 1: 5-hop incident root-cause lineage."""
        q = """
        MATCH (inc:Incident {id: $incident_id})-[:AFFECTS]->(svc:Service)
        OPTIONAL MATCH (svc)-[:DEPENDS_ON*0..2]->(dep:Service)<-[:MODIFIES]-(c:Commit)-[:IN_PR]->(pr:PullRequest)
        OPTIONAL MATCH (eng:Engineer)-[:AUTHORED_COMMIT]->(c)
        OPTIONAL MATCH (team:Team)-[:OWNS]->(dep)
        OPTIONAL MATCH (c)-[v:VIOLATES]->(d:Decision)
        RETURN inc.id AS incident_id, inc.title AS incident_title, inc.severity AS severity,
               svc.name AS affected_service, dep.name AS root_service,
               c.sha AS commit_sha, c.message AS commit_msg, c.timestamp AS commit_timestamp,
               pr.id AS pr_id, pr.title AS pr_title,
               eng.name AS author, eng.email AS author_email, eng.role AS author_role,
               team.name AS owning_team, team.channel AS team_channel,
               d.id AS violated_decision_id, d.title AS violated_decision_title,
               v.reason AS violation_reason;
        """
        res = self.manager.run_cypher(self.tenant_id, q, {"incident_id": "INC-2026-1015"}, read_only=True)
        self.assertTrue(res.success, f"Query 1 failed: {res.error}")
        self.assertGreater(len(res.data), 0)
        self.assertEqual(res.data[0].get("root_service"), "payment-ledger")
        self.assertEqual(res.data[0].get("commit_sha"), "a8f921c")

    def test_query_2_pagerank(self):
        """Test Query 2: FalkorDB native PageRank centrality."""
        q = """
        CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score
        RETURN node.id AS id, node.name AS service, node.tier AS tier, node.status AS status, score
        ORDER BY score DESC;
        """
        res = self.manager.run_cypher(self.tenant_id, q, read_only=True)
        self.assertTrue(res.success, f"Query 2 failed: {res.error}")
        self.assertGreater(len(res.data), 0)

    def test_query_3_blast_radius(self):
        """Test Query 3: Multi-hop downstream blast radius."""
        q = """
        MATCH path = (upstream:Service)-[r:DEPENDS_ON*1..3]->(target:Service {name: $service_name})
        RETURN upstream.name AS impacted_service, upstream.tier AS tier,
               length(path) AS hops,
               [n IN nodes(path) | n.name] AS path_services,
               [rel IN relationships(path) | properties(rel)] AS path_rels;
        """
        res = self.manager.run_cypher(self.tenant_id, q, {"service_name": "payment-ledger"}, read_only=True)
        self.assertTrue(res.success, f"Query 3 failed: {res.error}")
        self.assertGreater(len(res.data), 0)

    def test_query_4_decision_lineage(self):
        """Test Query 4: Architectural decision lineage & Slack warnings."""
        q = """
        MATCH (d:Decision)-[:GOVERNS]->(s:Service {name: $service_name})
        OPTIONAL MATCH (d)-[:SUPERSEDES]->(old_d:Decision)
        OPTIONAL MATCH (st:SlackThread)-[:REFERENCES]->(d)
        OPTIONAL MATCH (exp:Engineer)-[r:EXPERT_IN]->(s)
        RETURN d.id AS decision_id, d.title AS decision_title, d.status AS status,
               d.date AS decision_date, d.rationale AS rationale, d.author AS author,
               old_d.id AS superseded_decision_id, old_d.title AS superseded_title,
               st.id AS slack_id, st.channel AS slack_channel, st.quote AS slack_quote,
               exp.name AS expert_name, exp.role AS expert_role, r.confidence AS expert_confidence;
        """
        res = self.manager.run_cypher(self.tenant_id, q, {"service_name": "payment-ledger"}, read_only=True)
        self.assertTrue(res.success, f"Query 4 failed: {res.error}")
        self.assertGreater(len(res.data), 0)
        adrs = [r.get("decision_id") for r in res.data]
        self.assertIn("ADR-029", adrs)

    def test_query_5_agent_handoffs(self):
        """Test Query 5: Multi-agent graph handoff edge creation."""
        q = """
        MERGE (sess:Session {id: $session_id})
        ON CREATE SET sess.started_at = $timestamp
        SET sess.last_active_at = $timestamp

        CREATE (from_run:AgentRun {
            id: $from_run_id,
            agent_name: $from_agent,
            session_id: $session_id,
            findings: $findings,
            cypher_used: $cypher_used,
            timestamp: $timestamp
        })
        CREATE (to_run:AgentRun {
            id: $to_run_id,
            agent_name: $to_agent,
            session_id: $session_id,
            status: "pending",
            timestamp: $timestamp
        })

        MERGE (from_run)-[:PART_OF_SESSION]->(sess)
        MERGE (to_run)-[:PART_OF_SESSION]->(sess)
        MERGE (from_run)-[:HANDED_OFF_TO {timestamp: $timestamp, reason: "Autonomous investigation handoff"}]->(to_run)
        RETURN sess.id AS session_id, from_run.id AS from_id, to_run.id AS to_id;
        """
        params = {
            "session_id": "sess_test_unit",
            "timestamp": "2026-10-18T00:00:00Z",
            "from_run_id": "run_test_from",
            "from_agent": "TestTriageAgent",
            "findings": "Test findings",
            "cypher_used": "MATCH (n) RETURN n",
            "to_run_id": "run_test_to",
            "to_agent": "TestActionAgent",
        }
        res = self.manager.run_cypher(self.tenant_id, q, params, read_only=False)
        self.assertTrue(res.success, f"Query 5 failed: {res.error}")

    def test_query_6_action_and_memory(self):
        """Test Query 6: Graph action mutation and memory creation."""
        q = """
        MATCH (inc:Incident {id: $incident_id})
        MATCH (svc:Service {name: $service_name})
        MERGE (sess:Session {id: $session_id})

        SET inc.status = "Mitigated",
            inc.mitigated_at = $timestamp,
            inc.resolution_summary = $action_taken

        CREATE (act:RemediationAction {
            id: $action_id,
            description: $action_taken,
            timestamp: $timestamp,
            executor: "AutonomousEngineeringAgent"
        })
        MERGE (inc)-[:REMEDIATED_BY]->(act)
        MERGE (act)-[:APPLIED_TO]->(svc)

        CREATE (mem:EpisodicMemory {
            id: $memory_id,
            session_id: $session_id,
            summary: $action_summary,
            confidence: 0.99,
            timestamp: $timestamp,
            key_learnings: $learned_fact
        })
        MERGE (mem)-[:RESOLVED_INCIDENT]->(inc)
        MERGE (mem)-[:ABOUT_SERVICE]->(svc)
        MERGE (mem)-[:RECORDED_IN_SESSION]->(sess)

        MERGE (fact:SemanticFact {id: $fact_id})
        SET fact.subject = $service_name,
            fact.predicate = "mitigation_rule",
            fact.object = $learned_fact,
            fact.source = "IncidentResolution:" + $incident_id,
            fact.verified = true,
            fact.updated_at = $timestamp
        MERGE (fact)-[:ABOUT_SERVICE]->(svc)

        RETURN inc.id AS incident_id, inc.status AS incident_status,
               act.id AS action_id, mem.id AS memory_id, fact.id AS fact_id;
        """
        params = {
            "incident_id": "INC-2026-1015",
            "service_name": "payment-ledger",
            "session_id": "sess_test_unit",
            "timestamp": "2026-10-18T00:00:00Z",
            "action_id": "ACT-UNIT-TEST",
            "action_taken": "Applied test circuit breaker fix",
            "memory_id": "MEM-UNIT-TEST",
            "action_summary": "Reverted commit and fixed thread pool",
            "learned_fact": "Retry pool must not exceed 10 threads",
            "fact_id": "FACT-UNIT-TEST",
        }
        res = self.manager.run_cypher(self.tenant_id, q, params, read_only=False)
        self.assertTrue(res.success, f"Query 6 failed: {res.error}")


if __name__ == "__main__":
    unittest.main()
