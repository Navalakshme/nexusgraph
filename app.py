"""NexusGraph: Autonomous Engineering, Memory & Company Brain.

FalkorDB Graph Hacks Hackathon — Entering All 3 Tracks:
- Track 01: Agents That Act on Connected Data
- Track 02: Agent Memory & Multi-Agent Coordination
- Track 03: Company Brain & Architectural Decision Lineage
"""

import os
import sys
import json
import time
from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd

from src.db.falkor_client import FalkorGraphManager, get_db_manager, run_cypher
from src.db.seed_company_brain import seed_tenant_graph
from src.agents.orchestrator import NexusMultiAgentOrchestrator
from src.ui.graph_viz import (
    render_pyvis_network,
    build_pyvis_from_traversed_paths,
    build_pyvis_from_falkor_graph,
)
from src.mcp.falkor_tools import (
    compute_blast_radius_and_criticality,
    trace_incident_root_cause_multihop,
    trace_company_decision_lineage,
    recall_agent_memories,
)

# ------------------------------------------------------------------------------
# 1. Page Configuration & Custom Dark Mode Styling
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="NexusGraph | FalkorDB Agent Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* Completely hide sidebar */
    [data-testid="stSidebar"], section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* Dark glassmorphic theme */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Header card */
    .nexus-hero {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
    }
    
    .nexus-title {
        font-size: 26px;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
    }
    
    .track-tag {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        margin-right: 6px;
        margin-top: 4px;
    }
    .track-1 { background: rgba(14, 165, 233, 0.2); color: #38bdf8; border: 1px solid #0284c7; }
    .track-2 { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #d97706; }
    .track-3 { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid #9333ea; }
    
    /* Info badge */
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    
    /* Metric boxes */
    .metric-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 10px;
        padding: 14px;
        text-align: center;
    }
    .metric-val {
        font-size: 24px;
        font-weight: 800;
        color: #f8fafc;
    }
    .metric-lbl {
        font-size: 11px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }
    
    /* Architecture cards */
    .info-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 8px;
        padding: 16px;
        height: 100%;
    }
    .info-card h4 {
        margin: 0 0 8px 0;
        color: #38bdf8;
        font-size: 16px;
    }
    .info-card p, .info-card li {
        font-size: 13px;
        color: #cbd5e1;
        line-height: 1.5;
    }
    
    /* Agent step cards */
    .agent-card {
        background: rgba(15, 23, 42, 0.85);
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 12px;
    }
    .agent-card-1 { border-left: 4px solid #38bdf8; }
    .agent-card-2 { border-left: 4px solid #c084fc; }
    .agent-card-3 { border-left: 4px solid #fbbf24; }
    
    /* Pill citation tags */
    .citation-pill {
        background: #1e293b;
        color: #38bdf8;
        padding: 2px 8px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 12px;
        border: 1px solid rgba(56, 189, 248, 0.4);
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 2. Session State Initialization
# ------------------------------------------------------------------------------
if "current_tenant" not in st.session_state:
    st.session_state["current_tenant"] = os.getenv("FALKORDB_DEFAULT_TENANT", "acme_prod")

if "active_session_id" not in st.session_state:
    st.session_state["active_session_id"] = "sess_session_1_outage"

if "last_investigation_result" not in st.session_state:
    st.session_state["last_investigation_result"] = None

if "query_audit_log" not in st.session_state:
    st.session_state["query_audit_log"] = []

# Database Manager singleton
manager = get_db_manager()
conn_status = manager.check_connection()
is_connected = bool(conn_status.get("connected"))
current_tenant = st.session_state["current_tenant"]


# ------------------------------------------------------------------------------
# 3. Top Banner & Header Controls (Zero Sidebar Needed)
# ------------------------------------------------------------------------------
head_col1, head_col2 = st.columns([3, 1])

with head_col1:
    st.markdown("""
    <div class="nexus-hero">
        <div class="nexus-title">🧠 NexusGraph: Autonomous Engineering, Memory & Company Brain</div>
        <div style="color: #94a3b8; font-size: 14px; margin-bottom: 8px;">
            A live multi-agent reasoning and memory engine powered directly by <b>FalkorDB Cloud</b> & <b>Google Gemini</b>.
        </div>
        <div>
            <span class="track-tag track-1">Track 01: Connected Data & Actions</span>
            <span class="track-tag track-2">Track 02: Persistent Memory & Coordination</span>
            <span class="track-tag track-3">Track 03: Company Brain & Decision Lineage</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with head_col2:
    st.markdown("<div style='padding-top: 10px;'>", unsafe_allow_html=True)
    if is_connected:
        st.markdown(f"""
        <div class="status-badge">
            🟢 FalkorDB Cloud Connected ({conn_status.get('latency_ms')} ms)
        </div>
        <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">
            Graph: <code>nexus_{current_tenant}</code> (AWS Mumbai)
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error(f"🔴 FalkorDB Disconnected: {conn_status.get('error', '')[:50]}")
    
    st.markdown("<div style='margin-top: 10px;'>", unsafe_allow_html=True)
    if st.button("⚡ Reset / Re-seed Cloud Graph", use_container_width=True, help="Populate or reset the 25 nodes and 55 edges directly in FalkorDB Cloud"):
        with st.spinner("Seeding FalkorDB Cloud graph..."):
            res = seed_tenant_graph(manager=manager, tenant_id=current_tenant, reset=True)
            if res.get("success"):
                st.success(f"Seeded {res.get('total_nodes')} nodes & {res.get('total_edges')} edges!")
                time.sleep(0.6)
                st.rerun()
            else:
                st.error(f"Failed: {res.get('error')}")
    st.markdown("</div></div>", unsafe_allow_html=True)


# Fetch live metrics from FalkorDB strictly if connected
if is_connected:
    node_count_res = manager.run_cypher(tenant_id=current_tenant, query="MATCH (n) RETURN count(n) AS c", read_only=True)
    edge_count_res = manager.run_cypher(tenant_id=current_tenant, query="MATCH ()-[r]->() RETURN count(r) AS c", read_only=True)
    mem_count_res = manager.run_cypher(tenant_id=current_tenant, query="MATCH (m:EpisodicMemory) RETURN count(m) AS c", read_only=True)
    handoff_count_res = manager.run_cypher(tenant_id=current_tenant, query="MATCH ()-[r:HANDED_OFF_TO]->() RETURN count(r) AS c", read_only=True)
    pagerank_res = manager.run_cypher(
        tenant_id=current_tenant,
        query="CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score RETURN node.name AS name ORDER BY score DESC LIMIT 1",
        read_only=True,
    )
    tot_nodes = node_count_res.data[0]["c"] if node_count_res.success and node_count_res.data else 0
    tot_edges = edge_count_res.data[0]["c"] if edge_count_res.success and edge_count_res.data else 0
    tot_mems = mem_count_res.data[0]["c"] if mem_count_res.success and mem_count_res.data else 0
    tot_handoffs = handoff_count_res.data[0]["c"] if handoff_count_res.success and handoff_count_res.data else 0
    top_service = pagerank_res.data[0]["name"] if pagerank_res.success and pagerank_res.data else "—"
else:
    tot_nodes, tot_edges, tot_mems, tot_handoffs, top_service = 0, 0, 0, 0, "—"

mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
with mcol1:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#38bdf8;">{tot_nodes}</div><div class="metric-lbl">Total Graph Nodes</div></div>', unsafe_allow_html=True)
with mcol2:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#818cf8;">{tot_edges}</div><div class="metric-lbl">Connected Edges</div></div>', unsafe_allow_html=True)
with mcol3:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#fbbf24;">{tot_mems}</div><div class="metric-lbl">Episodic Memories</div></div>', unsafe_allow_html=True)
with mcol4:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#34d399;">{tot_handoffs}</div><div class="metric-lbl">Agent Handoffs</div></div>', unsafe_allow_html=True)
with mcol5:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f43f5e;">{top_service}</div><div class="metric-lbl">Top Centrality Service</div></div>', unsafe_allow_html=True)

st.markdown("<br/>", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 4. Five Clean, Intuitive Navigation Tabs
# ------------------------------------------------------------------------------
tab_dash, tab_pipe, tab_ag1, tab_ag2, tab_ag3 = st.tabs([
    "📊 1. System Overview & Live Graph",
    "🤖 2. Multi-Agent Investigation & Reasoning",
    "🔍 3. Agent 1: Triage & Topology (Track 01)",
    "🏛️ 4. Agent 2: Company Brain & ADR Lineage (Track 03)",
    "🧠 5. Agent 3: Persistent Memory & Actions (Track 02)",
])


# ==============================================================================
# TAB 1: SYSTEM OVERVIEW & ARCHITECTURE DASHBOARD
# ==============================================================================
with tab_dash:
    st.subheader("System Architecture & Dataset Explorer")
    st.markdown("Everything inside NexusGraph operates strictly against connected graph data in **FalkorDB Cloud**.")
    
    c_arch1, c_arch2, c_arch3 = st.columns(3)
    
    with c_arch1:
        st.markdown("""
        <div class="info-card">
            <h4>🌐 Where is the Data Stored?</h4>
            <p>
                <b>Database:</b> FalkorDB Cloud (AWS Mumbai • <code>ap-south-1</code>)<br/>
                <b>Graph Database Key:</b> <code>nexus_acme_prod</code><br/>
                <b>Engine:</b> FalkorDB GraphBLAS sparse matrices with disk persistence.<br/>
                <b>Isolation:</b> Every tenant is strictly isolated in its own graph namespace (<code>nexus_{tenant_id}</code>).
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c_arch2:
        st.markdown("""
        <div class="info-card">
            <h4>📦 What Data is Used?</h4>
            <p>A realistic enterprise engineering ecosystem linking 3 layers:</p>
            <ul>
                <li><b>7 Microservices:</b> <code>checkout-orchestrator</code>, <code>payment-ledger</code>, <code>auth-token-service</code>, etc.</li>
                <li><b>ADR Decisions:</b> <code>ADR-029</code> superseding <code>ADR-014</code>.</li>
                <li><b>Code & Commits:</b> Commit <code>a8f921c</code> by Elena Rostova.</li>
                <li><b>Slack & Tickets:</b> Thread <code>SLACK-991</code> with warnings.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with c_arch3:
        st.markdown("""
        <div class="info-card">
            <h4>🔄 Are the 3 Agents Connected?</h4>
            <p>
                <b>YES! They operate as a collaborative pipeline.</b><br/>
                State is passed <b>strictly through FalkorDB</b>:
            </p>
            <ul>
                <li><b>Agent 1</b> isolates root cause ➔ writes <code>[:HANDED_OFF_TO]</code> edge.</li>
                <li><b>Agent 2</b> reads handoff, queries ADR lineage ➔ writes <code>[:HANDED_OFF_TO]</code>.</li>
                <li><b>Agent 3</b> reads handoff, mitigates incident, and writes <code>(:EpisodicMemory)</code>.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("### 🌐 Live Enterprise Knowledge Graph (Rendered Directly from FalkorDB Cloud)")
    st.caption(f"Interactive PyVis graph rendering all active nodes and edges in `nexus_{current_tenant}`. Drag nodes or zoom to explore.")
    
    if is_connected:
        full_graph_html = build_pyvis_from_falkor_graph(manager=manager, tenant_id=current_tenant, max_nodes=50, height="520px")
        st.components.v1.html(full_graph_html, height=540, scrolling=True)
    else:
        st.warning("Connect to FalkorDB Cloud to explore live graph nodes.")


# ==============================================================================
# TAB 2: MULTI-AGENT COLLABORATIVE PIPELINE (ALL 3 AGENTS TOGETHER)
# ==============================================================================
with tab_pipe:
    st.subheader("Autonomous Multi-Agent Collaborative Pipeline")
    st.markdown("Run the 3 specialized agents in sequence: **TriageAgent** ➔ **LineageAgent** ➔ **ActionAgent** passing state via FalkorDB.")

    pcol1, pcol2, pcol3 = st.columns(3)
    preset_query = None
    if pcol1.button("🚨 Scenario A: Investigate SEV-1 504 Outage (INC-2026-1015)", use_container_width=True):
        preset_query = "Investigate SEV-1 Incident INC-2026-1015, verify if any architectural decision was violated, check past memory, and execute mitigation."
    if pcol2.button("📜 Scenario B: Audit ADR Lineage for payment-ledger", use_container_width=True):
        preset_query = "Audit architectural decision lineage and Slack warnings for payment-ledger to see which ADR was superseded."
    if pcol3.button("🧠 Scenario C: Recall Memory for auth-token-service", use_container_width=True):
        preset_query = "Recall cross-session episodic memories, procedural runbooks, and blast radius for auth-token-service."

    user_input = st.text_input(
        "Investigation Query / Instruction:",
        value=preset_query or "Investigate SEV-1 Incident INC-2026-1015, verify if any architectural decision was violated, check past memory, and execute mitigation.",
    )

    tcol1, tcol2 = st.columns([3, 1])
    with tcol1:
        auto_mitigate = st.checkbox("Auto-Execute Graph Remediation & Persist Episodic Memory in FalkorDB", value=True)
    with tcol2:
        run_btn = st.button("▶ Run Multi-Agent Investigation", type="primary", use_container_width=True, disabled=not is_connected)

    if run_btn:
        orchestrator = NexusMultiAgentOrchestrator(
            manager=manager,
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
        )
        
        with st.status("🚀 Running 3-Agent Collaborative Investigation...", expanded=True) as status:
            st.write("🔍 **Agent 1 (Triage & Topology)**: Running 5-hop incident traversal & PageRank blast radius in FalkorDB...")
            time.sleep(0.3)
            st.write("🏛️ **Agent 2 (Company Brain)**: Reading handoff from graph; inspecting ADR superseded lineage & Slack warnings...")
            time.sleep(0.3)
            st.write("🧠 **Agent 3 (Memory & Action)**: Recalling past runbooks, executing mitigation, and persisting EpisodicMemory...")
            
            result = orchestrator.run_investigation(
                tenant_id=current_tenant,
                session_id=st.session_state["active_session_id"],
                user_prompt=user_input,
                incident_id="INC-2026-1015",
                auto_mitigate=auto_mitigate,
            )
            st.session_state["last_investigation_result"] = result
            status.update(label="✅ Autonomous Multi-Agent Investigation Complete!", state="complete", expanded=False)

    # Render results
    inv_res = st.session_state["last_investigation_result"]
    if inv_res:
        st.markdown("---")
        st.markdown("### 🕵️ Multi-Agent Reasoning Trace (State Stored in FalkorDB)")
        
        col_ag1, col_ag2, col_ag3 = st.columns(3)
        steps = inv_res.get("agent_steps", [])
        
        if len(steps) >= 1:
            with col_ag1:
                s1 = steps[0]
                st.markdown(f"""
                <div class="agent-card agent-card-1">
                    <b style="color:#38bdf8;">1. {s1['agent_name']} ({s1['role']})</b><br/>
                    <small style="color:#94a3b8;">{s1['track']}</small>
                    <p style="font-size:13px; margin-top:8px;">{s1['reasoning']}</p>
                    <div style="font-size:12px;">
                        <b>Root Service:</b> <code>{s1['findings'].get('root_service')}</code><br/>
                        <b>Culprit Commit:</b> <code>{s1['findings'].get('culprit_commit')}</code><br/>
                        <b>Handoff Edge:</b> <code>[:HANDED_OFF_TO] ➔ {s1['handoff_to']}</code>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        if len(steps) >= 2:
            with col_ag2:
                s2 = steps[1]
                st.markdown(f"""
                <div class="agent-card agent-card-2">
                    <b style="color:#c084fc;">2. {s2['agent_name']} ({s2['role']})</b><br/>
                    <small style="color:#94a3b8;">{s2['track']}</small>
                    <p style="font-size:13px; margin-top:8px;">{s2['reasoning']}</p>
                    <div style="font-size:12px;">
                        <b>Violated Decision:</b> <span class="citation-pill">ADR-029</span><br/>
                        <b>Superseded:</b> <span class="citation-pill">ADR-014</span><br/>
                        <b>Slack Warning:</b> <code>{s2['findings'].get('slack_warning_thread')}</code><br/>
                        <b>Handoff Edge:</b> <code>[:HANDED_OFF_TO] ➔ {s2['handoff_to']}</code>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        if len(steps) >= 3:
            with col_ag3:
                s3 = steps[2]
                st.markdown(f"""
                <div class="agent-card agent-card-3">
                    <b style="color:#fbbf24;">3. {s3['agent_name']} ({s3['role']})</b><br/>
                    <small style="color:#94a3b8;">{s3['track']}</small>
                    <p style="font-size:13px; margin-top:8px;">{s3['reasoning']}</p>
                    <div style="font-size:12px;">
                        <b>Runbook Recalled:</b> <span class="citation-pill">{s3['findings'].get('procedural_runbook')}</span><br/>
                        <b>Action Taken:</b> <code>{s3['findings'].get('action_executed')[:40]}...</code><br/>
                        <b>Incident Status:</b> <b style="color:#34d399;">{s3['findings'].get('incident_status')}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # Interactive Subgraph Rendering with PyVis
        st.markdown("### 🌐 Visual Reasoning Subgraph (FalkorDB Traversed Paths Highlighted)")
        st.caption("Glowing gold edges denote the exact multi-hop path traversed by the agents across FalkorDB Cloud.")
        traversed = inv_res.get("traversed_paths", [])
        graph_html = build_pyvis_from_traversed_paths(traversed_paths=traversed, height="480px")
        st.components.v1.html(graph_html, height=500, scrolling=True)

        # Executive Report Synthesis
        st.markdown("### 📑 Executive Incident Synthesis (Google Gemini Source-Cited)")
        st.markdown(inv_res.get("final_synthesis", ""))

        with st.expander("💾 Memory Diff: Graph Mutation Stored in FalkorDB Cloud", expanded=False):
            st.json(inv_res.get("memory_diff", {}))
    else:
        st.info("👆 Click **'Scenario A'** or **'▶ Run Multi-Agent Investigation'** above to run the 3-agent pipeline and generate the live reasoning graph!")


# ==============================================================================
# TAB 3: AGENT 1: INFRASTRUCTURE & TOPOLOGY (TRACK 01)
# ==============================================================================
with tab_ag1:
    st.subheader("Agent 1 — Triage & Topology Specialist (Track 01 Focus)")
    st.markdown("Specialized in microservice topology, downstream dependency blast-radius calculation, and native PageRank centrality.")

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("#### 🏆 FalkorDB Native PageRank Centrality")
        st.caption("Executed Query: `CALL algo.pageRank('Service', 'DEPENDS_ON')`")
        pr_data = compute_blast_radius_and_criticality(manager=manager, tenant_id=current_tenant)
        pr_table = pr_data.get("pagerank_table", [])
        if pr_table:
            st.dataframe(pd.DataFrame(pr_table), use_container_width=True, hide_index=True)
        else:
            st.info("No PageRank results returned.")

    with c2:
        st.markdown("#### 💥 Interactive Blast-Radius Simulator")
        target_svc = st.selectbox(
            "Select Service to Simulate Outage:",
            options=["payment-ledger", "auth-token-service", "checkout-orchestrator", "redis-session-cache", "api-gateway"],
            index=0
        )
        blast_info = compute_blast_radius_and_criticality(manager=manager, tenant_id=current_tenant, service_name=target_svc)
        impacted = blast_info.get("impacted_services", [])
        st.markdown(f"**Impacted Upstream Services ({len(impacted)}):**")
        if impacted:
            st.dataframe(pd.DataFrame(impacted), use_container_width=True, hide_index=True)
        else:
            st.write("No upstream dependencies detected.")

    st.markdown("---")
    st.markdown("#### 📜 Live Cypher Query Audit Trail (Queries Executed in FalkorDB)")
    audit_entries = manager.get_audit_log(limit=10)
    if audit_entries:
        audit_rows = []
        for e in audit_entries:
            audit_rows.append({
                "Timestamp": e.get("timestamp")[:19].replace("T", " "),
                "Tenant": e.get("tenant_id"),
                "Latency (ms)": e.get("latency_ms"),
                "Rows": e.get("row_count"),
                "Success": "✅" if e.get("success") else "❌",
                "Cypher Query": e.get("query")[:80] + "..." if len(e.get("query", "")) > 80 else e.get("query"),
            })
        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)


# ==============================================================================
# TAB 4: AGENT 2: COMPANY BRAIN & DECISION LINEAGE (TRACK 03)
# ==============================================================================
with tab_ag2:
    st.subheader("Agent 2 — Company Brain & Lineage Investigator (Track 03 Focus)")
    st.markdown("Specialized in architectural decisions (ADRs), superseded lineage, Slack discussions, and team code ownership.")

    b_col1, b_col2 = st.columns([1, 1])
    with b_col1:
        st.markdown("#### 🏛️ ADR Lineage & Superseded Chains")
        st.caption("Query: `(:Decision)-[:SUPERSEDES]->(:Decision)`")
        adr_cypher = """
        MATCH (new_d:Decision)
        OPTIONAL MATCH (new_d)-[:SUPERSEDES]->(old_d:Decision)
        OPTIONAL MATCH (new_d)-[:GOVERNS]->(s:Service)
        RETURN new_d.id AS active_adr, new_d.title AS title, new_d.status AS status,
               old_d.id AS supersedes, s.name AS governs_service
        """
        adr_res = manager.run_cypher(tenant_id=current_tenant, query=adr_cypher, read_only=True)
        if adr_res.success and adr_res.data:
            st.dataframe(pd.DataFrame(adr_res.data), use_container_width=True, hide_index=True)

        st.markdown("#### 💬 Linked Slack Warnings & Jira Tickets")
        st.markdown("""
        - **Slack Thread `[SLACK-991]` (`#payments-eng`):**
          > *"Priya warned that raising retry threads without the circuit breaker flag will exhaust auth-token-service connections during traffic bursts."*
        - **Jira Ticket `[JIRA-1904]`:** *"Increase ledger throughput for flash sale"* linked to `[PR-482]` and commit `[a8f921c]`.
        """)

    with b_col2:
        st.markdown("#### 👥 Ownership & Expertise (Who Owns What / Who Knows What)")
        ownership_cypher = """
        MATCH (e:Engineer)-[:MEMBER_OF]->(t:Team)-[:OWNS]->(s:Service)
        OPTIONAL MATCH (e)-[exp:EXPERT_IN]->(s)
        RETURN e.name AS engineer, e.role AS role, t.name AS team, s.name AS service,
               exp.confidence AS expert_confidence
        ORDER BY s.name ASC
        """
        own_res = manager.run_cypher(tenant_id=current_tenant, query=ownership_cypher, read_only=True)
        if own_res.success and own_res.data:
            st.dataframe(pd.DataFrame(own_res.data), use_container_width=True, hide_index=True)


# ==============================================================================
# TAB 5: AGENT 3: PERSISTENT MEMORY & GRAPH ACTIONS (TRACK 02)
# ==============================================================================
with tab_ag3:
    st.subheader("Agent 3 — Memory & Action Coordinator (Track 02 Focus)")
    st.markdown("Specialized in persistent episodic memories, cross-session recall, and autonomous graph actions.")

    m_col1, m_col2 = st.columns([1, 1])
    with m_col1:
        st.markdown("#### 🔄 Agent Coordination & Handoff Chain")
        st.caption("Query: `MATCH (sess:Session)<-[:PART_OF_SESSION]-(r:AgentRun) ...`")
        handoffs_query = """
        MATCH (sess:Session)<-[:PART_OF_SESSION]-(r1:AgentRun)-[h:HANDED_OFF_TO]->(r2:AgentRun)
        RETURN sess.id AS session, r1.agent_name AS from_agent, r2.agent_name AS to_agent,
               r1.findings AS findings, h.timestamp AS timestamp
        ORDER BY h.timestamp DESC
        LIMIT 10
        """
        ho_res = manager.run_cypher(tenant_id=current_tenant, query=handoffs_query, read_only=True)
        if ho_res.success and ho_res.data:
            st.dataframe(pd.DataFrame(ho_res.data), use_container_width=True, hide_index=True)
        else:
            st.info("Run an investigation in Tab 2 to record multi-agent handoffs in FalkorDB.")

    with m_col2:
        st.markdown("#### 🔮 Cross-Session Memory Simulator")
        st.markdown("Demonstrates that memories written during **Session #1** directly inform and prevent outages in **Session #2**.")
        if st.button("⚡ Simulate Next-Day Session #2 Audit"):
            mem_recall = recall_agent_memories(manager=manager, tenant_id=current_tenant, service_name="payment-ledger")
            st.success("Session #2 successfully queried FalkorDB memory for 'payment-ledger'!")
            st.json({
                "episodic_memories_recalled": len(mem_recall.get("episodic_memories", [])),
                "procedural_runbooks_recalled": len(mem_recall.get("procedural_runbooks", [])),
                "semantic_facts_recalled": len(mem_recall.get("semantic_facts", [])),
                "active_mitigation_rule": mem_recall.get("semantic_facts", [{}])[0].get("rule") if mem_recall.get("semantic_facts") else None,
            })

    st.markdown("---")
    st.markdown("### 💻 Custom OpenCypher Console (Query FalkorDB Cloud Directly)")
    st.caption("Write and execute any OpenCypher query directly against your live FalkorDB Cloud database.")
    
    sample_cyphers = [
        "MATCH (n) RETURN labels(n) AS label, count(n) AS count ORDER BY count DESC",
        "MATCH (s:Service)-[r:DEPENDS_ON]->(d:Service) RETURN s.name AS source, r.criticality AS criticality, d.name AS target",
        "MATCH (c:Commit)-[v:VIOLATES]->(d:Decision) RETURN c.sha AS commit, c.message AS message, d.id AS violated_adr, v.reason AS reason",
        "MATCH (m:EpisodicMemory) RETURN m.id AS memory_id, m.summary AS summary, m.confidence AS confidence",
    ]
    chosen_sample = st.selectbox("Quick Cypher Templates:", sample_cyphers)
    cypher_input = st.text_area("OpenCypher Query:", value=chosen_sample, height=75)
    
    if st.button("▶ Execute Cypher on FalkorDB Cloud", type="secondary"):
        start_q = time.perf_counter()
        q_result = manager.run_cypher(tenant_id=current_tenant, query=cypher_input)
        lat_ms = round((time.perf_counter() - start_q) * 1000, 2)
        if q_result.success:
            st.success(f"Executed in {lat_ms} ms (Rows: {q_result.row_count})")
            if q_result.data:
                st.dataframe(pd.DataFrame(q_result.data), use_container_width=True)
            else:
                st.info("Query executed successfully with empty result set.")
        else:
            st.error(f"Query Error: {q_result.error}")
