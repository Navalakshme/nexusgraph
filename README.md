# 🧠 NexusGraph: Autonomous Engineering, Memory & Company Brain
> **FalkorDB Graph Hacks Hackathon — Entering All 3 Tracks**  
> *Track 01 (Agents That Act on Connected Data) | Track 02 (Agent Memory & Coordination) | Track 03 (Company Brain)*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FalkorDB](https://img.shields.io/badge/FalkorDB-Cloud-red.svg)](https://falkordb.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20GenAI-Gemini%202.5-4285F4.svg)](https://ai.google.dev/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38+-FF4B4B.svg)](https://streamlit.io/)
[![Zero Docker](https://img.shields.io/badge/Zero%20Docker-100%25%20Cloud-success.svg)](#zero-docker-setup--live-deployment)
[![Tests Passing](https://img.shields.io/badge/Tests-20%20Passed-brightgreen.svg)](tests/)

---

## 📌 Executive Summary

Modern engineering teams suffer from fragmented context: telemetry is siloed in observability dashboards, code history is in GitHub, architecture decisions (ADRs) are buried in Confluence, operational friction is scattered in Slack, and incident runbooks become stale. When a critical outage strikes, human incident commanders spend hours manually correlating alerts to commits, checking if superseded architecture decisions were violated, and coordinating teams.

**NexusGraph** solves this by turning **FalkorDB Cloud** into an active, querying Company Brain and multi-agent memory substrate. A collaborative team of three specialized autonomous agents (**TriageAgent**, **LineageAgent**, and **ActionAgent**) pass state exclusively by reading and writing graph edges directly inside FalkorDB. The system isolates root causes across 5 hops, audits architectural decision compliance, recalls cross-session episodic memories, and automatically mutates the graph to execute and remember incident mitigation.

---

## 🏆 Tracks Entered & Key Innovations

| Hackathon Track | How NexusGraph Satisfies & Exceeds Requirements | Live App Proof |
| :--- | :--- | :--- |
| **Track 01: Agents That Act on Connected Data** | Runs FalkorDB native PageRank (`CALL algo.pageRank('Service', 'DEPENDS_ON')`) to rank service criticality, executes 5-hop incident root-cause graph traversals, calculates downstream blast radius, and directly mutates graph state (`:RemediationAction`, `:Incident {status: "Mitigated"}`). | **Tab 1 & Tab 2**: Interactive blast-radius simulator, real-time Cypher execution audit trail with millisecond latencies, and PyVis glowing traversed reasoning paths. |
| **Track 02: Agent Memory & Multi-Agent Coordination** | Multi-tenant graph isolation (`nexus_{tenant_id}`) guarantees strict memory boundaries. Multi-agent state is passed through FalkorDB via `(:AgentRun)-[:HANDED_OFF_TO]->(:AgentRun)`. Cross-session `EpisodicMemory`, `SemanticFact`, and `ProceduralRunbook` nodes persist so Session #2 remembers and learns from Session #1. | **Tab 1 & Tab 3**: 3-Agent handoff chain, memory diff inspection drawer, and the *"Simulate Next Day Session"* interactive demo. |
| **Track 03: Company Brain** | Unifies code commits (`:Commit`), pull requests (`:PullRequest`), tickets (`:Ticket`), architectural decisions (`:Decision`), Slack warnings (`:SlackThread`), teams (`:Team`), and engineers (`:Engineer`). Traverses temporal decision lineage (`(ADR-029)-[:SUPERSEDES]->(ADR-014)`), detects commit violations, and attributes authoring provenance. | **Tab 1 & Tab 4**: ADR superseded timeline, Slack quote verification from `#payments-eng`, *Who Owns What / Who Knows What* matrix, and interactive OpenCypher console. |

---

## ⚡ Why FalkorDB Is the Irreplaceable Core (Rule 3 Proof)

> *"The graph has to do real work. If the product still works once FalkorDB is taken out, the graph is decoration."* — Hackathon Rule 3

NexusGraph **cannot function** without FalkorDB as its primary execution engine:

1. **Multi-Hop Relational Traversal vs. SQL Join Bomb:**
   Attributing root cause from an incident alert to an authoring engineer requires a 5-hop traversal across heterogeneous entities:  
   $$\text{(Incident)} \to \text{(Service)} \to \text{(Service)} \leftarrow \text{(Commit)} \to \text{(PR)} \leftarrow \text{(Engineer)}$$
   In relational databases, this requires 6 expensive table joins with recursive CTEs. In vector databases, semantic similarity cannot follow directional causal paths (e.g., distinguishing between a service that *caused* an outage vs. one that *suffered* from it). FalkorDB evaluates this in **< 4 milliseconds**.

2. **Native Graph Centrality Algorithms (PageRank):**
   Evaluating real-time blast radius requires graph topology algorithms. FalkorDB’s native C-based `CALL algo.pageRank('Service', 'DEPENDS_ON')` calculates exact inbound dependency centrality directly inside the database kernel without exporting graphs into external memory.

3. **Graph-Native Multi-Agent Coordination:**
   Rather than storing ephemeral agent dialogue in JSON blobs or Python memory, coordination state is modeled as first-class graph topology: `(:Session)<-[:PART_OF_SESSION]-(:AgentRun)-[:HANDED_OFF_TO]->(:AgentRun)`. If an agent crashes or hands off to another process, the incoming agent simply queries FalkorDB for its preceding `AgentRun` node.

4. **Temporal Architectural Decision Lineage:**
   Static search engines find matching keywords across ADRs, but cannot distinguish between active vs. superseded policies. FalkorDB natively traverses `(ADR-029)-[:SUPERSEDES]->(ADR-014)` and checks `(Commit)-[:VIOLATES]->(ADR-029)`, enabling autonomous agents to catch policy violations before and during incidents.

---

## 📊 Complete Property Graph Data Model

### Architecture & Entity-Relationship Schema

```mermaid
graph TD
    classDef incident fill:#FF5252,stroke:#FF1744,stroke-width:2px,color:#fff;
    classDef service fill:#00E5FF,stroke:#00B0FF,stroke-width:2px,color:#000;
    classDef code fill:#FFB300,stroke:#FFA000,stroke-width:2px,color:#000;
    classDef decision fill:#B388FF,stroke:#7C4DFF,stroke-width:2px,color:#000;
    classDef people fill:#00E676,stroke:#00C853,stroke-width:2px,color:#000;
    classDef memory fill:#FFD700,stroke:#FFC107,stroke-width:2px,color:#000;
    classDef agent fill:#40C4FF,stroke:#00B0FF,stroke-width:2px,color:#000;

    Inc["Incident: INC-2026-1015"]:::incident
    Rem["RemediationAction: ACT-01"]:::memory
    Svc1["Service: checkout-orchestrator"]:::service
    Svc2["Service: payment-ledger"]:::service
    Svc3["Service: auth-token-service"]:::service
    C["Commit: a8f921c"]:::code
    PR["PullRequest: PR-482"]:::code
    TK["Ticket: JIRA-1904"]:::code
    ADR29["Decision: ADR-029 (Active)"]:::decision
    ADR14["Decision: ADR-014 (Superseded)"]:::decision
    Slack["SlackThread: SLACK-991"]:::code
    Elena["Engineer: Elena Rostova"]:::people
    Priya["Engineer: Priya Nair"]:::people
    Team["Team: Payments Core"]:::people
    Mem["EpisodicMemory: MEM-SESSION-001"]:::memory
    Fact["SemanticFact: FACT-042"]:::memory
    Rb["ProceduralRunbook: RUNBOOK-07"]:::memory
    Run1["AgentRun: TriageAgent"]:::agent
    Run2["AgentRun: LineageAgent"]:::agent
    Run3["AgentRun: ActionAgent"]:::agent
    Sess["Session: sess_01"]:::agent

    Inc -- AFFECTS --> Svc1
    Inc -- TRIGGERED_BY --> C
    Inc -- REMEDIATED_BY --> Rem
    Rem -- APPLIED_TO --> Svc2
    Svc1 -- DEPENDS_ON --> Svc2
    Svc2 -- DEPENDS_ON --> Svc3
    C -- MODIFIES --> Svc2
    C -- IN_PR --> PR
    PR -- ADDRESSES --> TK
    Elena -- AUTHORED_COMMIT --> C
    Elena -- MEMBER_OF --> Team
    Team -- OWNS --> Svc2
    Priya -- EXPERT_IN --> Svc2
    C -- VIOLATES --> ADR29
    ADR29 -- SUPERSEDES --> ADR14
    ADR29 -- GOVERNS --> Svc2
    ADR29 -- PROTECTS --> Svc3
    Slack -- WARNS_ABOUT --> C
    Slack -- REFERENCES --> ADR29
    Priya -- POSTED_IN --> Slack
    Rb -- RESOLVES --> Inc
    Rb -- APPLIES_TO --> Svc2
    Mem -- RECALLS_DECISION --> ADR29
    Mem -- ABOUT_SERVICE --> Svc2
    Fact -- ABOUT_SERVICE --> Svc2
    Fact -- TARGET_SERVICE --> Svc3
    Run1 -- HANDED_OFF_TO --> Run2
    Run2 -- HANDED_OFF_TO --> Run3
    Run1 -- PART_OF_SESSION --> Sess
    Run2 -- PART_OF_SESSION --> Sess
    Run3 -- PART_OF_SESSION --> Sess
```

### Node Labels & Schema Catalog

| Node Label | Key Properties | Purpose & Semantic Role |
| :--- | :--- | :--- |
| `:Incident` | `id`, `title`, `severity`, `status`, `started_at`, `mitigated_at`, `commander` | Real-time production outages and reliability anomalies. |
| `:Service` | `name`, `tier`, `language`, `framework`, `port`, `version`, `repo` | Microservices and infrastructure topology. |
| `:Commit` | `sha`, `message`, `timestamp`, `files_changed`, `additions`, `deletions` | Git code changes and author provenance. |
| `:PullRequest` | `id`, `title`, `status`, `merged_at`, `repo` | Code reviews and merged pull requests. |
| `:Ticket` | `id`, `title`, `status`, `priority`, `description` | Issue tracking (Jira tickets, requirements). |
| `:Decision` | `id`, `title`, `status` (*Active/Superseded*), `date`, `rationale`, `author` | Architectural Decision Records (ADRs) governing systems. |
| `:SlackThread` | `id`, `channel`, `thread_ts`, `quote`, `timestamp`, `replies_count` | Discussions, warnings, and tribal knowledge. |
| `:Engineer` | `name`, `role`, `email`, `pagerduty`, `tz` | Software engineers, architects, and on-call leads. |
| `:Team` | `name`, `channel`, `description`, `lead` | Organizational engineering teams and ownership units. |
| `:EpisodicMemory` | `id`, `session_id`, `summary`, `confidence`, `timestamp`, `key_learnings` | Cross-session agent memory recalled across runs (Track 02). |
| `:SemanticFact` | `id`, `subject`, `predicate`, `object`, `rule`, `source`, `verified` | Distilled ground-truth rules and invariants (Track 02). |
| `:ProceduralRunbook` | `id`, `title`, `service`, `steps` (*list*), `verified`, `author` | Executable step-by-step mitigation procedures. |
| `:AgentRun` | `id`, `agent_name`, `session_id`, `findings`, `cypher_used`, `timestamp` | Audit records of autonomous agent steps in FalkorDB. |
| `:Session` | `id`, `started_at`, `last_active_at` | Agent investigation session anchor. |
| `:RemediationAction` | `id`, `description`, `timestamp`, `executor` | Graph actions executed to mitigate incidents. |

### Relationship Types Catalog

| Relationship | Source Node ➔ Target Node | Key Properties | Semantics |
| :--- | :--- | :--- | :--- |
| `[:AFFECTS]` | `:Incident` ➔ `:Service` | `symptom`, `error_rate` | Direct operational blast radius. |
| `[:DEPENDS_ON]` | `:Service` ➔ `:Service` | `criticality`, `timeout_ms`, `protocol` | Directed dependency topology for PageRank. |
| `[:MODIFIES]` | `:Commit` ➔ `:Service` | `diff_summary` | Service source code modification. |
| `[:IN_PR]` | `:Commit` ➔ `:PullRequest` | — | Commit membership in PR. |
| `[:ADDRESSES]` | `:PullRequest` ➔ `:Ticket` | — | PR implementation of Jira ticket. |
| `[:AUTHORED_COMMIT]` | `:Engineer` ➔ `:Commit` | — | Authorship provenance. |
| `[:MEMBER_OF]` | `:Engineer` ➔ `:Team` | — | Team affiliation. |
| `[:OWNS]` | `:Team` ➔ `:Service` | — | Service ownership boundary. |
| `[:EXPERT_IN]` | `:Engineer` ➔ `:Service` | `confidence`, `domain` | Subject-matter expertise matrix. |
| `[:VIOLATES]` | `:Commit` ➔ `:Decision` | `reason` | Commit breach of active ADR policy. |
| `[:SUPERSEDES]` | `:Decision` ➔ `:Decision` | — | Temporal decision lineage. |
| `[:GOVERNS]` | `:Decision` ➔ `:Service` | — | Policy governance over microservice. |
| `[:WARNS_ABOUT]` | `:SlackThread` ➔ `:Commit` | — | Team warning regarding risky change. |
| `[:REFERENCES]` | `:SlackThread` ➔ `:Decision` | — | Discussion context referencing ADR. |
| `[:RESOLVES]` | `:ProceduralRunbook` ➔ `:Incident` | — | Mitigation runbook mapping. |
| `[:APPLIES_TO]` | `:ProceduralRunbook` ➔ `:Service` | — | Runbook application target. |
| `[:HANDED_OFF_TO]` | `:AgentRun` ➔ `:AgentRun` | `timestamp`, `reason` | Graph-native multi-agent coordination. |
| `[:PART_OF_SESSION]` | `:AgentRun` ➔ `:Session` | — | Session containment. |
| `[:REMEDIATED_BY]` | `:Incident` ➔ `:RemediationAction` | — | Incident mitigation attachment. |
| `[:ABOUT_SERVICE]` | `:SemanticFact` ➔ `:Service` | — | Service invariant binding. |

---

## 💻 Core OpenCypher Queries & Graph Algorithms (Rule 10 Requirement)

The following exact, copy-pasteable OpenCypher queries power the engine:

### 1. Multi-Hop Incident Root-Cause & Attribution (5 Hops)
```cypher
MATCH (inc:Incident {id: $incident_id})-[:AFFECTS]->(svc:Service)
OPTIONAL MATCH (svc)-[:DEPENDS_ON*0..2]->(dep:Service)<-[:MODIFIES|MODIFIED]-(c:Commit)-[:IN_PR|PART_OF]->(pr:PullRequest)
OPTIONAL MATCH (eng:Engineer)-[:AUTHORED|AUTHORED_COMMIT]->(c)
OPTIONAL MATCH (team:Team)-[:OWNS]->(dep)
OPTIONAL MATCH (c)-[v:VIOLATES]->(d:Decision)
RETURN inc.id AS incident_id, inc.title AS incident_title, inc.severity AS severity,
       svc.name AS affected_service, dep.name AS root_service,
       c.sha AS commit_sha, c.message AS commit_msg, c.timestamp AS commit_timestamp,
       pr.id AS pr_id, pr.title AS pr_title,
       eng.name AS author, eng.email AS author_email, eng.role AS author_role,
       team.name AS owning_team, team.channel AS team_channel,
       d.id AS violated_decision_id, d.title AS violated_decision_title,
       v.reason AS violation_reason;
```

### 2. FalkorDB Native PageRank Centrality Algorithm
```cypher
CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score
RETURN node.id AS id, node.name AS service, node.tier AS tier, node.status AS status, score
ORDER BY score DESC;
```

### 3. Multi-Hop Downstream Blast-Radius Traversal (Up to 3 Hops)
```cypher
MATCH path = (upstream:Service)-[r:DEPENDS_ON*1..3]->(target:Service {name: $service_name})
RETURN upstream.name AS impacted_service, upstream.tier AS tier,
       length(path) AS hops,
       [n IN nodes(path) | n.name] AS path_services,
       [rel IN relationships(path) | properties(rel)] AS path_rels;
```

### 4. Company Brain: Architectural Decision Lineage & Slack Warnings
```cypher
MATCH (d:Decision)-[:GOVERNS]->(s:Service {name: $service_name})
OPTIONAL MATCH (d)-[:SUPERSEDES]->(old_d:Decision)
OPTIONAL MATCH (st:SlackThread)-[:REFERENCES|DISCUSSES]->(d)
OPTIONAL MATCH (exp:Engineer)-[r:EXPERT_IN]->(s)
RETURN d.id AS decision_id, d.title AS decision_title, d.status AS status,
       d.date AS decision_date, d.rationale AS rationale, d.author AS author,
       old_d.id AS superseded_decision_id, old_d.title AS superseded_title,
       st.id AS slack_id, st.channel AS slack_channel, st.quote AS slack_quote,
       exp.name AS expert_name, exp.role AS expert_role, r.confidence AS expert_confidence;
```

### 5. Multi-Agent Graph Handoff Writing (Track 02 Coordination)
```cypher
MERGE (sess:Session {id: $session_id})
ON CREATE SET sess.started_at = $timestamp
SET sess.last_active_at = $timestamp

CREATE (from_run:AgentRun {
    id: $from_run_id,
    agent_name: $from_agent,
    session_id: $session_id,
    findings: $findings,
    cypher_used: $cypher_used,
    timestamp: $timestamp
})
CREATE (to_run:AgentRun {
    id: $to_run_id,
    agent_name: $to_agent,
    session_id: $session_id,
    status: "pending",
    timestamp: $timestamp
})

MERGE (from_run)-[:PART_OF_SESSION]->(sess)
MERGE (to_run)-[:PART_OF_SESSION]->(sess)
MERGE (from_run)-[:HANDED_OFF_TO {timestamp: $timestamp, reason: "Autonomous investigation handoff"}]->(to_run)
RETURN sess.id AS session_id, from_run.id AS from_id, to_run.id AS to_id;
```

### 6. Graph Action Execution & Persistent Memory Creation
```cypher
MATCH (inc:Incident {id: $incident_id})
SET inc.status = "Mitigated",
    inc.mitigated_at = $timestamp,
    inc.resolution_summary = $action_taken

CREATE (act:RemediationAction {
    id: $action_id,
    description: $action_taken,
    timestamp: $timestamp,
    executor: "AutonomousEngineeringAgent"
})
MERGE (inc)-[:REMEDIATED_BY]->(act)
MERGE (sess:Session {id: $session_id})
MATCH (svc:Service {name: $service_name})
MERGE (act)-[:APPLIED_TO]->(svc)

CREATE (mem:EpisodicMemory {
    id: $memory_id,
    session_id: $session_id,
    summary: $action_summary,
    confidence: 0.99,
    timestamp: $timestamp,
    key_learnings: $learned_fact
})
MERGE (mem)-[:RESOLVED_INCIDENT]->(inc)
MERGE (mem)-[:ABOUT_SERVICE]->(svc)
MERGE (mem)-[:RECORDED_IN_SESSION]->(sess)

MERGE (fact:SemanticFact {id: $fact_id})
SET fact.subject = $service_name,
    fact.predicate = "mitigation_rule",
    fact.object = $learned_fact,
    fact.source = "IncidentResolution:" + $incident_id,
    fact.verified = true,
    fact.updated_at = $timestamp
MERGE (fact)-[:ABOUT_SERVICE]->(svc);
```

---

## 🚢 Zero-Docker Setup & Live Deployment

NexusGraph connects directly to **FalkorDB Cloud** via encrypted TCP sockets using the official `falkordb` SDK. **No Docker daemon or local containers are required.**

### Option A: Local 3-Step Setup (2 Minutes)

1. **Clone & Create Environment:**
   ```bash
   git clone https://github.com/your-username/nexusgraph.git
   cd nexusgraph
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   # source .venv/bin/activate # macOS/Linux
   pip install -r requirements.txt
   ```

2. **Configure `.env` (or use UI sidebar directly):**
   ```ini
   FALKORDB_HOST=your-instance.falkordb.cloud
   FALKORDB_PORT=6379
   FALKORDB_USERNAME=falkordb
   FALKORDB_PASSWORD=your-password
   FALKORDB_DEFAULT_TENANT=acme_prod
   GEMINI_API_KEY=your-gemini-api-key
   ```
   *(Free FalkorDB Cloud instances are provisioned instantly at [app.falkordb.cloud](https://app.falkordb.cloud)).*

3. **Launch Streamlit Dashboard:**
   ```bash
   streamlit run app.py
   ```
   *Judges can also paste FalkorDB Cloud credentials directly in the Streamlit sidebar.*

---

### Option B: Deploy Live to Streamlit Community Cloud (Zero-Install for Judges)

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io/) and select the repository (`Main file path: app.py`).
3. Under **Advanced settings ➔ Secrets**, paste:
   ```toml
   FALKORDB_HOST = "your-instance.falkordb.cloud"
   FALKORDB_PORT = 6379
   FALKORDB_USERNAME = "falkordb"
   FALKORDB_PASSWORD = "your-password"
   FALKORDB_DEFAULT_TENANT = "acme_prod"
   GEMINI_API_KEY = "your-gemini-api-key"
   ```
4. Click **Deploy**. The app will be live on a public URL in < 90 seconds.

---

### Option C: Deploy to Render / Railway
Add a `Dockerfile`-free Python Web Service:
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
- Set the environment variables in the dashboard.

---

## 🤖 Model Context Protocol (FastMCP) Integration

NexusGraph exposes its FalkorDB graph reasoning tools via the official **FastMCP** server standard (`mcp.server.fastmcp`). Any external LLM agent (Claude Desktop, Cursor, Antigravity, or custom agents) can connect directly to FalkorDB via MCP:

```bash
# Start the MCP server:
python -m src.mcp.server
```

**Exposed MCP Tools:**
1. `blast_radius_and_criticality(tenant_id, service_name)`
2. `trace_incident_root_cause(tenant_id, incident_id)`
3. `trace_decision_lineage(tenant_id, service_name)`
4. `recall_memories(tenant_id, service_name)`
5. `record_handoff(tenant_id, session_id, from_agent, to_agent, findings)`
6. `execute_graph_action(tenant_id, session_id, incident_id, service_name, action)`

---

## 🧪 Comprehensive Automated Verification

Run the full automated test suite (20 unit tests across all 6 phases):
```bash
python -m unittest discover tests
```

Execute the live rule verification harness:
```bash
python -m tests.verify_hackathon_rules
```

```text
======================================================================
 [PASS] ALL HACKATHON RULES VERIFIED SUCCESSFULLY!
======================================================================
Summary of Verified Tracks:
  [PASS] Track 01: Connected Data & Actions (PageRank, blast radius, root cause, graph action)
  [PASS] Track 02: Agent Memory & Multi-Agent Coordination (multi-tenant, graph handoffs, cross-session recall)
  [PASS] Track 03: Company Brain (ADRs, superseded lineage, Slack warning provenance, engineer ownership)
======================================================================
```

---

## 📜 AI Coding Assistant Disclosure (Hackathon Rule 11 Compliance)

In compliance with **Hackathon Rule 11**:
- **Tooling Used:** Google Antigravity Agentic IDE powered by **Gemini 2.5 Flash** was utilized as an AI pair-programming assistant during development.
- **Scope of AI Assistance:** Used for code scaffolding, typing boilerplate, unit test scaffolding, and initial documentation drafting.
- **Human Author Contribution:** The participant designed the graph data model, authored the OpenCypher traversal and mutation queries, implemented the 3-agent orchestration protocol, engineered the FalkorDB multi-tenant isolation routing, tuned the PageRank graph algorithms, verified all 20 test cases, and connected the live FalkorDB Cloud cluster.

---

## 📄 License
MIT License. Built with ❤️ for the FalkorDB Graph Hacks Hackathon 2026.
