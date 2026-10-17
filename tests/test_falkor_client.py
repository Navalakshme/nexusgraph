"""Unit tests for FalkorGraphManager and Cypher query handling."""

import os
import unittest
from unittest.mock import MagicMock, patch
from falkordb import Node, Edge, Path
from src.db.falkor_client import (
    FalkorGraphManager,
    CypherQueryResult,
    format_falkordb_value,
    get_db_manager,
    run_cypher,
)


class TestFalkorClient(unittest.TestCase):
    def setUp(self):
        FalkorGraphManager.reset_instance()

    def tearDown(self):
        FalkorGraphManager.reset_instance()

    def test_singleton_pattern(self):
        m1 = get_db_manager()
        m2 = get_db_manager()
        self.assertIs(m1, m2)

    def test_tenant_sanitization(self):
        mgr = get_db_manager()
        self.assertEqual(mgr._sanitize_tenant_id("ACME-Prod 123!"), "acme_prod_123")
        self.assertEqual(mgr._sanitize_tenant_id(""), "acme_prod")
        self.assertEqual(mgr._sanitize_tenant_id("tenant_alpha"), "tenant_alpha")

    def test_formatting_falkordb_primitives(self):
        # Test Node formatting
        node = Node(node_id=42, labels=["Service", "Microservice"], properties={"name": "auth-api", "version": "2.1.0"})
        formatted_node = format_falkordb_value(node)
        self.assertEqual(formatted_node["id"], 42)
        self.assertIn("Service", formatted_node["labels"])
        self.assertEqual(formatted_node["properties"]["name"], "auth-api")
        self.assertEqual(formatted_node["_type"], "node")

        # Test Edge formatting
        node2 = Node(node_id=99, labels=["Database"], properties={"name": "user-db"})
        edge = Edge(src_node=node, relation="CONNECTS_TO", dest_node=node2, edge_id=77, properties={"protocol": "tls"})
        formatted_edge = format_falkordb_value(edge)
        self.assertEqual(formatted_edge["id"], 77)
        self.assertEqual(formatted_edge["relation"], "CONNECTS_TO")
        self.assertEqual(formatted_edge["src_node_id"], 42)
        self.assertEqual(formatted_edge["dest_node_id"], 99)
        self.assertEqual(formatted_edge["properties"]["protocol"], "tls")
        self.assertEqual(formatted_edge["_type"], "edge")

        # Test scalar formatting
        self.assertEqual(format_falkordb_value(100), 100)
        self.assertEqual(format_falkordb_value("hello"), "hello")
        self.assertIsNone(format_falkordb_value(None))

    def test_cypher_execution_with_mock_graph(self):
        mgr = get_db_manager({"host": "dummy.cloud", "port": 6379})
        mgr.is_connected = True
        mgr.client = MagicMock()

        # Mock graph and query result
        mock_graph = MagicMock()
        mgr._graphs["nexus_tenant_a"] = mock_graph

        node1 = Node(node_id=1, labels=["Agent"], properties={"name": "ArchitectAgent"})
        mock_res = MagicMock()
        mock_res.header = [["HEADER_TYPE_STRING", "a"]]
        mock_res.result_set = [[node1]]
        mock_res.nodes_created = 1
        mock_res.relationships_created = 0
        mock_res.run_time_ms = 1.2
        mock_graph.query.return_value = mock_res
        mock_graph.ro_query.return_value = mock_res

        # Execute write query
        result = mgr.run_cypher(
            tenant_id="tenant_a",
            query="CREATE (a:Agent {name: $name}) RETURN a",
            params={"name": "ArchitectAgent"},
            read_only=False,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.tenant_id, "tenant_a")
        self.assertEqual(result.row_count, 1)
        self.assertGreater(result.latency_ms, 0.0)
        self.assertEqual(result.data[0]["a"]["properties"]["name"], "ArchitectAgent")
        self.assertEqual(result.stats["nodes_created"], 1)

        # Check audit log
        audit = mgr.get_audit_log()
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["tenant_id"], "tenant_a")
        self.assertIn("CREATE (a:Agent", audit[0]["query"])

        # Execute read-only query
        ro_result = mgr.run_cypher(
            tenant_id="tenant_a",
            query="MATCH (a:Agent) RETURN a",
            read_only=True,
        )
        self.assertTrue(ro_result.success)
        mock_graph.ro_query.assert_called_once()
        self.assertEqual(len(mgr.get_audit_log()), 2)

    def test_placeholder_connection_rejection(self):
        # With default placeholder, connect should gracefully fail without crashing
        mgr = get_db_manager({"host": "your-instance.falkordb.cloud"})
        status = mgr.check_connection()
        self.assertFalse(status["connected"])
        self.assertIn("placeholder", status["error"])


if __name__ == "__main__":
    unittest.main()
