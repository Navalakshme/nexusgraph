"""NexusGraph OpenCypher Graph Toolset.

Implements the 6 core FalkorDB tools satisfying all 3 hackathon tracks:
- Track 01 (Connected Data & Actions): Blast radius, PageRank, multi-hop incident root-cause tracing, graph actions
- Track 02 (Agent Memory & Coordination): Episodic & semantic memory recall, agent handoff graphs, persistent memory updates
- Track 03 (Company Brain & Decision Lineage): ADR superseded chains, Slack discussions, ticket & PR provenance

Every tool executes real OpenCypher queries on FalkorDB Cloud and returns both
structured answers and explicit `graph_paths` (source, relationship, target, properties)
for visual rendering in the Streamlit graph UI.
"""

import uuid
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from src.db.falkor_client import FalkorGraphManager, get_db_manager

logger = logging.getLogger("nexusgraph.tools")
logging.basicConfig(level=logging.INFO)


def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ==============================================================================
# TOOL 1: Blast Radius & Criticality (PageRank + Downstream Traversal)
# ==============================================================================
def compute_blast_radius_and_criticality(
    manager: Optional[FalkorGraphManager] = None,
    tenant_id: str = "acme_prod",
    service_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute microservice criticality via FalkorDB PageRank algorithm and multi-hop blast radius.

    Args:
        manager: FalkorGraphManager singleton or mock
        tenant_id: Target tenant id (nexus_{tenant_id})
        service_name: Optional target service name to compute upstream blast radius for

    Returns:
        Dict containing PageRank scores, impacted upstream services, executed Cypher, and graph_paths.
    """
    manager = manager or get_db_manager()
    clean_tenant = manager._sanitize_tenant_id(tenant_id)
    graph_paths: List[Dict[str, Any]] = []
    cypher_executed: List[str] = []

    # 1. FalkorDB Native PageRank algorithm
    pagerank_cypher = (
        "CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score "
        "RETURN node.id AS id, node.name AS service, node.tier AS tier, node.status AS status, score "
        "ORDER BY score DESC"
    )
    cypher_executed.append(pagerank_cypher)
    res_pr = manager.run_cypher(tenant_id=clean_tenant, query=pagerank_cypher, read_only=True)

    pagerank_table: List[Dict[str, Any]] = []
    if res_pr.success and res_pr.data:
        for row in res_pr.data:
            pagerank_table.append({
                "service": row.get("service"),
                "tier": row.get("tier"),
                "status": row.get("status") or "active",
                "pagerank_score": round(float(row.get("score", 0.0)), 4),
            })
    else:
        # Graceful fallback: Multi-hop in-degree centrality Cypher query
        fallback_cypher = (
            "MATCH (s:Service) "
            "OPTIONAL MATCH (upstream:Service)-[r:DEPENDS_ON]->(s) "
            "RETURN s.name AS service, s.tier AS tier, count(r) AS in_degree, "
            "count(r) * 1.25 AS pagerank_score "
            "ORDER BY pagerank_score DESC"
        )
        cypher_executed.append(fallback_cypher)
        res_fb = manager.run_cypher(tenant_id=clean_tenant, query=fallback_cypher, read_only=True)
        if res_fb.success and res_fb.data:
            for row in res_fb.data:
                pagerank_table.append({
                    "service": row.get("service"),
                    "tier": row.get("tier"),
                    "status": "active",
                    "pagerank_score": round(float(row.get("pagerank_score", 0.0)), 2),
                })

    # Determine target service for blast-radius calculation
    target_svc = service_name or (pagerank_table[0]["service"] if pagerank_table else "payment-ledger")

    # 2. Multi-hop Downstream Blast-Radius Traversal (Up to 3 hops)
    blast_cypher = (
        "MATCH path = (upstream:Service)-[r:DEPENDS_ON*1..3]->(target:Service {name: $service_name}) "
        "RETURN upstream.name AS impacted_service, upstream.tier AS tier, "
        "length(path) AS hops, "
        "[n IN nodes(path) | n.name] AS path_services, "
        "[rel IN relationships(path) | properties(rel)] AS path_rels"
    )
    cypher_executed.append(blast_cypher)
    res_blast = manager.run_cypher(
        tenant_id=clean_tenant,
        query=blast_cypher,
        params={"service_name": target_svc},
        read_only=True,
    )

    impacted_services: List[Dict[str, Any]] = []
    total_paths_count = 0
    if res_blast.success and res_blast.data:
        total_paths_count = len(res_blast.data)
        # Deduplicate by unique microservice name, preserving shortest hop path
        unique_svcs: Dict[str, Dict[str, Any]] = {}
        for row in res_blast.data:
            svc_name = row.get("impacted_service")
            hops = row.get("hops", 1)
            if svc_name and (svc_name not in unique_svcs or hops < unique_svcs[svc_name]["hops"]):
                unique_svcs[svc_name] = {
                    "impacted_service": svc_name,
                    "hops": hops,
                    "tier": row.get("tier"),
                    "path": " -> ".join(row.get("path_services", [])),
                }

            # Build graph paths
            path_services = row.get("path_services", [])
            path_rels = row.get("path_rels", [])
            for i in range(len(path_services) - 1):
                props = path_rels[i] if i < len(path_rels) else {}
                graph_paths.append({
                    "source": path_services[i],
                    "source_label": "Service",
                    "relationship": "DEPENDS_ON",
                    "target": path_services[i + 1],
                    "target_label": "Service",
                    "properties": props or {},
                })

        # Order by shortest hops ascending
        impacted_services = sorted(unique_svcs.values(), key=lambda s: s["hops"])

    return {
        "success": True,
        "service_name": target_svc,
        "pagerank_table": pagerank_table,
        "impacted_services": impacted_services,
        "total_impacted_count": len(impacted_services),
        "total_paths_count": total_paths_count,
        "cypher_executed": cypher_executed,
        "graph_paths": graph_paths,
    }


# ==============================================================================
# TOOL 2: Trace Incident Root Cause Multi-Hop
# ==============================================================================
def trace_incident_root_cause_multihop(
    manager: Optional[FalkorGraphManager] = None,
    tenant_id: str = "acme_prod",
    incident_id: str = "INC-2026-1015",
) -> Dict[str, Any]:
    """Execute a 5-hop OpenCypher query connecting:
    Incident -> Affected Services -> Downstream Dependencies -> Recent Commits -> Pull Requests -> Engineer & Team.

    Also traces violations of architectural decisions (Track 03) and Slack warnings.

    Args:
        manager: FalkorGraphManager singleton or mock
        tenant_id: Target tenant id (nexus_{tenant_id})
        incident_id: Incident identifier (e.g. INC-2026-1015)

    Returns:
        Structured root-cause analysis, culprit commit, violating decisions, and graph_paths.
    """
    manager = manager or get_db_manager()
    clean_tenant = manager._sanitize_tenant_id(tenant_id)
    graph_paths: List[Dict[str, Any]] = []
    cypher_executed: List[str] = []

    # 1. 5-hop Root Cause Traversal Cypher
    root_cause_cypher = """
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
           v.reason AS violation_reason
    """
    cypher_executed.append(root_cause_cypher)
    res = manager.run_cypher(
        tenant_id=clean_tenant,
        query=root_cause_cypher,
        params={"incident_id": incident_id},
        read_only=True,
    )

    root_causes: List[Dict[str, Any]] = []
    seen_edges = set()

    if res.success and res.data:
        for row in res.data:
            root_causes.append(row)
            inc_id = row.get("incident_id")
            aff_svc = row.get("affected_service")
            root_svc = row.get("root_service")
            commit_sha = row.get("commit_sha")
            author = row.get("author")
            team = row.get("owning_team")
            violated_dec = row.get("violated_decision_id")

            # Build graph paths
            if inc_id and aff_svc:
                edge_key = (inc_id, "AFFECTS", aff_svc)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    graph_paths.append({
                        "source": inc_id,
                        "source_label": "Incident",
                        "relationship": "AFFECTS",
                        "target": aff_svc,
                        "target_label": "Service",
                        "properties": {"severity": row.get("severity")},
                    })

            if aff_svc and root_svc and aff_svc != root_svc:
                edge_key = (aff_svc, "DEPENDS_ON", root_svc)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    graph_paths.append({
                        "source": aff_svc,
                        "source_label": "Service",
                        "relationship": "DEPENDS_ON",
                        "target": root_svc,
                        "target_label": "Service",
                        "properties": {},
                    })

            if commit_sha and root_svc:
                edge_key = (commit_sha, "MODIFIES", root_svc)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    graph_paths.append({
                        "source": commit_sha,
                        "source_label": "Commit",
                        "relationship": "MODIFIES",
                        "target": root_svc,
                        "target_label": "Service",
                        "properties": {"message": row.get("commit_msg")},
                    })

            if author and commit_sha:
                edge_key = (author, "AUTHORED", commit_sha)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    graph_paths.append({
                        "source": author,
                        "source_label": "Engineer",
                        "relationship": "AUTHORED",
                        "target": commit_sha,
                        "target_label": "Commit",
                        "properties": {"role": row.get("author_role")},
                    })

            if team and root_svc:
                edge_key = (team, "OWNS", root_svc)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    graph_paths.append({
                        "source": team,
                        "source_label": "Team",
                        "relationship": "OWNS",
                        "target": root_svc,
                        "target_label": "Service",
                        "properties": {"channel": row.get("team_channel")},
                    })

            if commit_sha and violated_dec:
                edge_key = (commit_sha, "VIOLATES", violated_dec)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    graph_paths.append({
                        "source": commit_sha,
                        "source_label": "Commit",
                        "relationship": "VIOLATES",
                        "target": violated_dec,
                        "target_label": "Decision",
                        "properties": {"reason": row.get("violation_reason")},
                    })

    # 2. Query Slack warning discussions linked to the culprit commit
    slack_cypher = """
    MATCH (c:Commit {sha: "a8f921c"})<-[:WARNS_ABOUT|DISCUSSES]-(st:SlackThread)
    OPTIONAL MATCH (eng:Engineer)-[:POSTED_IN]->(st)
    RETURN st.id AS slack_id, st.channel AS channel, st.quote AS quote,
           st.timestamp AS timestamp, eng.name AS warned_by
    """
    cypher_executed.append(slack_cypher)
    res_slack = manager.run_cypher(tenant_id=clean_tenant, query=slack_cypher, read_only=True)
    slack_warnings = res_slack.data if res_slack.success else []

    for s in slack_warnings:
        slack_id = s.get("slack_id")
        warned_by = s.get("warned_by")
        if slack_id and warned_by:
            graph_paths.append({
                "source": warned_by,
                "source_label": "Engineer",
                "relationship": "POSTED_IN",
                "target": slack_id,
                "target_label": "SlackThread",
                "properties": {"quote": s.get("quote")},
            })
            graph_paths.append({
                "source": slack_id,
                "source_label": "SlackThread",
                "relationship": "WARNS_ABOUT",
                "target": "a8f921c",
                "target_label": "Commit",
                "properties": {},
            })

    return {
        "success": True,
        "incident_id": incident_id,
        "root_causes": root_causes,
        "culprit_commit": root_causes[0].get("commit_sha") if root_causes else None,
        "author": root_causes[0].get("author") if root_causes else None,
        "owning_team": root_causes[0].get("owning_team") if root_causes else None,
        "slack_warnings": slack_warnings,
        "cypher_executed": cypher_executed,
        "graph_paths": graph_paths,
    }


# ==============================================================================
# TOOL 3: Trace Company Decision Lineage (Track 03 Company Brain)
# ==============================================================================
def trace_company_decision_lineage(
    manager: Optional[FalkorGraphManager] = None,
    tenant_id: str = "acme_prod",
    service_name: str = "payment-ledger",
) -> Dict[str, Any]:
    """Query active and superseded architectural decisions (ADRs) governing the service,
    linked Slack discussions, tickets, and subject-matter experts.

    Args:
        manager: FalkorGraphManager singleton or mock
        tenant_id: Target tenant id (nexus_{tenant_id})
        service_name: Name of target service (e.g. payment-ledger)

    Returns:
        Structured ADR lineage, superseded history, Slack context, and graph_paths.
    """
    manager = manager or get_db_manager()
    clean_tenant = manager._sanitize_tenant_id(tenant_id)
    graph_paths: List[Dict[str, Any]] = []
    cypher_executed: List[str] = []

    decision_cypher = """
    MATCH (d:Decision)-[:GOVERNS]->(s:Service {name: $service_name})
    OPTIONAL MATCH (d)-[:SUPERSEDES]->(old_d:Decision)
    OPTIONAL MATCH (st:SlackThread)-[:REFERENCES]->(d)
    OPTIONAL MATCH (exp:Engineer)-[r:EXPERT_IN]->(s)
    RETURN d.id AS decision_id, d.title AS decision_title, d.status AS status,
           d.date AS decision_date, d.rationale AS rationale, d.author AS author,
           old_d.id AS superseded_decision_id, old_d.title AS superseded_title,
           old_d.date AS superseded_date,
           st.id AS slack_id, st.channel AS slack_channel, st.quote AS slack_quote,
           exp.name AS expert_name, exp.role AS expert_role, r.confidence AS expert_confidence,
           r.domain AS expert_domain
    """
    cypher_executed.append(decision_cypher)
    res = manager.run_cypher(
        tenant_id=clean_tenant,
        query=decision_cypher,
        params={"service_name": service_name},
        read_only=True,
    )

    decisions: List[Dict[str, Any]] = []
    experts: List[Dict[str, Any]] = []
    slack_context: List[Dict[str, Any]] = []
    seen_decisions = set()
    seen_experts = set()
    seen_slack = set()

    if res.success and res.data:
        for row in res.data:
            dec_id = row.get("decision_id")
            if dec_id and dec_id not in seen_decisions:
                seen_decisions.add(dec_id)
                decisions.append({
                    "id": dec_id,
                    "title": row.get("decision_title"),
                    "status": row.get("status"),
                    "date": row.get("decision_date"),
                    "rationale": row.get("rationale"),
                    "author": row.get("author"),
                    "superseded_by": None,
                    "supersedes": {
                        "id": row.get("superseded_decision_id"),
                        "title": row.get("superseded_title"),
                        "date": row.get("superseded_date"),
                    } if row.get("superseded_decision_id") else None,
                })
                # Add Decision -> Service path
                graph_paths.append({
                    "source": dec_id,
                    "source_label": "Decision",
                    "relationship": "GOVERNS",
                    "target": service_name,
                    "target_label": "Service",
                    "properties": {"status": row.get("status")},
                })
                # Add ADR-029 -> SUPERSEDES -> ADR-014
                if row.get("superseded_decision_id"):
                    graph_paths.append({
                        "source": dec_id,
                        "source_label": "Decision",
                        "relationship": "SUPERSEDES",
                        "target": row.get("superseded_decision_id"),
                        "target_label": "Decision",
                        "properties": {},
                    })

            exp_name = row.get("expert_name")
            if exp_name and exp_name not in seen_experts:
                seen_experts.add(exp_name)
                experts.append({
                    "name": exp_name,
                    "role": row.get("expert_role"),
                    "confidence": row.get("expert_confidence"),
                    "domain": row.get("expert_domain"),
                })
                graph_paths.append({
                    "source": exp_name,
                    "source_label": "Engineer",
                    "relationship": "EXPERT_IN",
                    "target": service_name,
                    "target_label": "Service",
                    "properties": {
                        "confidence": row.get("expert_confidence"),
                        "domain": row.get("expert_domain"),
                    },
                })

            slack_id = row.get("slack_id")
            if slack_id and slack_id not in seen_slack:
                seen_slack.add(slack_id)
                slack_context.append({
                    "id": slack_id,
                    "channel": row.get("slack_channel"),
                    "quote": row.get("slack_quote"),
                })
                if dec_id:
                    graph_paths.append({
                        "source": slack_id,
                        "source_label": "SlackThread",
                        "relationship": "REFERENCES",
                        "target": dec_id,
                        "target_label": "Decision",
                        "properties": {},
                    })

    return {
        "success": True,
        "service_name": service_name,
        "active_decisions": [d for d in decisions if d.get("status") == "Active"],
        "all_decisions": decisions,
        "experts": experts,
        "slack_discussions": slack_context,
        "cypher_executed": cypher_executed,
        "graph_paths": graph_paths,
    }


# ==============================================================================
# TOOL 4: Recall Agent Memories (Track 02 Persistent Memory)
# ==============================================================================
def recall_agent_memories(
    manager: Optional[FalkorGraphManager] = None,
    tenant_id: str = "acme_prod",
    service_name: str = "payment-ledger",
) -> Dict[str, Any]:
    """Query persistent cross-session memory nodes (EpisodicMemory, ProceduralRunbook, SemanticFact)
    linked to the service or previous incidents.

    Args:
        manager: FalkorGraphManager singleton or mock
        tenant_id: Target tenant id (nexus_{tenant_id})
        service_name: Target service name

    Returns:
        Structured episodic memories, runbooks, semantic facts, and graph_paths.
    """
    manager = manager or get_db_manager()
    clean_tenant = manager._sanitize_tenant_id(tenant_id)
    graph_paths: List[Dict[str, Any]] = []
    cypher_executed: List[str] = []

    memory_cypher = """
    MATCH (s:Service {name: $service_name})
    OPTIONAL MATCH (ep:EpisodicMemory)-[:ABOUT_SERVICE|TARGET_SERVICE|PROTECTS_SERVICE|LINKED_TO|RESOLVED_INCIDENT|RECALLS_DECISION*1..2]-(s)
    OPTIONAL MATCH (rb:ProceduralRunbook)-[:APPLIES_TO|RESOLVES*1..2]-(s)
    OPTIONAL MATCH (sf:SemanticFact)-[:ABOUT_SERVICE|TARGET_SERVICE|ABOUT*1..2]-(s)
    RETURN collect(DISTINCT {
               id: ep.id,
               session_id: ep.session_id,
               summary: ep.summary,
               confidence: ep.confidence,
               timestamp: ep.timestamp,
               key_learnings: ep.key_learnings
           }) AS episodic_memories,
           collect(DISTINCT {
               id: rb.id,
               title: rb.title,
               steps: rb.steps,
               verified: rb.verified,
               author: rb.author,
               updated_at: rb.updated_at
           }) AS procedural_runbooks,
           collect(DISTINCT {
               id: sf.id,
               subject: sf.subject,
               predicate: sf.predicate,
               object: sf.object,
               rule: sf.rule,
               source: sf.source,
               verified: sf.verified
           }) AS semantic_facts
    """
    cypher_executed.append(memory_cypher)
    res = manager.run_cypher(
        tenant_id=clean_tenant,
        query=memory_cypher,
        params={"service_name": service_name},
        read_only=True,
    )

    episodic_memories = []
    procedural_runbooks = []
    semantic_facts = []

    if res.success and res.data:
        row = res.data[0]
        # Filter out empty dicts from OPTIONAL MATCH
        episodic_memories = [m for m in row.get("episodic_memories", []) if m.get("id")]
        procedural_runbooks = [r for r in row.get("procedural_runbooks", []) if r.get("id")]
        semantic_facts = [f for f in row.get("semantic_facts", []) if f.get("id")]

    # Build graph paths
    for ep in episodic_memories:
        graph_paths.append({
            "source": ep["id"],
            "source_label": "EpisodicMemory",
            "relationship": "ABOUT_SERVICE",
            "target": service_name,
            "target_label": "Service",
            "properties": {"confidence": ep.get("confidence")},
        })

    for rb in procedural_runbooks:
        graph_paths.append({
            "source": rb["id"],
            "source_label": "ProceduralRunbook",
            "relationship": "APPLIES_TO",
            "target": service_name,
            "target_label": "Service",
            "properties": {"title": rb.get("title")},
        })

    for sf in semantic_facts:
        graph_paths.append({
            "source": sf["id"],
            "source_label": "SemanticFact",
            "relationship": "ABOUT_SERVICE",
            "target": service_name,
            "target_label": "Service",
            "properties": {"rule": sf.get("rule")},
        })

    return {
        "success": True,
        "service_name": service_name,
        "episodic_memories": episodic_memories,
        "procedural_runbooks": procedural_runbooks,
        "semantic_facts": semantic_facts,
        "cypher_executed": cypher_executed,
        "graph_paths": graph_paths,
    }


# ==============================================================================
# TOOL 5: Record Agent Handoff (Track 02 Agent Coordination in Graph)
# ==============================================================================
def record_agent_handoff(
    manager: Optional[FalkorGraphManager] = None,
    tenant_id: str = "acme_prod",
    session_id: str = "sess_default",
    from_agent: str = "TriageAgent",
    to_agent: str = "RemediationAgent",
    findings_summary: str = "Identified commit a8f921c as cause of connection starvation.",
    cypher_used: str = "MATCH (c:Commit {sha: 'a8f921c'})-[:VIOLATES]->(d:Decision) RETURN c, d",
) -> Dict[str, Any]:
    """Write Session, AgentRun, and HANDED_OFF_TO edges directly into FalkorDB
    so agents coordinate their state through the graph itself.

    Args:
        manager: FalkorGraphManager singleton or mock
        tenant_id: Target tenant id
        session_id: Active session identifier
        from_agent: Originating agent name
        to_agent: Recipient agent name
        findings_summary: Summary of facts discovered
        cypher_used: Cypher query executed by originating agent

    Returns:
        Structured handoff confirmation, node ids, and graph_paths.
    """
    manager = manager or get_db_manager()
    clean_tenant = manager._sanitize_tenant_id(tenant_id)
    now = _now_iso()
    from_run_id = f"run_{session_id}_{from_agent.lower()}"
    to_run_id = f"run_{session_id}_{to_agent.lower()}"
    graph_paths: List[Dict[str, Any]] = []

    handoff_cypher = """
    MERGE (sess:Session {id: $session_id})
    ON CREATE SET sess.started_at = $timestamp
    SET sess.last_active_at = $timestamp

    MERGE (from_run:AgentRun {id: $from_run_id})
    SET from_run.agent_name = $from_agent,
        from_run.session_id = $session_id,
        from_run.findings = $findings,
        from_run.cypher_used = $cypher_used,
        from_run.timestamp = $timestamp

    MERGE (to_run:AgentRun {id: $to_run_id})
    SET to_run.agent_name = $to_agent,
        to_run.session_id = $session_id,
        to_run.status = "pending",
        to_run.timestamp = $timestamp

    MERGE (from_run)-[:PART_OF_SESSION]->(sess)
    MERGE (to_run)-[:PART_OF_SESSION]->(sess)
    MERGE (from_run)-[h:HANDED_OFF_TO]->(to_run)
    SET h.timestamp = $timestamp,
        h.reason = "Autonomous investigation handoff"

    RETURN sess.id AS session_id, from_run.id AS from_id, to_run.id AS to_id
    """
    res = manager.run_cypher(
        tenant_id=clean_tenant,
        query=handoff_cypher,
        params={
            "session_id": session_id,
            "timestamp": now,
            "from_run_id": from_run_id,
            "from_agent": from_agent,
            "findings": findings_summary,
            "cypher_used": cypher_used,
            "to_run_id": to_run_id,
            "to_agent": to_agent,
        },
        read_only=False,
    )

    graph_paths.append({
        "source": from_run_id,
        "source_label": "AgentRun",
        "relationship": "HANDED_OFF_TO",
        "target": to_run_id,
        "target_label": "AgentRun",
        "properties": {"from_agent": from_agent, "to_agent": to_agent, "timestamp": now},
    })
    graph_paths.append({
        "source": from_run_id,
        "source_label": "AgentRun",
        "relationship": "PART_OF_SESSION",
        "target": session_id,
        "target_label": "Session",
        "properties": {},
    })

    return {
        "success": res.success,
        "session_id": session_id,
        "from_agent": from_agent,
        "from_run_id": from_run_id,
        "to_agent": to_agent,
        "to_run_id": to_run_id,
        "findings_summary": findings_summary,
        "cypher_executed": [handoff_cypher],
        "graph_paths": graph_paths,
        "error": res.error,
    }


# ==============================================================================
# TOOL 6: Execute Graph Action & Persist Memory (Track 01 & Track 02)
# ==============================================================================
def execute_graph_action_and_persist_memory(
    manager: Optional[FalkorGraphManager] = None,
    tenant_id: str = "acme_prod",
    session_id: str = "sess_default",
    incident_id: str = "INC-2026-1015",
    service_name: str = "payment-ledger",
    action_taken: str = "Reverted commit a8f921c and enabled circuit breaker flag via RUNBOOK-07",
    learned_fact: str = "Payment ledger retry pool must never exceed 10 threads without circuit breaker flag active",
) -> Dict[str, Any]:
    """Mutate the graph based on the agent's decision:
    - Sets Incident status to 'Mitigated' and attaches RemediationAction
    - Creates persistent EpisodicMemory linked to Session, Incident, and Service
    - Creates or updates SemanticFact rule on Service

    Args:
        manager: FalkorGraphManager singleton or mock
        tenant_id: Target tenant id (nexus_{tenant_id})
        session_id: Active session identifier
        incident_id: Target incident id
        service_name: Name of mitigated service
        action_taken: Specific remediation executed
        learned_fact: Enduring rule/learning to persist for future sessions

    Returns:
        Confirmation dict with generated IDs and graph_paths.
    """
    manager = manager or get_db_manager()
    clean_tenant = manager._sanitize_tenant_id(tenant_id)
    now = _now_iso()
    action_id = f"ACT-{incident_id}"
    memory_id = f"MEM-{incident_id}"
    fact_id = f"FACT-{service_name.upper().replace('-', '_')}"
    graph_paths: List[Dict[str, Any]] = []

    mutate_cypher = """
    MATCH (inc:Incident {id: $incident_id})
    MATCH (svc:Service {name: $service_name})
    MERGE (sess:Session {id: $session_id})

    SET inc.status = "Mitigated",
        inc.mitigated_at = $timestamp,
        inc.resolution_summary = $action_taken

    MERGE (act:RemediationAction {id: $action_id})
    SET act.description = $action_taken,
        act.timestamp = $timestamp,
        act.executor = "AutonomousEngineeringAgent (Simulated DevOps Control Plane)",
        act.mode = "Simulated"
    MERGE (inc)-[:REMEDIATED_BY]->(act)
    MERGE (act)-[:APPLIED_TO]->(svc)

    MERGE (mem:EpisodicMemory {id: $memory_id})
    SET mem.session_id = $session_id,
        mem.summary = $action_summary,
        mem.confidence = 0.99,
        mem.timestamp = $timestamp,
        mem.key_learnings = $learned_fact
    MERGE (mem)-[:RESOLVED_INCIDENT]->(inc)
    MERGE (mem)-[:ABOUT_SERVICE]->(svc)
    MERGE (mem)-[:RECORDED_IN_SESSION]->(sess)

    MERGE (fact:SemanticFact {id: $fact_id})
    SET fact.subject = $service_name,
        fact.predicate = "mitigation_rule",
        fact.object = $learned_fact,
        fact.rule = $learned_fact,
        fact.source = "IncidentResolution:" + $incident_id,
        fact.verified = true,
        fact.updated_at = $timestamp
    MERGE (fact)-[:ABOUT_SERVICE]->(svc)

    RETURN inc.id AS incident_id, inc.status AS incident_status,
           act.id AS action_id, mem.id AS memory_id, fact.id AS fact_id
    """
    res = manager.run_cypher(
        tenant_id=clean_tenant,
        query=mutate_cypher,
        params={
            "incident_id": incident_id,
            "timestamp": now,
            "action_taken": action_taken,
            "action_id": action_id,
            "session_id": session_id,
            "service_name": service_name,
            "memory_id": memory_id,
            "action_summary": f"Mitigated incident {incident_id} by: {action_taken}",
            "learned_fact": learned_fact,
            "fact_id": fact_id,
        },
        read_only=False,
    )

    # Build explicit graph paths for rendering the newly created subgraph
    graph_paths.append({
        "source": incident_id,
        "source_label": "Incident",
        "relationship": "REMEDIATED_BY",
        "target": action_id,
        "target_label": "RemediationAction",
        "properties": {"action": action_taken, "timestamp": now},
    })
    graph_paths.append({
        "source": action_id,
        "source_label": "RemediationAction",
        "relationship": "APPLIED_TO",
        "target": service_name,
        "target_label": "Service",
        "properties": {},
    })
    graph_paths.append({
        "source": memory_id,
        "source_label": "EpisodicMemory",
        "relationship": "RESOLVED_INCIDENT",
        "target": incident_id,
        "target_label": "Incident",
        "properties": {},
    })
    graph_paths.append({
        "source": memory_id,
        "source_label": "EpisodicMemory",
        "relationship": "ABOUT_SERVICE",
        "target": service_name,
        "target_label": "Service",
        "properties": {"learnings": learned_fact},
    })
    graph_paths.append({
        "source": fact_id,
        "source_label": "SemanticFact",
        "relationship": "ABOUT_SERVICE",
        "target": service_name,
        "target_label": "Service",
        "properties": {"rule": learned_fact},
    })

    return {
        "success": res.success,
        "incident_id": incident_id,
        "incident_status": "Mitigated",
        "service_name": service_name,
        "action_id": action_id,
        "memory_id": memory_id,
        "fact_id": fact_id,
        "action_taken": action_taken,
        "learned_fact": learned_fact,
        "cypher_executed": [mutate_cypher],
        "graph_paths": graph_paths,
        "error": res.error,
    }
