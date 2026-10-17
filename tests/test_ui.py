"""Unit tests for UI and graph visualization module."""

import unittest
from src.ui.graph_viz import (
    render_pyvis_network,
    build_pyvis_from_traversed_paths,
    build_pyvis_from_falkor_graph,
    _infer_node_type,
)


class TestGraphViz(unittest.TestCase):
    def test_infer_node_type(self):
        self.assertEqual(_infer_node_type("INC-2026-1015"), "Incident")
        self.assertEqual(_infer_node_type("ADR-029"), "Decision")
        self.assertEqual(_infer_node_type("PR-482"), "PullRequest")
        self.assertEqual(_infer_node_type("JIRA-1904"), "Ticket")
        self.assertEqual(_infer_node_type("MEM-SESSION-001"), "EpisodicMemory")
        self.assertEqual(_infer_node_type("FACT-042"), "SemanticFact")
        self.assertEqual(_infer_node_type("RUNBOOK-07"), "ProceduralRunbook")
        self.assertEqual(_infer_node_type("RUN_triage_123"), "AgentRun")
        self.assertEqual(_infer_node_type("ACT-4819"), "RemediationAction")
        self.assertEqual(_infer_node_type("SLACK-991"), "SlackThread")
        self.assertEqual(_infer_node_type("a8f921c"), "Commit")
        self.assertEqual(_infer_node_type("payment-ledger"), "Service")

    def test_render_pyvis_network_html(self):
        nodes = [
            {"id": "payment-ledger", "type": "Service", "properties": {"tier": 1}},
            {"id": "INC-2026-1015", "type": "Incident", "properties": {"severity": "SEV-1"}},
        ]
        edges = [
            {"source": "INC-2026-1015", "target": "payment-ledger", "label": "AFFECTS"},
        ]
        html = render_pyvis_network(nodes=nodes, edges=edges, highlight_edges={("INC-2026-1015", "AFFECTS", "payment-ledger")})
        self.assertIn("<html", html.lower())
        self.assertIn("payment-ledger", html)
        self.assertIn("INC-2026-1015", html)

    def test_build_pyvis_from_traversed_paths(self):
        paths = [
            {
                "source": "api-gateway",
                "source_label": "Service",
                "relationship": "DEPENDS_ON",
                "target": "checkout-orchestrator",
                "target_label": "Service",
                "properties": {"criticality": "high"},
            },
            {
                "source": "checkout-orchestrator",
                "source_label": "Service",
                "relationship": "DEPENDS_ON",
                "target": "payment-ledger",
                "target_label": "Service",
                "properties": {"criticality": "critical"},
            },
        ]
        html = build_pyvis_from_traversed_paths(paths)
        self.assertIn("<html", html.lower())
        self.assertIn("checkout-orchestrator", html)
        self.assertIn("payment-ledger", html)

    def test_build_pyvis_empty_states(self):
        # Empty traversed paths returns clean empty state message
        empty_paths_html = build_pyvis_from_traversed_paths([])
        self.assertIn("No Graph Paths Traversed Yet", empty_paths_html)

        # Disconnected or empty FalkorDB returns clean empty state message
        from unittest.mock import MagicMock
        mock_mgr = MagicMock()
        mock_mgr.run_cypher.return_value = MagicMock(success=True, data=[])
        empty_graph_html = build_pyvis_from_falkor_graph(manager=mock_mgr, tenant_id="test_tenant")
        self.assertIn("No Active Graph Data in FalkorDB", empty_graph_html)
        self.assertNotIn("checkout-orchestrator", empty_graph_html)


if __name__ == "__main__":
    unittest.main()

