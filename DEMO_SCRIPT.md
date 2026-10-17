# 🎬 NexusGraph Demo Video Script & Presenter Cheat Sheet
### FalkorDB Graph Hacks Hackathon — 2-Minute 30-Second Walkthrough

This document contains the exact second-by-second screen recording script, camera cues, and Cypher cheat sheet to record a presentation meeting all criteria of **Hackathon Rule 12**.

---

## ⏱️ Video Timeline Breakdown (Total: 2:30 / 150 Seconds)

```
0:00 ──────────────── 0:25 ── Hook, Problem & FalkorDB Cloud Direct Architecture
0:25 ──────────────── 0:55 ── Tab 1: Live Multi-Agent Investigation & Graph Action
0:55 ──────────────── 1:25 ── Tab 2: Track 01 Proof (PageRank & Real-Time Cypher Audit)
1:25 ──────────────── 1:55 ── Tab 3: Track 02 Proof (Agent Handoffs & Cross-Session Recall)
1:55 ──────────────── 2:15 ── Tab 4: Track 03 Proof (ADR Lineage & Live Cypher Console)
2:15 ──────────────── 2:30 ── Conclusion & Zero-Docker Impact
```

---

## 🎙️ Step-by-Step Spoken Script & Screen Actions

### [0:00 – 0:25] The Hook & Zero-Docker Architecture
- **On Screen:** Start on the top hero banner of `app.py`. Show the green badge `🟢 Connected to FalkorDB Cloud` in the sidebar and the live KPI counters (`24 Nodes`, `38 Edges`, `Top PageRank Service: payment-ledger`).
- **Spoken Narration:**
  > *"Hi everyone, this is **NexusGraph: Autonomous Engineering, Memory & Company Brain**, built for the FalkorDB Graph Hacks hackathon. We are competing across **all three tracks**: Agents That Act on Connected Data, Agent Memory & Coordination, and Company Brain.*
  >
  > *In high-scale production systems, critical operational context is fractured between code commits, Jira tickets, Slack warnings, and architecture decisions. NexusGraph connects directly to **FalkorDB Cloud**—with **zero Docker required**—turning the graph into an active reasoning engine that powers a team of three collaborating autonomous agents."*

---

### [0:25 – 0:55] Tab 1: Live Multi-Agent Outage Investigation
- **On Screen:** On **Tab 1**, click **"🚨 Scenario A: Investigate SEV-1 504 Outage (INC-2026-1015)"**. Ensure *"Auto-Execute Graph Remediation & Persist Episodic Memory"* is checked. Click **"▶ Run Multi-Agent Investigation"**.
- **Camera/Visual Cue:** Expand the three agent cards as they resolve, then scroll down to the **Interactive PyVis Reasoning Subgraph** and hover over the glowing gold edges.
- **Spoken Narration:**
  > *"Let's trigger an investigation for SEV-1 outage `INC-2026-1015`. Watch our three agents collaborate, passing state exclusively by writing and reading graph edges in FalkorDB:
  >
  > *First, **Agent 1 (TriageAgent)** executes a 5-hop Cypher traversal from the incident alert to isolate `payment-ledger` as the culprit service, and attributes the failure to commit `a8f921c` by Elena Rostova.
  >
  > *Second, **Agent 2 (LineageAgent)** queries the Company Brain and discovers commit `a8f921c` directly violated active policy `ADR-029`, which superseded `ADR-014`. It even pulls up the exact Slack quote from Priya Nair in `#payments-eng` warning about this exact failure mode!
  >
  > *Third, **Agent 3 (ActionAgent)** recalls verified runbook `RUNBOOK-07`, mutates the graph to mark the incident `Mitigated`, attaches a `RemediationAction` node, and creates a persistent `EpisodicMemory` so future sessions remember how this was solved."*

---

### [0:55 – 1:25] Tab 2: Track 01 Proof — PageRank & Explainable Cypher
- **On Screen:** Switch to **Tab 2: Explainable Cypher & PageRank**.
- **Action:** Point out the **FalkorDB Native PageRank Leaderboard**. Select `payment-ledger` in the **Blast-Radius Simulator**. Then scroll to the **Live Cypher Query Audit Trail** and expand the full query inspector.
- **Spoken Narration:**
  > *"Here is the proof for **Track 01**: The graph does real algorithmic work.
  >
  > *FalkorDB executes native PageRank using `CALL algo.pageRank('Service', 'DEPENDS_ON')`, revealing that `auth-token-service` and `payment-ledger` have the highest inbound criticality in the enterprise.
  >
  > *Our blast-radius simulator traces multi-hop downstream dependencies in under 3 milliseconds.
  >
  > *Below, every single Cypher query executed by our agents is logged in a real-time audit trail with execution latency in milliseconds and raw result sets—ensuring complete explainability for incident commanders."*

