"""NexusGraph FalkorDB Client & Manager.

Provides direct connectivity to FalkorDB Cloud with:
- Singleton management with thread-safe access
- Multi-tenant graph isolation (nexus_{tenant_id}) satisfying Hackathon Track 02
- Streamlit session state and .env credential resolution
- Query execution latency measurement in milliseconds
- Real-time in-memory and session-accessible query audit trail
- Robust node, edge, and path serialization into native Python dicts/lists
"""

import os
import re
import sys
import time
import logging
import threading
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

logger = logging.getLogger("nexusgraph.falkordb")
logging.basicConfig(level=logging.INFO)

try:
    from falkordb import FalkorDB, Graph, QueryResult, Node, Edge, Path
    FALKORDB_AVAILABLE = True
except ImportError:
    FALKORDB_AVAILABLE = False
    FalkorDB = None
    Graph = None
    QueryResult = None
    Node = None
    Edge = None
    Path = None

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None


def format_falkordb_value(val: Any) -> Any:
    """Format FalkorDB primitives, Nodes, Edges, and Paths into standard Python types."""
    if val is None:
        return None

    # FalkorDB Node
    if Node is not None and isinstance(val, Node):
        return {
            "id": getattr(val, "id", None),
            "labels": list(getattr(val, "labels", [])),
            "properties": dict(getattr(val, "properties", {})),
            "_type": "node",
        }

    # FalkorDB Edge
    if Edge is not None and isinstance(val, Edge):
        src_node = getattr(val, "src_node", None)
        dest_node = getattr(val, "dest_node", None)
        return {
            "id": getattr(val, "id", None),
            "relation": getattr(val, "relation", ""),
            "src_node_id": getattr(src_node, "id", None) if src_node is not None else None,
            "dest_node_id": getattr(dest_node, "id", None) if dest_node is not None else None,
            "properties": dict(getattr(val, "properties", {})),
            "_type": "edge",
        }

    # FalkorDB Path
    if Path is not None and isinstance(val, Path):
        raw_nodes = val.nodes() if callable(getattr(val, "nodes", None)) else getattr(val, "nodes", [])
        raw_edges = val.edges() if callable(getattr(val, "edges", None)) else getattr(val, "edges", [])
        return {
            "nodes": [format_falkordb_value(n) for n in raw_nodes],
            "edges": [format_falkordb_value(e) for e in raw_edges],
            "_type": "path",
        }

    # Dict
    if isinstance(val, dict):
        return {k: format_falkordb_value(v) for k, v in val.items()}

    # List / Tuple / Set
    if isinstance(val, (list, tuple, set)):
        return [format_falkordb_value(item) for item in val]

    # Native scalars (int, float, str, bool)
    return val


