"""Unit tests for seed_company_brain module."""

import unittest
from unittest.mock import MagicMock, patch
from src.db.falkor_client import FalkorGraphManager, CypherQueryResult
from src.db.seed_company_brain import seed_tenant_graph, create_schema_indexes


class TestSeedCompanyBrain(unittest.TestCase):
    def setUp(self):
        FalkorGraphManager.reset_instance()

    def tearDown(self):
        FalkorGraphManager.reset_instance()

    def test_seed_tenant_graph_execution(self):
        mock_manager = MagicMock(spec=FalkorGraphManager)
        mock_manager._sanitize_tenant_id.return_value = "acme_prod"

        # Mock run_cypher returning CypherQueryResult
        def mock_run_cypher(tenant_id, query, params=None, read_only=False):
            if "total_nodes" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[{"total_nodes": 24, "total_edges": 38}],
                    row_count=1,
                    latency_ms=1.5,
                )
            if "labels(n)" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[
                        {"labels": ["Service"], "count": 7},
                        {"labels": ["Engineer"], "count": 4},
                        {"labels": ["Team"], "count": 4},
                        {"labels": ["Decision"], "count": 2},
                        {"labels": ["Commit"], "count": 1},
                        {"labels": ["PullRequest"], "count": 1},
                        {"labels": ["Ticket"], "count": 1},
                        {"labels": ["SlackThread"], "count": 1},
                        {"labels": ["Incident"], "count": 1},
                        {"labels": ["ProceduralRunbook"], "count": 1},
                        {"labels": ["EpisodicMemory"], "count": 1},
                        {"labels": ["SemanticFact"], "count": 1},
                    ],
                    row_count=12,
                    latency_ms=1.2,
                )
            return CypherQueryResult(
                success=True,
                tenant_id=tenant_id,
                query=query,
                data=[],
                row_count=0,
                latency_ms=1.0,
            )

        mock_manager.run_cypher.side_effect = mock_run_cypher

        result = seed_tenant_graph(manager=mock_manager, tenant_id="acme_prod", reset=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["tenant_id"], "acme_prod")
        self.assertEqual(result["graph_name"], "nexus_acme_prod")
        self.assertEqual(result["total_nodes"], 24)
        self.assertEqual(result["total_edges"], 38)
        self.assertEqual(result["label_counts"]["Service"], 7)
        self.assertEqual(result["label_counts"]["Engineer"], 4)
        self.assertEqual(result["label_counts"]["Team"], 4)
        self.assertEqual(result["label_counts"]["Decision"], 2)

        # Verify DETACH DELETE was called
        calls = [c for c in mock_manager.run_cypher.call_args_list if "DETACH DELETE" in str(c)]
        self.assertEqual(len(calls), 1)

    def test_seed_tenant_graph_no_reset(self):
        mock_manager = MagicMock(spec=FalkorGraphManager)
        mock_manager._sanitize_tenant_id.return_value = "acme_prod"

        def mock_run_cypher(tenant_id, query, params=None, read_only=False):
            if "total_nodes" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[{"total_nodes": 10, "total_edges": 15}],
                    row_count=1,
                    latency_ms=1.0,
                )
            if "labels(n)" in query:
                return CypherQueryResult(
                    success=True,
                    tenant_id=tenant_id,
                    query=query,
                    data=[],
                    row_count=0,
                    latency_ms=1.0,
                )
            return CypherQueryResult(
                success=True,
                tenant_id=tenant_id,
                query=query,
                data=[],
                row_count=0,
                latency_ms=1.0,
            )

        mock_manager.run_cypher.side_effect = mock_run_cypher

        result = seed_tenant_graph(manager=mock_manager, tenant_id="acme_prod", reset=False)
        self.assertTrue(result["success"])

        # Verify DETACH DELETE was NOT called
        calls = [c for c in mock_manager.run_cypher.call_args_list if "DETACH DELETE" in str(c)]
        self.assertEqual(len(calls), 0)


if __name__ == "__main__":
    unittest.main()
