"""NexusGraph Seed Company Brain Module.

Idempotently populates FalkorDB Cloud with a realistic, highly interconnected
knowledge graph spanning all 3 hackathon tracks:
- Track 01 (Agents That Act on Connected Data): Microservice topology, multi-hop dependencies
- Track 02 (Agent Memory & Coordination): Multi-tenant isolation (nexus_{tenant_id}), Episodic & Semantic memory, Procedural runbooks
- Track 03 (Company Brain): ADRs/Decisions, Commits, PRs, Tickets, Slack discussions, Violations, Incidents
"""

import sys
import time
import logging
import argparse
from typing import Any, Dict, List, Optional
from src.db.falkor_client import FalkorGraphManager, get_db_manager

logger = logging.getLogger("nexusgraph.seeder")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def create_schema_indexes(manager: FalkorGraphManager, tenant_id: str) -> None:
    """Create indexes on key node labels to optimize Cypher lookups and traversals."""
    indexes = [
        "CREATE INDEX FOR (s:Service) ON (s.name)",
        "CREATE INDEX FOR (e:Engineer) ON (e.name)",
        "CREATE INDEX FOR (t:Team) ON (t.name)",
        "CREATE INDEX FOR (d:Decision) ON (d.id)",
        "CREATE INDEX FOR (c:Commit) ON (c.sha)",
        "CREATE INDEX FOR (i:Incident) ON (i.id)",
        "CREATE INDEX FOR (pr:PullRequest) ON (pr.id)",
        "CREATE INDEX FOR (tk:Ticket) ON (tk.id)",
        "CREATE INDEX FOR (st:SlackThread) ON (st.id)",
        "CREATE INDEX FOR (rb:ProceduralRunbook) ON (rb.id)",
        "CREATE INDEX FOR (mem:EpisodicMemory) ON (mem.id)",
        "CREATE INDEX FOR (fact:SemanticFact) ON (fact.id)",
    ]
    for idx_query in indexes:
        try:
            manager.run_cypher(tenant_id=tenant_id, query=idx_query)
        except Exception as e:
            logger.debug("Index creation notice: %s (%s)", idx_query, e)