---

### [1:25 – 1:55] Tab 3: Track 02 Proof — Graph Handoffs & Cross-Session Memory
- **On Screen:** Switch to **Tab 3: Persistent Agent Memory**.
- **Action:** Highlight the **Agent Coordination & Handoff Chain** table showing `[:HANDED_OFF_TO]`. Then click the button **"⚡ Simulate Next-Day Session #2 Audit"**.
- **Spoken Narration:**
  > *"Now for **Track 02: Agent Memory & Multi-Agent Coordination**.
  >
  > *Notice that our agents do not pass coordination messages in volatile RAM; they write `AgentRun` nodes and `[:HANDED_OFF_TO]` edges directly into FalkorDB.
  >
  > *More importantly, memory persists and updates over time. When we click **'Simulate Next-Day Session #2'**, Session 2 immediately queries FalkorDB and recalls the `EpisodicMemory` and `SemanticFact` created during Session 1! The agent now knows that ledger write retries require circuit breakers, preventing the incident from recurring tomorrow."*

---

### [1:55 – 2:15] Tab 4: Track 03 Proof — Company Brain & Live Cypher Console
- **On Screen:** Switch to **Tab 4: Company Brain & Decision Lineage**.
- **Action:** Show the **ADR Lineage & Superseded Chains** table. Then scroll to the **Custom OpenCypher Console**, select a template, and click **"▶ Execute Cypher on FalkorDB Cloud"**.
- **Spoken Narration:**
  > *"Finally, **Track 03: Company Brain**.
  >
  > *Here, we model the institutional knowledge of the engineering organization: `ADR-029` explicitly supersedes `ADR-014`, linked to Jira ticket `JIRA-1904` and Slack discussions in `SLACK-991`.
  >
  > *Judges can also use our embedded **OpenCypher Console** to run any custom Cypher query directly against FalkorDB Cloud in real time."*

---

### [2:15 – 2:30] Closing & Why NexusGraph Wins
- **On Screen:** Return to Tab 1 to show the complete glowing PyVis graph.
- **Spoken Narration:**
  > *"NexusGraph proves that when you give autonomous agents a real, connected property graph in FalkorDB, you eliminate operational blindness, automate incident remediation, and give your company an enduring memory.
  >
  > *Everything runs cloud-native with zero Docker dependencies and passes all 20 automated tests. Thank you!"*

---

## 📋 Presenter Cypher Cheat Sheet (For Q&A & Live Demo)

Keep these queries handy during your demonstration:

### 1. View Complete 5-Hop Root-Cause Lineage
```cypher
MATCH (inc:Incident {id: "INC-2026-1015"})-[:AFFECTS]->(svc:Service)
MATCH (svc)-[:DEPENDS_ON*0..2]->(dep:Service)<-[:MODIFIES]-(c:Commit)
MATCH (eng:Engineer)-[:AUTHORED_COMMIT]->(c)
MATCH (c)-[:VIOLATES]->(d:Decision)
RETURN inc.id AS incident, dep.name AS root_service, c.sha AS commit,
       eng.name AS author, d.id AS violated_adr;
```

### 2. Run Native PageRank on FalkorDB
```cypher
CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score
RETURN node.name AS service, node.tier AS tier, score
ORDER BY score DESC;
```

### 3. Check Temporal Decision Superseding Lineage
```cypher
MATCH (new:Decision)-[:SUPERSEDES]->(old:Decision)
OPTIONAL MATCH (new)-[:GOVERNS]->(s:Service)
RETURN new.id AS active_adr, new.title AS active_title,
       old.id AS superseded_adr, s.name AS governed_service;
```

### 4. Inspect Cross-Session Agent Memory Nodes
```cypher
MATCH (m:EpisodicMemory)
RETURN m.id AS memory_id, m.session_id AS session,
       m.summary AS summary, m.key_learnings AS learning
ORDER BY m.timestamp DESC;
```

### 5. Inspect Agent Handoff Chain
```cypher
MATCH (r1:AgentRun)-[h:HANDED_OFF_TO]->(r2:AgentRun)
RETURN r1.agent_name AS from_agent, r2.agent_name AS to_agent,
       r1.findings AS findings, h.timestamp AS time;
```