@dataclass
class CypherQueryResult:
    """Standardized result envelope for Cypher queries executed on FalkorDB."""
    success: bool
    tenant_id: str
    query: str
    params: Dict[str, Any] = field(default_factory=dict)
    data: List[Dict[str, Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    row_count: int = 0
    latency_ms: float = 0.0
    stats: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    read_only: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert result envelope to dictionary."""
        return {
            "success": self.success,
            "tenant_id": self.tenant_id,
            "query": self.query,
            "params": self.params,
            "data": self.data,
            "columns": self.columns,
            "row_count": self.row_count,
            "latency_ms": self.latency_ms,
            "stats": self.stats,
            "error": self.error,
            "read_only": self.read_only,
            "timestamp": self.timestamp,
        }

    def to_dataframe(self) -> Any:
        """Convert result records to a Pandas DataFrame."""
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is required for to_dataframe()")
        return pd.DataFrame(self.data)

    def __iter__(self):
        """Allow direct iteration over rows."""
        return iter(self.data)

    def __len__(self) -> int:
        return self.row_count

    def __getitem__(self, index: int) -> Dict[str, Any]:
        return self.data[index]


class FalkorGraphManager:
    """Singleton connection manager for FalkorDB Cloud.

    Provides multi-tenant graph isolation, automatic credential resolution
    (env vars or Streamlit session overrides), query latency measurement,
    and a query audit trail for live UI inspection.
    """

    _instance: Optional["FalkorGraphManager"] = None
    _lock = threading.Lock()

    def __init__(self, overrides: Optional[Dict[str, Any]] = None):
        """Initialize the FalkorDB manager.

        Args:
            overrides: Optional credential dictionary to override environment variables.
        """
        self._lock = threading.Lock()
        self.client: Optional[FalkorDB] = None
        self._graphs: Dict[str, Any] = {}
        self.query_audit_log: List[Dict[str, Any]] = []
        self._max_audit_log_size = 500

        # Connection status tracking
        self.is_connected = False
        self.connection_error: Optional[str] = None
        self.active_host: Optional[str] = None
        self.active_port: Optional[int] = None

        # Credentials configuration
        self.configure(overrides)

    @classmethod
    def get_instance(cls, overrides: Optional[Dict[str, Any]] = None) -> "FalkorGraphManager":
        """Get or initialize the thread-safe singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(overrides=overrides)
        elif overrides:
            with cls._lock:
                cls._instance.configure(overrides)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for tests)."""
        with cls._lock:
            cls._instance = None

    def _is_streamlit_active(self) -> bool:
        """Return True only if running within an active Streamlit server context."""
        if "streamlit" not in sys.modules:
            return False
        try:
            from streamlit.runtime import exists
            return bool(exists())
        except Exception:
            return False

    def _get_streamlit_override(self, key: str) -> Optional[Any]:
        """Check Streamlit session state for runtime user credentials."""
        if self._is_streamlit_active():
            try:
                import streamlit as st
                if hasattr(st, "session_state") and st.session_state is not None:
                    return st.session_state.get(key)
            except Exception:
                pass
    def _get_streamlit_secret(self, key: str) -> Optional[Any]:
        """Check Streamlit secrets for securely deployed cloud environment variables."""
        if "streamlit" in sys.modules:
            try:
                import streamlit as st
                if hasattr(st, "secrets") and key in st.secrets:
                    return st.secrets[key]
            except Exception:
                pass
        return None

    def configure(self, overrides: Optional[Dict[str, Any]] = None) -> None:
        """Configure credentials with resolution precedence:
        1. Explicit overrides argument
        2. Streamlit Cloud Secrets (for secure public deployment)
        3. Streamlit session_state
        4. Environment variables / .env
        """
        overrides = overrides or {}

        # 1. Resolve host
        host = (
            overrides.get("host")
            or overrides.get("FALKORDB_HOST")
            or self._get_streamlit_secret("FALKORDB_HOST")
            or self._get_streamlit_override("falkor_host")
            or os.getenv("FALKORDB_HOST", "localhost")
        )

        # 2. Resolve port
        port_raw = (
            overrides.get("port")
            or overrides.get("FALKORDB_PORT")
            or self._get_streamlit_secret("FALKORDB_PORT")
            or self._get_streamlit_override("falkor_port")
            or os.getenv("FALKORDB_PORT", "6379")
        )
        try:
            port = int(port_raw)
        except (ValueError, TypeError):
            port = 6379

        # 3. Resolve username
        username = (
            overrides.get("username")
            or overrides.get("FALKORDB_USERNAME")
            or self._get_streamlit_secret("FALKORDB_USERNAME")
            or self._get_streamlit_override("falkor_username")
            or os.getenv("FALKORDB_USERNAME", "falkordb")
        )
        if username and username.strip() in ("", "None", "none"):
            username = None

        # 4. Resolve password
        password = (
            overrides.get("password")
            or overrides.get("FALKORDB_PASSWORD")
            or self._get_streamlit_secret("FALKORDB_PASSWORD")
            or self._get_streamlit_override("falkor_password")
            or os.getenv("FALKORDB_PASSWORD")
        )
        if password and password.strip() in ("", "None", "none", "your-password"):
            password = None

        # 5. Resolve default tenant
        default_tenant = (
            overrides.get("default_tenant")
            or overrides.get("FALKORDB_DEFAULT_TENANT")
            or self._get_streamlit_override("falkor_tenant")
            or os.getenv("FALKORDB_DEFAULT_TENANT", "acme_prod")
        )

        # 6. Resolve SSL
        ssl_raw = (
            overrides.get("ssl")
            or overrides.get("FALKORDB_SSL")
            or self._get_streamlit_override("falkor_ssl")
            or os.getenv("FALKORDB_SSL", "false")
        )
        if isinstance(ssl_raw, str):
            ssl = ssl_raw.strip().lower() in ("true", "1", "yes")
        else:
            ssl = bool(ssl_raw)

        # Update instance config
        self.host = str(host).strip()
        self.port = port
        self.username = username.strip() if username else None
        self.password = password.strip() if password else None
        self.default_tenant = self._sanitize_tenant_id(str(default_tenant))
        self.ssl = ssl

        # Invalidate existing client and graphs on reconfiguration
        self.client = None
        self._graphs.clear()
        self.is_connected = False
        self.connection_error = None

    def _sanitize_tenant_id(self, tenant_id: Optional[str]) -> str:
        """Sanitize tenant ID to safe alphanumeric characters and underscores."""
        if not tenant_id:
            tenant_id = self.default_tenant or "default"
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", str(tenant_id).strip().lower())
        return clean.strip("_") or "default"

    def connect(self) -> bool:
        """Establish direct connection to FalkorDB Cloud.

        Returns:
            bool: True if connection is successfully established, False otherwise.
        """
        if not FALKORDB_AVAILABLE:
            self.connection_error = "falkordb Python package is not installed."
            self.is_connected = False
            return False

        # Check if placeholder credentials are in use
        if self.host in ("your-instance.falkordb.cloud", "placeholder", ""):
            self.connection_error = (
                f"FalkorDB host '{self.host}' is a placeholder. Please configure valid credentials "
                "in .env or in the Streamlit UI sidebar."
            )
            self.is_connected = False
            return False

        try:
            connect_kwargs: Dict[str, Any] = {
                "host": self.host,
                "port": self.port,
                "ssl": self.ssl,
            }
            if self.password:
                connect_kwargs["password"] = self.password
            if self.username:
                connect_kwargs["username"] = self.username

            logger.info("Connecting to FalkorDB at %s:%s (SSL=%s, user=%s)",
                        self.host, self.port, self.ssl, self.username)
            self.client = FalkorDB(**connect_kwargs)
            self.active_host = self.host
            self.active_port = self.port
            self.is_connected = True
            self.connection_error = None
            return True
        except Exception as e:
            self.client = None
            self.is_connected = False
            self.connection_error = str(e)
            logger.warning("Failed to connect to FalkorDB (%s:%s): %s", self.host, self.port, e)
            return False

    def reconnect(self, **overrides) -> bool:
        """Reconfigure and reconnect to FalkorDB."""
        self.configure(overrides)
        return self.connect()

    def check_connection(self) -> Dict[str, Any]:
        """Perform a live health-check ping against FalkorDB.

        Returns:
            Dict containing connection status, latency, and host details.
        """
        if not self.is_connected or self.client is None:
            success = self.connect()
            if not success:
                return {
                    "connected": False,
                    "host": self.host,
                    "port": self.port,
                    "error": self.connection_error,
                    "latency_ms": 0.0,
                }

        start = time.perf_counter()
        try:
            # Query a ping on default tenant graph
            graph = self.get_graph(self.default_tenant)
            res = graph.query("RETURN 1 AS ping")
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "connected": True,
                "host": self.host,
                "port": self.port,
                "tenant": self.default_tenant,
                "latency_ms": latency_ms,
                "error": None,
                "raw_result": res.result_set if hasattr(res, "result_set") else None,
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            self.is_connected = False
            self.connection_error = str(e)
            return {
                "connected": False,
                "host": self.host,
                "port": self.port,
                "latency_ms": latency_ms,
                "error": str(e),
            }

    def get_graph(self, tenant_id: Optional[str] = None) -> Any:
        """Select a multi-tenant graph: nexus_{tenant_id}.

        Enforces Track 02 Multi-Tenant Memory Isolation by namespace-prefixing
        every graph with `nexus_`.

        Args:
            tenant_id: Tenant identifier. Defaults to self.default_tenant.

        Returns:
            FalkorDB Graph instance.
        """
        if not self.is_connected or self.client is None:
            if not self.connect():
                raise ConnectionError(
                    f"Not connected to FalkorDB: {self.connection_error or 'Unknown connection error'}"
                )

        clean_tenant = self._sanitize_tenant_id(tenant_id)
        graph_name = f"nexus_{clean_tenant}"

        with self._lock:
            if graph_name not in self._graphs:
                self._graphs[graph_name] = self.client.select_graph(graph_name)
            return self._graphs[graph_name]

    def _sync_audit_log_to_streamlit(self, entry: Dict[str, Any]) -> None:
        """Mirror audit log entry into Streamlit session_state for live judge visualization."""
        if self._is_streamlit_active():
            try:
                import streamlit as st
                if hasattr(st, "session_state") and st.session_state is not None:
                    if "query_audit_log" not in st.session_state:
                        st.session_state["query_audit_log"] = []
                    st.session_state["query_audit_log"].insert(0, entry)
                    if len(st.session_state["query_audit_log"]) > self._max_audit_log_size:
                        st.session_state["query_audit_log"].pop()
            except Exception:
                pass

    def run_cypher(
        self,
        tenant_id: Optional[str] = None,
        query: str = "",
        params: Optional[Dict[str, Any]] = None,
        read_only: bool = False,
    ) -> CypherQueryResult:
        """Execute a Cypher query on the designated multi-tenant graph.

        - Executes ro_query when read_only=True or query when read_only=False
        - Measures execution latency in milliseconds
        - Records query, parameters, row count, and latency into query_audit_log
        - Formats result_set cleanly into Python dicts/lists

        Args:
            tenant_id: Target tenant id (nexus_{tenant_id})
            query: Cypher query string
            params: Query parameter mapping
            read_only: If True, executes using ro_query (read-only replica/mode)

        Returns:
            CypherQueryResult containing structured records, latency, and stats.
        """
        clean_tenant = self._sanitize_tenant_id(tenant_id)
        params = params or {}
        start_time = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()

        # Check connection status
        if not self.is_connected or self.client is None:
            if not self.connect():
                err_msg = f"FalkorDB connection unavailable: {self.connection_error}"
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                res = CypherQueryResult(
                    success=False,
                    tenant_id=clean_tenant,
                    query=query,
                    params=params,
                    latency_ms=elapsed_ms,
                    error=err_msg,
                    read_only=read_only,
                    timestamp=timestamp,
                )
                self._record_audit_entry(res.to_dict())
                return res

        try:
            graph = self.get_graph(clean_tenant)
            
            # Execute query based on read_only flag
            if read_only:
                raw_res = graph.ro_query(query, params)
            else:
                raw_res = graph.query(query, params)

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Extract columns and result records
            header = list(getattr(raw_res, "header", []) or [])
            # In FalkorDB, header elements might be strings or column descriptors
            columns = [str(col[1] if isinstance(col, (list, tuple)) and len(col) > 1 else col) for col in header]

            raw_records = getattr(raw_res, "result_set", []) or []
            formatted_data: List[Dict[str, Any]] = []

            for row in raw_records:
                record_dict: Dict[str, Any] = {}
                if columns:
                    for idx, col_name in enumerate(columns):
                        val = row[idx] if idx < len(row) else None
                        record_dict[col_name] = format_falkordb_value(val)
                else:
                    # If no columns header was provided
                    for idx, val in enumerate(row):
                        record_dict[f"col_{idx}"] = format_falkordb_value(val)
                formatted_data.append(record_dict)

            # Extract execution statistics
            stats = {
                "nodes_created": getattr(raw_res, "nodes_created", 0),
                "nodes_deleted": getattr(raw_res, "nodes_deleted", 0),
                "relationships_created": getattr(raw_res, "relationships_created", 0),
                "relationships_deleted": getattr(raw_res, "relationships_deleted", 0),
                "properties_set": getattr(raw_res, "properties_set", 0),
                "labels_added": getattr(raw_res, "labels_added", 0),
                "server_run_time_ms": getattr(raw_res, "run_time_ms", None),
            }

            result_obj = CypherQueryResult(
                success=True,
                tenant_id=clean_tenant,
                query=query,
                params=params,
                data=formatted_data,
                columns=columns,
                row_count=len(formatted_data),
                latency_ms=elapsed_ms,
                stats=stats,
                read_only=read_only,
                timestamp=timestamp,
            )

            self._record_audit_entry(result_obj.to_dict())
            return result_obj

        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            err_msg = str(e)
            if "already indexed" in err_msg.lower():
                logger.debug("Cypher index notice on tenant 'nexus_%s': %s", clean_tenant, err_msg)
            else:
                logger.error("Cypher execution failed on tenant 'nexus_%s' (%s ms): %s",
                             clean_tenant, elapsed_ms, err_msg)
            result_obj = CypherQueryResult(
                success=False,
                tenant_id=clean_tenant,
                query=query,
                params=params,
                latency_ms=elapsed_ms,
                error=err_msg,
                read_only=read_only,
                timestamp=timestamp,
            )
            self._record_audit_entry(result_obj.to_dict())
            return result_obj

    def _record_audit_entry(self, entry: Dict[str, Any]) -> None:
        """Store audit record in-memory and mirror to Streamlit session state."""
        with self._lock:
            self.query_audit_log.insert(0, entry)
            if len(self.query_audit_log) > self._max_audit_log_size:
                self.query_audit_log.pop()
        self._sync_audit_log_to_streamlit(entry)

    def get_audit_log(self, limit: int = 50, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent query audit log entries.

        Args:
            limit: Maximum entries to return.
            tenant_id: Optional tenant filter.

        Returns:
            List of audit log records.
        """
        with self._lock:
            entries = self.query_audit_log
            if tenant_id:
                clean_tenant = self._sanitize_tenant_id(tenant_id)
                entries = [e for e in entries if e.get("tenant_id") == clean_tenant]
            return list(entries[:limit])

    def clear_audit_log(self) -> None:
        """Clear query audit log."""
        with self._lock:
            self.query_audit_log.clear()
        if self._is_streamlit_active():
            try:
                import streamlit as st
                if hasattr(st, "session_state") and "query_audit_log" in st.session_state:
                    st.session_state["query_audit_log"] = []
            except Exception:
                pass


def get_db_manager(overrides: Optional[Dict[str, Any]] = None) -> FalkorGraphManager:
    """Convenience getter for FalkorGraphManager singleton."""
    return FalkorGraphManager.get_instance(overrides=overrides)


def run_cypher(
    query: str,
    params: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
    read_only: bool = False,
) -> CypherQueryResult:
    """Convenience functional wrapper for executing Cypher queries."""
    mgr = get_db_manager()
    return mgr.run_cypher(tenant_id=tenant_id, query=query, params=params, read_only=read_only)