def seed_tenant_graph(
    manager: Optional[FalkorGraphManager] = None,
    tenant_id: str = "acme_prod",
    reset: bool = True,
) -> Dict[str, Any]:
    """Seed the tenant graph with an interconnected company brain dataset.

    Args:
        manager: Instance of FalkorGraphManager. If None, default singleton is used.
        tenant_id: Tenant identifier (graph name: nexus_{tenant_id}).
        reset: If True, executes MATCH (n) DETACH DELETE n prior to seeding.

    Returns:
        Summary dict containing counts of created entities and execution stats.
    """
    if manager is None:
        manager = get_db_manager()

    start_time = time.perf_counter()
    clean_tenant = manager._sanitize_tenant_id(tenant_id)
    graph_name = f"nexus_{clean_tenant}"
    logger.info("Starting seed process for tenant '%s' (graph: %s, reset=%s)",
                clean_tenant, graph_name, reset)

    # 1. Reset graph if requested
    if reset:
        logger.info("Resetting graph '%s'...", graph_name)
        reset_res = manager.run_cypher(
            tenant_id=clean_tenant,
            query="MATCH (n) DETACH DELETE n",
        )
        if not reset_res.success and "placeholder" in (reset_res.error or ""):
            return {
                "success": False,
                "error": reset_res.error,
                "tenant_id": clean_tenant,
                "graph_name": graph_name,
            }

    # 2. Setup indexes
    create_schema_indexes(manager, clean_tenant)

    # 3. Track 03: Seed Teams
    teams_query = """
    UNWIND $teams AS t
    MERGE (team:Team {name: t.name})
    SET team.channel = t.channel,
        team.description = t.description,
        team.lead = t.lead
    RETURN count(team) AS count
    """
    teams_data = [
        {
            "name": "Payments Core",
            "channel": "#payments-eng",
            "description": "Processes financial transactions and maintains the resilient double-entry ledger",
            "lead": "Priya Nair",
        },
        {
            "name": "Identity & Auth",
            "channel": "#auth-sec",
            "description": "Manages session tokens, OAuth2, cryptographic signatures & access tokens",
            "lead": "Marcus Vance",
        },
        {
            "name": "Checkout Experience",
            "channel": "#checkout-ui",
            "description": "Customer checkout workflows, cart orchestration & checkout frontend",
            "lead": "Sarah Lin",
        },
        {
            "name": "SRE Platform",
            "channel": "#sre-oncall",
            "description": "Cloud infrastructure, latency telemetry, incident management & operational runbooks",
            "lead": "Devon Brooks",
        },
    ]
    manager.run_cypher(tenant_id=clean_tenant, query=teams_query, params={"teams": teams_data})

    # 4. Track 03: Seed Engineers & Team Memberships
    engineers_query = """
    UNWIND $engineers AS eng
    MERGE (e:Engineer {name: eng.name})
    SET e.role = eng.role,
        e.email = eng.email,
        e.pagerduty = eng.pagerduty,
        e.tz = eng.tz
    WITH e, eng
    MATCH (t:Team {name: eng.team})
    MERGE (e)-[:MEMBER_OF]->(t)
    RETURN count(e) AS count
    """
    engineers_data = [
        {
            "name": "Priya Nair",
            "role": "Staff Engineer",
            "team": "Payments Core",
            "email": "priya.nair@acme.corp",
            "pagerduty": "PD-PNAIR",
            "tz": "America/New_York",
        },
        {
            "name": "Marcus Vance",
            "role": "Principal Architect",
            "team": "Identity & Auth",
            "email": "marcus.vance@acme.corp",
            "pagerduty": "PD-MVANCE",
            "tz": "America/Los_Angeles",
        },
        {
            "name": "Elena Rostova",
            "role": "Senior Backend Engineer",
            "team": "Payments Core",
            "email": "elena.rostova@acme.corp",
            "pagerduty": "PD-EROSTOVA",
            "tz": "Europe/London",
        },
        {
            "name": "Devon Brooks",
            "role": "SRE Lead",
            "team": "SRE Platform",
            "email": "devon.brooks@acme.corp",
            "pagerduty": "PD-DBROOKS",
            "tz": "America/Chicago",
        },
    ]
    manager.run_cypher(tenant_id=clean_tenant, query=engineers_query, params={"engineers": engineers_data})

    # 5. Track 01: Seed 7 Interconnected Microservices
    services_query = """
    UNWIND $services AS s
    MERGE (svc:Service {name: s.name})
    SET svc.tier = s.tier,
        svc.language = s.language,
        svc.framework = s.framework,
        svc.port = s.port,
        svc.version = s.version,
        svc.repo = s.repo
    RETURN count(svc) AS count
    """
    services_data = [
        {
            "name": "api-gateway",
            "tier": 1,
            "language": "Go",
            "framework": "Envoy/Custom",
            "port": 443,
            "version": "v3.4.1",
            "repo": "infra/api-gateway",
        },
        {
            "name": "auth-token-service",
            "tier": 1,
            "language": "Rust",
            "framework": "Actix",
            "port": 8081,
            "version": "v2.8.0",
            "repo": "security/auth-token-service",
        },
        {
            "name": "checkout-orchestrator",
            "tier": 1,
            "language": "TypeScript/Node",
            "framework": "Fastify",
            "port": 8080,
            "version": "v4.1.2",
            "repo": "checkout/orchestrator",
        },
        {
            "name": "payment-ledger",
            "tier": 1,
            "language": "Kotlin",
            "framework": "Spring Boot 3",
            "port": 8443,
            "version": "v5.2.0",
            "repo": "payments-core/payment-ledger",
        },
        {
            "name": "fraud-scoring-engine",
            "tier": 2,
            "language": "Python",
            "framework": "FastAPI",
            "port": 8090,
            "version": "v1.9.5",
            "repo": "risk/fraud-scoring",
        },
        {
            "name": "redis-session-cache",
            "tier": 1,
            "language": "C",
            "framework": "Redis 7.2",
            "port": 6379,
            "version": "v7.2.4",
            "repo": "infra/redis-cluster",
        },
        {
            "name": "webhook-dispatcher",
            "tier": 3,
            "language": "Go",
            "framework": "Fiber",
            "port": 8085,
            "version": "v1.5.0",
            "repo": "integrations/webhook-dispatcher",
        },
    ]
    manager.run_cypher(tenant_id=clean_tenant, query=services_query, params={"services": services_data})

    # 6. Team Ownership & Engineer Expertise
    ownership_query = """
    UNWIND $ownership AS o
    MATCH (t:Team {name: o.team})
    MATCH (s:Service {name: o.service})
    MERGE (t)-[:OWNS]->(s)
    """
    ownership_data = [
        {"team": "Checkout Experience", "service": "api-gateway"},
        {"team": "Identity & Auth", "service": "auth-token-service"},
        {"team": "Checkout Experience", "service": "checkout-orchestrator"},
        {"team": "Payments Core", "service": "payment-ledger"},
        {"team": "Payments Core", "service": "fraud-scoring-engine"},
        {"team": "Identity & Auth", "service": "redis-session-cache"},
        {"team": "SRE Platform", "service": "webhook-dispatcher"},
    ]
    manager.run_cypher(tenant_id=clean_tenant, query=ownership_query, params={"ownership": ownership_data})

    expertise_query = """
    UNWIND $expertise AS exp
    MATCH (e:Engineer {name: exp.engineer})
    MATCH (s:Service {name: exp.service})
    MERGE (e)-[r:EXPERT_IN]->(s)
    SET r.confidence = exp.confidence,
        r.domain = exp.domain
    """
    expertise_data = [
        {"engineer": "Priya Nair", "service": "payment-ledger", "confidence": 0.98, "domain": "Distributed consensus, Idempotency, Ledger consistency"},
        {"engineer": "Priya Nair", "service": "checkout-orchestrator", "confidence": 0.92, "domain": "End-to-end transaction lifecycle"},
        {"engineer": "Marcus Vance", "service": "auth-token-service", "confidence": 0.99, "domain": "OAuth2, JWT revocation & token caching"},
        {"engineer": "Marcus Vance", "service": "redis-session-cache", "confidence": 0.95, "domain": "Redis cluster clustering & replication topology"},
        {"engineer": "Elena Rostova", "service": "payment-ledger", "confidence": 0.94, "domain": "Batch transaction execution & thread pool retries"},
        {"engineer": "Devon Brooks", "service": "api-gateway", "confidence": 0.97, "domain": "Edge routing, cascading timeout mitigation"},
        {"engineer": "Devon Brooks", "service": "payment-ledger", "confidence": 0.93, "domain": "Observability, p99 latency alarms & runbooks"},
    ]
    manager.run_cypher(tenant_id=clean_tenant, query=expertise_query, params={"expertise": expertise_data})

    # 7. Track 01: Microservice Dependency Topology
    # Designed so payment-ledger and auth-token-service have high inbound dependency centrality
    dependencies_query = """
    UNWIND $deps AS d
    MATCH (src:Service {name: d.from})
    MATCH (dest:Service {name: d.to})
    MERGE (src)-[r:DEPENDS_ON]->(dest)
    SET r.criticality = d.criticality,
        r.timeout_ms = d.timeout_ms,
        r.protocol = d.protocol
    """
    dependencies_data = [
        {"from": "api-gateway", "to": "checkout-orchestrator", "criticality": "high", "timeout_ms": 2500, "protocol": "HTTP/2"},
        {"from": "api-gateway", "to": "auth-token-service", "criticality": "critical", "timeout_ms": 800, "protocol": "gRPC"},
        {"from": "checkout-orchestrator", "to": "auth-token-service", "criticality": "critical", "timeout_ms": 1000, "protocol": "gRPC"},
        {"from": "checkout-orchestrator", "to": "fraud-scoring-engine", "criticality": "high", "timeout_ms": 1500, "protocol": "HTTP/REST"},
        {"from": "checkout-orchestrator", "to": "payment-ledger", "criticality": "critical", "timeout_ms": 3000, "protocol": "gRPC"},
        {"from": "checkout-orchestrator", "to": "redis-session-cache", "criticality": "medium", "timeout_ms": 500, "protocol": "RESP"},
        {"from": "fraud-scoring-engine", "to": "redis-session-cache", "criticality": "medium", "timeout_ms": 400, "protocol": "RESP"},
        {"from": "fraud-scoring-engine", "to": "payment-ledger", "criticality": "high", "timeout_ms": 2000, "protocol": "gRPC"},
        {"from": "payment-ledger", "to": "auth-token-service", "criticality": "critical", "timeout_ms": 600, "protocol": "gRPC"},
        {"from": "payment-ledger", "to": "redis-session-cache", "criticality": "high", "timeout_ms": 400, "protocol": "RESP"},
        {"from": "payment-ledger", "to": "webhook-dispatcher", "criticality": "low", "timeout_ms": 5000, "protocol": "AMQP"},
        {"from": "webhook-dispatcher", "to": "auth-token-service", "criticality": "critical", "timeout_ms": 1000, "protocol": "gRPC"},
    ]
    manager.run_cypher(tenant_id=clean_tenant, query=dependencies_query, params={"deps": dependencies_data})

    # 8. Track 03: Architectural Decisions (ADR-014 Superseded by ADR-029)
    decisions_query = """
    UNWIND $decisions AS dec
    MERGE (d:Decision {id: dec.id})
    SET d.title = dec.title,
        d.status = dec.status,
        d.date = dec.date,
        d.rationale = dec.rationale,
        d.author = dec.author
    """
    decisions_data = [
        {
            "id": "ADR-014",
            "title": "Use Synchronous gRPC Retries on Payment Ledger",
            "status": "Superseded",
            "date": "2026-06-10",
            "author": "Elena Rostova",
            "rationale": "Initial low-volume deployment relied on simple synchronous retries up to 3 times per batch transaction.",
        },
        {
            "id": "ADR-029",
            "title": "Enforce Circuit Breaker & Idempotency Keys on Ledger Writes",
            "status": "Active",
            "date": "2026-10-12",
            "author": "Marcus Vance",
            "rationale": "Prevent cascading retry storms during token cache spikes. Synchronous retries without circuit breakers are strictly forbidden; requests must fail fast or queue to dead-letter storage.",
        },
    ]
    manager.run_cypher(tenant_id=clean_tenant, query=decisions_query, params={"decisions": decisions_data})

    # Decision Lineage & Governance Edges
    decision_links_query = """
    MATCH (old:Decision {id: "ADR-014"})
    MATCH (new:Decision {id: "ADR-029"})
    MATCH (ledger:Service {name: "payment-ledger"})
    MATCH (auth:Service {name: "auth-token-service"})
    MATCH (marcus:Engineer {name: "Marcus Vance"})
    MATCH (priya:Engineer {name: "Priya Nair"})
    MERGE (new)-[:SUPERSEDES]->(old)
    MERGE (new)-[:GOVERNS]->(ledger)
    MERGE (new)-[:PROTECTS]->(auth)
    MERGE (marcus)-[:AUTHORED_DECISION]->(new)
    MERGE (priya)-[:REVIEWED_DECISION {approved: true}]->(new)
    """
    manager.run_cypher(tenant_id=clean_tenant, query=decision_links_query)

    # 9. Track 03: Ticket, Pull Request, Commit & Violation
    code_history_query = """
    // 1. Ticket
    MERGE (tk:Ticket {id: "JIRA-1904"})
    SET tk.title = "Increase ledger throughput for flash sale",
        tk.status = "Closed",
        tk.priority = "P1",
        tk.description = "Optimize ledger batch writing for upcoming flash sale by expanding thread pool capacity."

    // 2. Pull Request
    MERGE (pr:PullRequest {id: "PR-482"})
    SET pr.title = "Scale batch retry pool for flash sale",
        pr.status = "Merged",
        pr.merged_at = "2026-10-15T14:45:00Z",
        pr.repo = "payments-core/payment-ledger"
    MERGE (pr)-[:ADDRESSES]->(tk)

    // 3. Commit
    MERGE (c:Commit {sha: "a8f921c"})
    SET c.message = "feat(ledger): bump batch retry pool to 50 threads",
        c.timestamp = "2026-10-15T14:20:00Z",
        c.files_changed = "src/main/resources/application.yml,src/main/java/ledger/RetryManager.java",
        c.additions = 45,
        c.deletions = 12

    // 4. Edges
    WITH tk, pr, c
    MATCH (elena:Engineer {name: "Elena Rostova"})
    MATCH (ledger:Service {name: "payment-ledger"})
    MATCH (adr029:Decision {id: "ADR-029"})
    MERGE (elena)-[:AUTHORED_COMMIT]->(c)
    MERGE (c)-[:IN_PR]->(pr)
    MERGE (c)-[:MODIFIES]->(ledger)
    MERGE (c)-[:VIOLATES {
        reason: "Re-enabled synchronous thread pool retries (50 threads) without circuit breaker flag, violating ADR-029"
    }]->(adr029)
    """
    manager.run_cypher(tenant_id=clean_tenant, query=code_history_query)

    # 10. Track 03: Slack Discussion with Warning Quote
    slack_query = """
    MERGE (st:SlackThread {id: "SLACK-991"})
    SET st.channel = "#payments-eng",
        st.thread_ts = "1729002150.001",
        st.quote = "Priya warned that raising retry threads without the circuit breaker flag will exhaust auth-token-service connections during traffic bursts.",
        st.timestamp = "2026-10-15T14:35:00Z",
        st.replies_count = 8
    WITH st
    MATCH (priya:Engineer {name: "Priya Nair"})
    MATCH (team:Team {name: "Payments Core"})
    MATCH (c:Commit {sha: "a8f921c"})
    MATCH (adr029:Decision {id: "ADR-029"})
    MERGE (priya)-[:POSTED_IN]->(st)
    MERGE (st)-[:IN_CHANNEL]->(team)
    MERGE (st)-[:WARNS_ABOUT]->(c)
    MERGE (st)-[:REFERENCES]->(adr029)
    """
    manager.run_cypher(tenant_id=clean_tenant, query=slack_query)

    # 11. Track 01 & Track 02: Active Incident & Runbook
    incident_runbook_query = """
    // Active Incident
    MERGE (inc:Incident {id: "INC-2026-1015"})
    SET inc.title = "Cascading 504 Timeouts on Checkout & Payment Ledger",
        inc.severity = "SEV-1",
        inc.status = "Open",
        inc.started_at = "2026-10-15T18:10:00Z",
        inc.commander = "Devon Brooks",
        inc.current_hypothesis = "Ledger retry pool saturation cascading into auth-token-service connection starvation."

    // Procedural Runbook
    MERGE (rb:ProceduralRunbook {id: "RUNBOOK-07"})
    SET rb.title = "Rollback Retry Pool & Enable Circuit Breaker Flag",
        rb.service = "payment-ledger",
        rb.steps = [
            "1. Revert commit a8f921c or apply hotfix patch PR-483",
            "2. Set LEDGER_CIRCUIT_BREAKER_ENABLED=true in configmap",
            "3. Restart payment-ledger pods gracefully with rollout restart",
            "4. Verify auth-token-service p99 latency drops below 25ms and 504s recover to 0%"
        ],
        rb.verified = true,
        rb.author = "Devon Brooks",
        rb.updated_at = "2026-10-12T17:00:00Z"

    WITH inc, rb
    MATCH (checkout:Service {name: "checkout-orchestrator"})
    MATCH (ledger:Service {name: "payment-ledger"})
    MATCH (c:Commit {sha: "a8f921c"})
    MATCH (devon:Engineer {name: "Devon Brooks"})
    MERGE (inc)-[:AFFECTS {symptom: "504 Gateway Timeout on checkout API (error rate 34.2%)"}]->(checkout)
    MERGE (inc)-[:AFFECTS {symptom: "Thread pool exhaustion, CPU 98%, gRPC queue depth > 400"}]->(ledger)
    MERGE (inc)-[:TRIGGERED_BY]->(c)
    MERGE (devon)-[:COMMANDS_INCIDENT]->(inc)
    MERGE (rb)-[:RESOLVES]->(inc)
    MERGE (rb)-[:APPLIES_TO]->(ledger)
    """
    manager.run_cypher(tenant_id=clean_tenant, query=incident_runbook_query)

    # 12. Track 02: Initial Episodic Memory & Semantic Facts (Cross-Session Recall)
    memories_query = """
    // Episodic Memory from prior session
    MERGE (mem:EpisodicMemory {id: "MEM-SESSION-001"})
    SET mem.session_id = "sess_pre_incident_01",
        mem.summary = "Architect review on ADR-029: Priya Nair and Marcus Vance established that synchronous retries on ledger cause auth-token-service cascading saturation. Circuit breaker flag is mandatory.",
        mem.confidence = 0.98,
        mem.timestamp = "2026-10-12T16:00:00Z",
        mem.key_learnings = "Never increase retry threads without enabling circuit breaker and token cache fallback."

    // Semantic Fact
    MERGE (fact:SemanticFact {id: "FACT-042"})
    SET fact.subject = "payment-ledger",
        fact.predicate = "requires_circuit_breaker_for",
        fact.object = "auth-token-service",
        fact.source = "ADR-029",
        fact.verified = true,
        fact.updated_at = "2026-10-12T16:30:00Z",
        fact.rule = "Payment ledger write retries MUST have circuit breaker protection to avoid exhausting auth-token-service connection pool."

    WITH mem, fact
    MATCH (adr029:Decision {id: "ADR-029"})
    MATCH (adr014:Decision {id: "ADR-014"})
    MATCH (priya:Engineer {name: "Priya Nair"})
    MATCH (marcus:Engineer {name: "Marcus Vance"})
    MATCH (ledger:Service {name: "payment-ledger"})
    MATCH (auth:Service {name: "auth-token-service"})
    MERGE (mem)-[:RECALLS_DECISION]->(adr029)
    MERGE (mem)-[:INVOLVED]->(priya)
    MERGE (mem)-[:INVOLVED]->(marcus)
    MERGE (mem)-[:ABOUT_SERVICE]->(ledger)
    MERGE (mem)-[:TARGET_SERVICE]->(auth)
    MERGE (fact)-[:ABOUT_SERVICE]->(ledger)
    MERGE (fact)-[:TARGET_SERVICE]->(auth)
    MERGE (adr014)-[:GOVERNS]->(ledger)
    """
    manager.run_cypher(tenant_id=clean_tenant, query=memories_query)

    # 13. Query counts to compile summary
    summary_query = """
    MATCH (n)
    WITH count(n) AS total_nodes
    OPTIONAL MATCH ()-[r]->()
    WITH total_nodes, count(r) AS total_edges
    RETURN total_nodes, total_edges
    """
    count_res = manager.run_cypher(tenant_id=clean_tenant, query=summary_query, read_only=True)
    total_nodes = count_res.data[0]["total_nodes"] if count_res.data else 0
    total_edges = count_res.data[0]["total_edges"] if count_res.data else 0

    # Detailed label breakdown
    labels_query = """
    MATCH (n)
    RETURN labels(n) AS labels, count(n) AS count
    """
    labels_res = manager.run_cypher(tenant_id=clean_tenant, query=labels_query, read_only=True)
    label_breakdown = {}
    for row in labels_res.data:
        lbls = row.get("labels") or []
        count = row.get("count", 0)
        for l in lbls:
            label_breakdown[l] = label_breakdown.get(l, 0) + count

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info("Successfully seeded tenant '%s': %s nodes, %s edges in %s ms",
                clean_tenant, total_nodes, total_edges, elapsed_ms)

    return {
        "success": True,
        "tenant_id": clean_tenant,
        "graph_name": graph_name,
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "label_counts": label_breakdown,
        "elapsed_ms": elapsed_ms,
    }


