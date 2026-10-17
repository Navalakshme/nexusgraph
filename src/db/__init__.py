"""Database package for NexusGraph FalkorDB integration."""
from src.db.falkor_client import FalkorGraphManager, CypherQueryResult, get_db_manager, run_cypher


def seed_tenant_graph(*args, **kwargs):
    from src.db.seed_company_brain import seed_tenant_graph as _seed
    return _seed(*args, **kwargs)


__all__ = [
    "FalkorGraphManager",
    "CypherQueryResult",
    "get_db_manager",
    "run_cypher",
    "seed_tenant_graph",
]
