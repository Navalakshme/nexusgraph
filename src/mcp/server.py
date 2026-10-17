"""NexusGraph Model Context Protocol (MCP) Server.

Exposes FalkorDB graph reasoning, multi-hop root-cause tracing, decision lineage,
agent memory recall, handoffs, and graph actions to autonomous agents via MCP.
"""

import sys
import logging
from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP

from src.mcp.falkor_tools import (
    compute_blast_radius_and_criticality,
    trace_incident_root_cause_multihop,
    trace_company_decision_lineage,
    recall_agent_memories,
    record_agent_handoff,
    execute_graph_action_and_persist_memory,
)

logger = logging.getLogger("nexusgraph.mcp.server")
logging.basicConfig(level=logging.INFO)

# Initialize standard FastMCP Server
mcp = FastMCP("nexusgraph-falkordb-mcp")


@mcp.tool()
def blast_radius_and_criticality(
    tenant_id: str = "acme_prod",
    service_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute FalkorDB native PageRank algorithm and multi-hop downstream blast radius traversal.

    Args:
        tenant_id: Tenant identifier (nexus_{tenant_id})
        service_name: Target microservice name (e.g. 'payment-ledger' or 'auth-token-service')
    """
    return compute_blast_radius_and_criticality(tenant_id=tenant_id, service_name=service_name)


@mcp.tool()
def trace_incident_root_cause(
    tenant_id: str = "acme_prod",
    incident_id: str = "INC-2026-1015",
) -> Dict[str, Any]:
    """Execute 5-hop OpenCypher query connecting:
    Incident -> Affected Services -> Downstream Dependencies -> Recent Commits -> Pull Requests -> Engineer & Owning Team.
    Also returns violating decisions and Slack warnings.

    Args:
        tenant_id: Tenant identifier (nexus_{tenant_id})
        incident_id: Incident ID to investigate (e.g. 'INC-2026-1015')
    """
    return trace_incident_root_cause_multihop(tenant_id=tenant_id, incident_id=incident_id)


@mcp.tool()
def trace_decision_lineage(
    tenant_id: str = "acme_prod",
    service_name: str = "payment-ledger",
) -> Dict[str, Any]:
    """Query Company Brain for active and superseded architectural decisions (ADRs) governing
    the service, linked Slack warning discussions, Jira tickets, and expert engineers.

    Args:
        tenant_id: Tenant identifier (nexus_{tenant_id})
        service_name: Microservice name to retrieve decisions for (e.g. 'payment-ledger')
    """
    return trace_company_decision_lineage(tenant_id=tenant_id, service_name=service_name)


@mcp.tool()
def recall_memories(
    tenant_id: str = "acme_prod",
    service_name: str = "payment-ledger",
) -> Dict[str, Any]:
    """Recall cross-session persistent memories (EpisodicMemory, ProceduralRunbook, SemanticFact)
    linked to the service from prior agent investigations.

    Args:
        tenant_id: Tenant identifier (nexus_{tenant_id})
        service_name: Service name to recall memory for (e.g. 'payment-ledger')
    """
    return recall_agent_memories(tenant_id=tenant_id, service_name=service_name)


@mcp.tool()
def record_handoff(
    tenant_id: str = "acme_prod",
    session_id: str = "sess_default",
    from_agent: str = "TriageAgent",
    to_agent: str = "RemediationAgent",
    findings_summary: str = "Identified commit a8f921c as cause of connection starvation.",
    cypher_used: str = "MATCH (c:Commit {sha: 'a8f921c'})-[:VIOLATES]->(d:Decision) RETURN c, d",
) -> Dict[str, Any]:
    """Record an agent-to-agent coordination handoff edge directly into FalkorDB
    so coordination state lives inside the graph itself.

    Args:
        tenant_id: Tenant identifier (nexus_{tenant_id})
        session_id: Active session ID
        from_agent: Name of originating agent
        to_agent: Name of receiving agent
        findings_summary: Investigation summary handed off
        cypher_used: Cypher query executed by originating agent
    """
    return record_agent_handoff(
        tenant_id=tenant_id,
        session_id=session_id,
        from_agent=from_agent,
        to_agent=to_agent,
        findings_summary=findings_summary,
        cypher_used=cypher_used,
    )


@mcp.tool()
def execute_graph_action(
    tenant_id: str = "acme_prod",
    session_id: str = "sess_default",
    incident_id: str = "INC-2026-1015",
    service_name: str = "payment-ledger",
    action_taken: str = "Reverted commit a8f921c and enabled circuit breaker flag via RUNBOOK-07",
    learned_fact: str = "Payment ledger retry pool must never exceed 10 threads without circuit breaker flag active",
) -> Dict[str, Any]:
    """Mutate FalkorDB graph based on autonomous agent actions:
    - Mitigates Incident and links RemediationAction
    - Creates persistent EpisodicMemory linked to Session and Incident
    - Creates or updates SemanticFact on the Service for future sessions

    Args:
        tenant_id: Tenant identifier (nexus_{tenant_id})
        session_id: Active session ID
        incident_id: Incident mitigated
        service_name: Service remediated
        action_taken: Remediation steps performed
        learned_fact: Enduring rule learned to avoid future recurrence
    """
    return execute_graph_action_and_persist_memory(
        tenant_id=tenant_id,
        session_id=session_id,
        incident_id=incident_id,
        service_name=service_name,
        action_taken=action_taken,
        learned_fact=learned_fact,
    )


if __name__ == "__main__":
    logger.info("Starting NexusGraph FalkorDB FastMCP Server...")
    mcp.run()
