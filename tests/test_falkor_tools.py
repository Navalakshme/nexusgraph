"""Unit tests for FalkorDB graph tools and MCP server."""

import unittest
from unittest.mock import MagicMock
from src.db.falkor_client import FalkorGraphManager, CypherQueryResult
from src.mcp.falkor_tools import (
    compute_blast_radius_and_criticality,
    trace_incident_root_cause_multihop,
    trace_company_decision_lineage,
    recall_agent_memories,
    record_agent_handoff,
    execute_graph_action_and_persist_memory,
)
from src.mcp.server import mcp


class TestFalkorTools(unittest.TestCase):
    def setUp(self):
        FalkorGraphManager.reset_instance()
        self.mock_mgr = MagicMock(spec=FalkorGraphManager)
        self.mock_mgr._sanitize_tenant_id.return_value = "acme_prod"

    def test_compute_blast_radius_and_criticality(self):
        def mock_run_cypher(tenant_id, query, params=None, read_only=False):
            if "algo.pageRank" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[
                        {"service": "auth-token-service", "tier": 1, "score": 2.84, "status": "active"},
                        {"service": "payment-ledger", "tier": 1, "score": 2.45, "status": "active"},
                        {"service": "redis-session-cache", "tier": 1, "score": 1.62, "status": "active"},
                    ],
                    row_count=3,
                    latency_ms=1.5,
                )
            if "upstream:Service" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[
                        {
                            "impacted_service": "api-gateway",
                            "tier": 1,
                            "hops": 2,
                            "path_services": ["api-gateway", "checkout-orchestrator", "payment-ledger"],
                            "path_rels": [{"criticality": "high"}, {"criticality": "critical"}],
                        }
                    ],
                    row_count=1,
                    latency_ms=2.1,
                )
            return CypherQueryResult(success=True, tenant_id=tenant_id, query=query, data=[])

        self.mock_mgr.run_cypher.side_effect = mock_run_cypher

        res = compute_blast_radius_and_criticality(
            manager=self.mock_mgr,
            tenant_id="acme_prod",
            service_name="payment-ledger",
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["service_name"], "payment-ledger")
        self.assertEqual(len(res["pagerank_table"]), 3)
        self.assertEqual(res["pagerank_table"][0]["service"], "auth-token-service")
        self.assertEqual(len(res["impacted_services"]), 1)
        self.assertEqual(res["impacted_services"][0]["impacted_service"], "api-gateway")
        self.assertGreater(len(res["graph_paths"]), 0)
        self.assertEqual(res["graph_paths"][0]["source"], "api-gateway")
        self.assertEqual(res["graph_paths"][0]["target"], "checkout-orchestrator")

    def test_trace_incident_root_cause_multihop(self):
        def mock_run_cypher(tenant_id, query, params=None, read_only=False):
            if "inc:Incident" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[
                        {
                            "incident_id": "INC-2026-1015",
                            "incident_title": "Cascading 504 Timeouts",
                            "severity": "SEV-1",
                            "affected_service": "checkout-orchestrator",
                            "root_service": "payment-ledger",
                            "commit_sha": "a8f921c",
                            "commit_msg": "feat(ledger): bump batch retry pool to 50 threads",
                            "author": "Elena Rostova",
                            "author_role": "Senior Backend Engineer",
                            "owning_team": "Payments Core",
                            "team_channel": "#payments-eng",
                            "violated_decision_id": "ADR-029",
                            "violation_reason": "Re-enabled synchronous thread pool retries",
                        }
                    ],
                    row_count=1,
                    latency_ms=3.2,
                )
            if "SlackThread" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[
                        {
                            "slack_id": "SLACK-991",
                            "channel": "#payments-eng",
                            "quote": "Priya warned that raising retry threads...",
                            "warned_by": "Priya Nair",
                        }
                    ],
                    row_count=1,
                    latency_ms=1.1,
                )
            return CypherQueryResult(success=True, tenant_id=tenant_id, query=query, data=[])

        self.mock_mgr.run_cypher.side_effect = mock_run_cypher

        res = trace_incident_root_cause_multihop(
            manager=self.mock_mgr,
            tenant_id="acme_prod",
            incident_id="INC-2026-1015",
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["culprit_commit"], "a8f921c")
        self.assertEqual(res["author"], "Elena Rostova")
        self.assertEqual(res["owning_team"], "Payments Core")
        self.assertEqual(len(res["slack_warnings"]), 1)
        self.assertGreater(len(res["graph_paths"]), 0)

        # Check for VIOLATES edge in graph_paths
        violates_paths = [p for p in res["graph_paths"] if p.get("relationship") == "VIOLATES"]
        self.assertEqual(len(violates_paths), 1)
        self.assertEqual(violates_paths[0]["target"], "ADR-029")

    def test_trace_company_decision_lineage(self):
        def mock_run_cypher(tenant_id, query, params=None, read_only=False):
            return CypherQueryResult(
                success=True,
                tenant_id=tenant_id,
                query=query,
                data=[
                    {
                        "decision_id": "ADR-029",
                        "decision_title": "Enforce Circuit Breaker & Idempotency Keys",
                        "status": "Active",
                        "rationale": "Prevent cascading retry storms",
                        "superseded_decision_id": "ADR-014",
                        "superseded_title": "Use Synchronous gRPC Retries",
                        "expert_name": "Priya Nair",
                        "expert_role": "Staff Engineer",
                        "expert_confidence": 0.98,
                        "expert_domain": "Distributed consensus",
                        "slack_id": "SLACK-991",
                        "slack_channel": "#payments-eng",
                        "slack_quote": "Priya warned...",
                    }
                ],
                row_count=1,
                latency_ms=1.8,
            )

        self.mock_mgr.run_cypher.side_effect = mock_run_cypher

        res = trace_company_decision_lineage(
            manager=self.mock_mgr,
            tenant_id="acme_prod",
            service_name="payment-ledger",
        )

        self.assertTrue(res["success"])
        self.assertEqual(len(res["active_decisions"]), 1)
        self.assertEqual(res["active_decisions"][0]["id"], "ADR-029")
        self.assertEqual(res["active_decisions"][0]["supersedes"]["id"], "ADR-014")
        self.assertEqual(len(res["experts"]), 1)
        self.assertEqual(res["experts"][0]["name"], "Priya Nair")

        # Check SUPERSEDES edge in graph paths
        supersedes_paths = [p for p in res["graph_paths"] if p.get("relationship") == "SUPERSEDES"]
        self.assertEqual(len(supersedes_paths), 1)
        self.assertEqual(supersedes_paths[0]["source"], "ADR-029")
        self.assertEqual(supersedes_paths[0]["target"], "ADR-014")

    def test_recall_agent_memories(self):
        def mock_run_cypher(tenant_id, query, params=None, read_only=False):
            return CypherQueryResult(
                success=True,
                tenant_id=tenant_id,
                query=query,
                data=[
                    {
                        "episodic_memories": [
                            {
                                "id": "MEM-SESSION-001",
                                "session_id": "sess_01",
                                "summary": "Architect review on ADR-029",
                                "confidence": 0.98,
                            }
                        ],
                        "procedural_runbooks": [
                            {
                                "id": "RUNBOOK-07",
                                "title": "Rollback Retry Pool & Enable Circuit Breaker Flag",
                                "steps": ["1. Revert commit a8f921c"],
                            }
                        ],
                        "semantic_facts": [
                            {
                                "id": "FACT-042",
                                "rule": "Payment ledger requires circuit breaker",
                            }
                        ],
                    }
                ],
                row_count=1,
                latency_ms=2.0,
            )

        self.mock_mgr.run_cypher.side_effect = mock_run_cypher

        res = recall_agent_memories(
            manager=self.mock_mgr,
            tenant_id="acme_prod",
            service_name="payment-ledger",
        )

        self.assertTrue(res["success"])
        self.assertEqual(len(res["episodic_memories"]), 1)
        self.assertEqual(res["episodic_memories"][0]["id"], "MEM-SESSION-001")
        self.assertEqual(len(res["procedural_runbooks"]), 1)
        self.assertEqual(res["procedural_runbooks"][0]["id"], "RUNBOOK-07")
        self.assertEqual(len(res["semantic_facts"]), 1)
        self.assertEqual(res["semantic_facts"][0]["id"], "FACT-042")
        self.assertGreater(len(res["graph_paths"]), 0)

    def test_record_agent_handoff(self):
        self.mock_mgr.run_cypher.return_value = CypherQueryResult(
            success=True,
            tenant_id="acme_prod",
            query="HANDOFF",
            data=[{"session_id": "sess_100", "from_id": "run_triage", "to_id": "run_remediation"}],
            row_count=1,
            latency_ms=1.1,
        )

        res = record_agent_handoff(
            manager=self.mock_mgr,
            tenant_id="acme_prod",
            session_id="sess_100",
            from_agent="TriageAgent",
            to_agent="RemediationAgent",
            findings_summary="Identified commit a8f921c",
            cypher_used="MATCH (c:Commit) RETURN c",
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["from_agent"], "TriageAgent")
        self.assertEqual(res["to_agent"], "RemediationAgent")
        handoff_edges = [p for p in res["graph_paths"] if p.get("relationship") == "HANDED_OFF_TO"]
        self.assertEqual(len(handoff_edges), 1)

    def test_execute_graph_action_and_persist_memory(self):
        self.mock_mgr.run_cypher.return_value = CypherQueryResult(
            success=True,
            tenant_id="acme_prod",
            query="ACTION",
            data=[{"incident_id": "INC-2026-1015", "incident_status": "Mitigated"}],
            row_count=1,
            latency_ms=2.3,
        )

        res = execute_graph_action_and_persist_memory(
            manager=self.mock_mgr,
            tenant_id="acme_prod",
            session_id="sess_100",
            incident_id="INC-2026-1015",
            service_name="payment-ledger",
            action_taken="Reverted a8f921c and enabled circuit breaker",
            learned_fact="Never bump retry pool without circuit breaker active",
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["incident_status"], "Mitigated")
        remediated_paths = [p for p in res["graph_paths"] if p.get("relationship") == "REMEDIATED_BY"]
        self.assertEqual(len(remediated_paths), 1)
        memory_paths = [p for p in res["graph_paths"] if p.get("relationship") == "RESOLVED_INCIDENT"]
        self.assertEqual(len(memory_paths), 1)

    def test_fastmcp_tools_registered(self):
        # Verify all tools registered on FastMCP server instance
        tool_names = [tool.name for tool in mcp._tool_manager.list_tools()]
        expected_tools = [
            "blast_radius_and_criticality",
            "trace_incident_root_cause",
            "trace_decision_lineage",
            "recall_memories",
            "record_handoff",
            "execute_graph_action",
        ]
        for expected in expected_tools:
            self.assertIn(expected, tool_names, f"Expected {expected} in FastMCP tools")


if __name__ == "__main__":
    unittest.main()