def main():
    """CLI entrypoint for seeding FalkorDB Cloud."""
    parser = argparse.ArgumentParser(description="Seed FalkorDB with NexusGraph Company Brain data.")
    parser.add_argument("--host", help="FalkorDB host")
    parser.add_argument("--port", type=int, help="FalkorDB port")
    parser.add_argument("--password", help="FalkorDB password")
    parser.add_argument("--username", help="FalkorDB username")
    parser.add_argument("--ssl", action="store_true", help="Enable SSL")
    parser.add_argument("--tenant", default="acme_prod", help="Tenant ID (default: acme_prod)")
    parser.add_argument("--no-reset", action="store_true", help="Do not wipe existing graph before seeding")
    args = parser.parse_args()

    overrides = {}
    if args.host:
        overrides["host"] = args.host
    if args.port:
        overrides["port"] = args.port
    if args.password:
        overrides["password"] = args.password
    if args.username:
        overrides["username"] = args.username
    if args.ssl:
        overrides["ssl"] = True

    manager = get_db_manager(overrides=overrides if overrides else None)

    print("=" * 60)
    print(" NexusGraph: Seeding Company Brain into FalkorDB")
    print("=" * 60)
    print(f"Tenant Graph: nexus_{args.tenant}")
    print(f"Target Host:  {manager.host}:{manager.port} (SSL={manager.ssl})")
    print(f"Reset Graph:  {not args.no_reset}")
    print("-" * 60)

    # Check connection
    conn_status = manager.check_connection()
    if not conn_status["connected"]:
        print(f"\n[WARNING] Could not connect to FalkorDB Cloud: {conn_status['error']}")
        print("\nTo connect to your FalkorDB Cloud instance:")
        print("1. Update your .env file with your FalkorDB Cloud credentials:")
        print("   FALKORDB_HOST=your-instance.falkordb.cloud")
        print("   FALKORDB_PORT=6379")
        print("   FALKORDB_PASSWORD=your-password")
        print("\n2. Or provide CLI flags directly:")
        print("   python -m src.db.seed_company_brain --host <host> --port <port> --password <pass>")
        sys.exit(1)

    result = seed_tenant_graph(
        manager=manager,
        tenant_id=args.tenant,
        reset=not args.no_reset,
    )

    if result.get("success"):
        print("\n[SUCCESS] Seeding Completed Successfully!")
        print(f"Total Nodes: {result['total_nodes']}")
        print(f"Total Edges: {result['total_edges']}")
        print(f"Latency:     {result['elapsed_ms']} ms")
        print("\nEntity Counts by Label:")
        for label, count in sorted(result.get("label_counts", {}).items()):
            print(f"  - {label:20s}: {count}")
    else:
        print(f"\n[ERROR] Seeding Failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
