"""Unit tests for NexusMultiAgentOrchestrator."""

import unittest
from unittest.mock import MagicMock, patch
from src.db.falkor_client import FalkorGraphManager, CypherQueryResult
from src.agents.orchestrator import NexusMultiAgentOrchestrator


class TestMultiAgentOrchestrator(unittest.TestCase):
    def setUp(self):
        FalkorGraphManager.reset_instance()
        self.mock_mgr = MagicMock(spec=FalkorGraphManager)
        self.mock_mgr._sanitize_tenant_id.return_value = "acme_prod"
        self.patcher = patch("src.agents.orchestrator.genai.Client")
        self.mock_client_cls = self.patcher.start()
        self.mock_client = MagicMock()
        self.mock_client.models.generate_content.return_value.text = "Mocked Gemini synthesis: [INC-2026-1015], [Commit a8f921c], [payment-ledger], [ADR-029], [SLACK-991], [RUNBOOK-07]."
        self.mock_client_cls.return_value = self.mock_client

    def tearDown(self):
        self.patcher.stop()

    def test_orchestrator_initialization(self):
        orch = NexusMultiAgentOrchestrator(manager=self.mock_mgr)
        self.assertIsNotNone(orch.manager)
        self.assertEqual(orch.gemini_model, "gemini-3.8-flash")

    def test_run_investigation_three_agents_sequence(self):
        def mock_run_cypher(tenant_id, query, params=None, read_only=False):
            # 1. Incident Root Cause
            if "inc:Incident" in query and "AFFECTS" in query:
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
                    latency_ms=2.0,
                )
            # 2. Slack Thread warning
            if "SlackThread" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[
                        {
                            "slack_id": "SLACK-991",
                            "channel": "#payments-eng",
                            "quote": "Priya warned that raising retry threads without the circuit breaker flag will exhaust auth-token-service connections.",
                            "warned_by": "Priya Nair",
                        }
                    ],
                    row_count=1,
                    latency_ms=1.5,
                )
            # 3. PageRank
            if "algo.pageRank" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[
                        {"service": "auth-token-service", "tier": 1, "score": 2.84, "status": "active"},
                        {"service": "payment-ledger", "tier": 1, "score": 2.45, "status": "active"},
                    ],
                    row_count=2,
                    latency_ms=1.8,
                )
            # 4. Blast Radius
            if "upstream:Service" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[
                        {
                            "impacted_service": "checkout-orchestrator",
                            "tier": 1,
                            "hops": 1,
                            "path_services": ["checkout-orchestrator", "payment-ledger"],
                            "path_rels": [{"criticality": "critical"}],
                        }
                    ],
                    row_count=1,
                    latency_ms=1.9,
                )
            # 5. Decision Lineage
            if "d:Decision" in query and "GOVERNS" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[
                        {
                            "decision_id": "ADR-029",
                            "decision_title": "Enforce Circuit Breaker & Idempotency Keys on Ledger Writes",
                            "status": "Active",
                            "rationale": "Prevent cascading retry storms during token cache spikes",
                            "superseded_decision_id": "ADR-014",
                            "superseded_title": "Use Synchronous gRPC Retries on Payment Ledger",
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
                    latency_ms=2.1,
                )
            # 6. Memory Recall
            if "EpisodicMemory" in query and "ProceduralRunbook" in query:
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
                                    "summary": "Architect review on ADR-029: Priya and Marcus established circuit breaker mandatory.",
                                    "confidence": 0.98,
                                }
                            ],
                            "procedural_runbooks": [
                                {
                                    "id": "RUNBOOK-07",
                                    "title": "Rollback Retry Pool & Enable Circuit Breaker Flag",
                                    "steps": ["1. Revert commit a8f921c"],
                                    "verified": True,
                                }
                            ],
                            "semantic_facts": [
                                {
                                    "id": "FACT-042",
                                    "rule": "Payment ledger write retries MUST have circuit breaker protection",
                                }
                            ],
                        }
                    ],
                    row_count=1,
                    latency_ms=2.0,
                )
            # 7. Agent Handoff / Graph Action
            return CypherQueryResult(
                success=True,
                tenant_id=tenant_id,
                query=query,
                data=[{"session_id": "sess_test", "action_id": "ACT-01", "memory_id": "MEM-01", "fact_id": "FACT-01"}],
                row_count=1,
                latency_ms=1.5,
            )

        self.mock_mgr.run_cypher.side_effect = mock_run_cypher

        orchestrator = NexusMultiAgentOrchestrator(manager=self.mock_mgr)
        result = orchestrator.run_investigation(
            tenant_id="acme_prod",
            session_id="sess_test_100",
            incident_id="INC-2026-1015",
            auto_mitigate=True,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["session_id"], "sess_test_100")
        self.assertEqual(result["tenant_id"], "acme_prod")
        self.assertEqual(result["incident_id"], "INC-2026-1015")

        # Verify 3 steps executed
        steps = result["agent_steps"]
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0]["agent_name"], "TriageAgent")
        self.assertEqual(steps[1]["agent_name"], "LineageAgent")
        self.assertEqual(steps[2]["agent_name"], "ActionAgent")

        # Verify traversed paths
        self.assertGreater(len(result["traversed_paths"]), 0)

        # Verify final synthesis contains required citations
        synthesis = result["final_synthesis"]
        self.assertIn("[INC-2026-1015]", synthesis)
        self.assertIn("[Commit a8f921c]", synthesis)
        self.assertIn("[ADR-029]", synthesis)
        self.assertIn("[SLACK-991]", synthesis)
        self.assertIn("[RUNBOOK-07]", synthesis)

        # Verify memory diff
        memory_diff = result["memory_diff"]
        self.assertIsNotNone(memory_diff["remediation_action"]["id"])
        self.assertEqual(memory_diff["remediation_action"]["status"], "Mitigated")
        self.assertEqual(len(memory_diff["agent_handoffs"]), 2)

        # Verify summary
        summary = result["summary"]
        self.assertEqual(summary["root_service"], "payment-ledger")
        self.assertEqual(summary["culprit_commit"], "a8f921c")
        self.assertEqual(summary["violated_decision"], "ADR-029")
        self.assertEqual(summary["applied_runbook"], "RUNBOOK-07")
        self.assertEqual(summary["status"], "Mitigated")

    def test_run_investigation_no_auto_mitigate(self):
        def mock_run_cypher(tenant_id, query, params=None, read_only=False):
            return CypherQueryResult(
                success=True,
                tenant_id=tenant_id,
                query=query,
                data=[],
                row_count=0,
                latency_ms=1.0,
            )

        self.mock_mgr.run_cypher.side_effect = mock_run_cypher

        orchestrator = NexusMultiAgentOrchestrator(manager=self.mock_mgr)
        result = orchestrator.run_investigation(
            tenant_id="acme_prod",
            session_id="sess_manual",
            incident_id="INC-2026-1015",
            auto_mitigate=False,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["status"], "Investigated")
        self.assertEqual(result["memory_diff"]["remediation_action"]["status"], "Pending")


if __name__ == "__main__":
    unittest.main()
