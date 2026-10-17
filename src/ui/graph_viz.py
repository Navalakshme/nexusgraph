"""NexusGraph Interactive Graph Visualizer using PyVis.

Renders dark-themed, high-contrast, interactive network graphs with:
- Color-coded node classifications (Incident=Red, Service=Cyan, Decision=Purple,
  Engineer=Emerald, Memory/Runbook=Gold, Commit=Amber)
- Glowing highlighted traversed edges representing multi-agent reasoning paths
- Rich hover tooltips with node properties and metadata
- Physics stabilization suited for microservice and knowledge topologies
"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple
from pyvis.network import Network
from src.db.falkor_client import FalkorGraphManager, get_db_manager

# Node Category Color Palette (High-contrast dark mode)
NODE_COLORS = {
    "Incident": {"background": "#FF5252", "border": "#FF1744", "highlight": "#FF8A80"},
    "Service": {"background": "#00E5FF", "border": "#00B0FF", "highlight": "#80D8FF"},
    "Commit": {"background": "#FFB300", "border": "#FFA000", "highlight": "#FFE082"},
    "PullRequest": {"background": "#FF9100", "border": "#FF6D00", "highlight": "#FFD180"},
    "Ticket": {"background": "#FB8C00", "border": "#EF6C00", "highlight": "#FFE0B2"},
    "Decision": {"background": "#B388FF", "border": "#7C4DFF", "highlight": "#D1C4E9"},
    "Engineer": {"background": "#00E676", "border": "#00C853", "highlight": "#B9F6CA"},
    "Team": {"background": "#1DE9B6", "border": "#00BFA5", "highlight": "#A7FFEB"},
    "EpisodicMemory": {"background": "#FFD700", "border": "#FFC107", "highlight": "#FFF9C4"},
    "SemanticFact": {"background": "#FFCA28", "border": "#FFB300", "highlight": "#FFF8E1"},
    "ProceduralRunbook": {"background": "#FFC400", "border": "#FFAB00", "highlight": "#FFFDE7"},
    "AgentRun": {"background": "#40C4FF", "border": "#00B0FF", "highlight": "#80D8FF"},
    "Session": {"background": "#7C4DFF", "border": "#651FFF", "highlight": "#B388FF"},
    "RemediationAction": {"background": "#69F0AE", "border": "#00E676", "highlight": "#C8E6C9"},
    "SlackThread": {"background": "#EA80FC", "border": "#E040FB", "highlight": "#F8BBD0"},
}

DEFAULT_COLOR = {"background": "#90CAF9", "border": "#42A5F5", "highlight": "#BBDEFB"}

NODE_SHAPES = {
    "Incident": "diamond",
    "Service": "box",
    "Commit": "triangle",
    "PullRequest": "triangleDown",
    "Ticket": "square",
    "Decision": "star",
    "Engineer": "circle",
    "Team": "hexagon",
    "EpisodicMemory": "ellipse",
    "SemanticFact": "ellipse",
    "ProceduralRunbook": "box",
    "AgentRun": "dot",
    "Session": "database",
    "RemediationAction": "box",
    "SlackThread": "dot",
}


def _infer_node_type(node_id: str, label: Optional[str] = None) -> str:
    """Infer primary node category from label or ID prefix."""
    if label and label in NODE_COLORS:
        return label

    node_str = str(node_id).upper()
    if node_str.startswith("INC-"):
        return "Incident"
    if node_str.startswith("ADR-"):
        return "Decision"
    if node_str.startswith("PR-"):
        return "PullRequest"
    if node_str.startswith("JIRA-") or node_str.startswith("TK-"):
        return "Ticket"
    if node_str.startswith("MEM-"):
        return "EpisodicMemory"
    if node_str.startswith("FACT-"):
        return "SemanticFact"
    if node_str.startswith("RUNBOOK-") or node_str.startswith("RB-"):
        return "ProceduralRunbook"
    if node_str.startswith("RUN_"):
        return "AgentRun"
    if node_str.startswith("SESS_"):
        return "Session"
    if node_str.startswith("ACT-"):
        return "RemediationAction"
    if node_str.startswith("SLACK-"):
        return "SlackThread"
    if len(node_id) == 7 and all(c in "0123456789abcdefABCDEF" for c in node_id):
        return "Commit"

    # Default to Service for hyphenated microservice names
    if "-" in str(node_id) and not any(c.isupper() for c in str(node_id)):
        return "Service"

    return label or "Service"


def render_pyvis_network(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    highlight_edges: Optional[Set[Tuple[str, str, str]]] = None,
    height: str = "520px",
) -> str:
    """Generate interactive PyVis dark-mode HTML network graph string.

    Args:
        nodes: List of node dictionaries with {id, label, type, properties}
        edges: List of edge dictionaries with {source, target, label, properties}
        highlight_edges: Optional set of (source, relationship, target) tuples to highlight
        height: CSS height string

    Returns:
        Complete self-contained HTML string.
    """
    net = Network(
        height=height,
        width="100%",
        bgcolor="#0e1117",
        font_color="#ECEFF1",
        directed=True,
    )

    highlight_edges = highlight_edges or set()
    added_nodes = set()

    for n in nodes:
        node_id = str(n.get("id"))
        if node_id in added_nodes:
            continue
        added_nodes.add(node_id)

        node_type = _infer_node_type(node_id, n.get("type") or n.get("label"))
        color_info = NODE_COLORS.get(node_type, DEFAULT_COLOR)
        shape = NODE_SHAPES.get(node_type, "dot")
        display_label = n.get("display_name") or n.get("label") or node_id

        # Format hover tooltip
        props = n.get("properties") or {}
        prop_lines = [f"<b>{k}:</b> {v}" for k, v in props.items() if k not in ("_type", "id")]
        title = f"<div style='font-family:sans-serif;'><b>[{node_type}] {display_label}</b><br/>" + "<br/>".join(prop_lines[:5]) + "</div>"

        net.add_node(
            node_id,
            label=display_label,
            title=title,
            color=color_info["background"],
            borderWidth=2,
            borderWidthSelected=4,
            shape=shape,
            size=22 if node_type in ("Incident", "Decision", "Service") else 16,
            font={"size": 13, "color": "#FFFFFF", "face": "Segoe UI, sans-serif"},
        )

    added_edges = set()
    for e in edges:
        src = str(e.get("source"))
        dest = str(e.get("target"))
        rel = str(e.get("label") or e.get("relationship") or "RELATED_TO")

        if src not in added_nodes:
            net.add_node(src, label=src, color=DEFAULT_COLOR["background"], shape="dot")
            added_nodes.add(src)
        if dest not in added_nodes:
            net.add_node(dest, label=dest, color=DEFAULT_COLOR["background"], shape="dot")
            added_nodes.add(dest)

        edge_key = (src, rel, dest)
        if edge_key in added_edges:
            continue
        added_edges.add(edge_key)

        is_highlighted = edge_key in highlight_edges or (src, dest) in [(h[0], h[2]) for h in highlight_edges]
        props = e.get("properties") or {}
        edge_title = f"<div style='font-family:sans-serif;'><b>{rel}</b><br/>" + "<br/>".join(f"{k}: {v}" for k, v in props.items()) + "</div>"

        if is_highlighted:
            net.add_edge(
                src,
                dest,
                label=rel,
                title=edge_title,
                color="#FFD700",  # Bright gold for traversed agent paths
                width=3.8,
                arrows={"to": {"enabled": True, "scaleFactor": 1.1}},
                font={"color": "#FFD700", "size": 11, "strokeWidth": 2, "strokeColor": "#0e1117"},
                dashes=False,
            )
        else:
            net.add_edge(
                src,
                dest,
                label=rel,
                title=edge_title,
                color="#475569",  # Slate gray for normal edges
                width=1.5,
                arrows={"to": {"enabled": True, "scaleFactor": 0.8}},
                font={"color": "#94A3B8", "size": 9, "strokeWidth": 1, "strokeColor": "#0e1117"},
            )

    # Configure physics for smooth layout and interactive navigation
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -60,
          "centralGravity": 0.012,
          "springLength": 110,
          "springConstant": 0.08,
          "damping": 0.4
        },
        "maxVelocity": 45,
        "solver": "forceAtlas2Based",
        "stabilization": { "iterations": 120 }
      },
      "interaction": {
        "hover": true,
        "zoomView": true,
        "dragView": true,
        "navigationButtons": true
      }
    }
    """)

    return net.generate_html()


def build_pyvis_from_traversed_paths(traversed_paths: List[Dict[str, Any]], height: str = "520px") -> str:
    """Build PyVis visualization focused entirely on the agent's traversed paths."""
    if not traversed_paths:
        return f"""
        <div style="height: {height}; display: flex; align-items: center; justify-content: center; background-color: #0d1117; color: #8b949e; border: 1px dashed #30363d; border-radius: 8px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; text-align: center; padding: 20px;">
            <div>
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#58a6ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 12px; opacity: 0.8;">
                    <circle cx="18" cy="5" r="3"></circle>
                    <circle cx="6" cy="12" r="3"></circle>
                    <circle cx="18" cy="19" r="3"></circle>
                    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
                </svg>
                <h4 style="color: #c9d1d9; margin: 0 0 6px 0; font-size: 15px;">No Graph Paths Traversed Yet</h4>
                <p style="font-size: 13px; max-width: 380px; margin: 0 auto; color: #8b949e; line-height: 1.4;">
                    Run an investigation or graph query to visualize live multi-hop reasoning paths traversed in FalkorDB.
                </p>
            </div>
        </div>
        """

    nodes_map: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    highlight_edges: Set[Tuple[str, str, str]] = set()

    for p in traversed_paths:
        src = str(p.get("source"))
        dest = str(p.get("target"))
        rel = str(p.get("relationship", "CONNECTED_TO"))
        src_label = p.get("source_label")
        dest_label = p.get("target_label")
        props = p.get("properties") or {}

        if src not in nodes_map:
            nodes_map[src] = {"id": src, "label": src, "type": src_label, "properties": {}}
        if dest not in nodes_map:
            nodes_map[dest] = {"id": dest, "label": dest, "type": dest_label, "properties": {}}

        edges.append({"source": src, "target": dest, "label": rel, "properties": props})
        highlight_edges.add((src, rel, dest))

    return render_pyvis_network(
        nodes=list(nodes_map.values()),
        edges=edges,
        highlight_edges=highlight_edges,
        height=height,
    )


def build_pyvis_from_falkor_graph(
    manager: Optional[FalkorGraphManager] = None,
    tenant_id: str = "acme_prod",
    highlight_paths: Optional[List[Dict[str, Any]]] = None,
    max_nodes: int = 50,
    height: str = "550px",
) -> str:
    """Query FalkorDB for tenant subgraph and render with PyVis."""
    manager = manager or get_db_manager()
    clean_tenant = manager._sanitize_tenant_id(tenant_id)

    query = f"""
    MATCH (n)
    OPTIONAL MATCH (n)-[r]->(m)
    RETURN n, r, m
    LIMIT {max_nodes}
    """
    res = manager.run_cypher(tenant_id=clean_tenant, query=query, read_only=True)

    nodes_map: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    highlight_set: Set[Tuple[str, str, str]] = set()

    if highlight_paths:
        for p in highlight_paths:
            highlight_set.add((str(p.get("source")), str(p.get("relationship")), str(p.get("target"))))

    if res.success and res.data:
        for row in res.data:
            node_n = row.get("n")
            rel_r = row.get("r")
            node_m = row.get("m")

            if node_n:
                n_id = str(node_n.get("properties", {}).get("name") or node_n.get("properties", {}).get("id") or node_n.get("id"))
                n_lbl = node_n.get("labels", [""])[0] if node_n.get("labels") else ""
                if n_id not in nodes_map:
                    nodes_map[n_id] = {
                        "id": n_id,
                        "label": n_id,
                        "type": n_lbl,
                        "properties": node_n.get("properties", {}),
                    }

            if node_m:
                m_id = str(node_m.get("properties", {}).get("name") or node_m.get("properties", {}).get("id") or node_m.get("id"))
                m_lbl = node_m.get("labels", [""])[0] if node_m.get("labels") else ""
                if m_id not in nodes_map:
                    nodes_map[m_id] = {
                        "id": m_id,
                        "label": m_id,
                        "type": m_lbl,
                        "properties": node_m.get("properties", {}),
                    }

            if node_n and node_m and rel_r:
                src_id = str(node_n.get("properties", {}).get("name") or node_n.get("properties", {}).get("id") or node_n.get("id"))
                dest_id = str(node_m.get("properties", {}).get("name") or node_m.get("properties", {}).get("id") or node_m.get("id"))
                rel_type = rel_r.get("relation") or "CONNECTED"
                edges.append({
                    "source": src_id,
                    "target": dest_id,
                    "label": rel_type,
                    "properties": rel_r.get("properties", {}),
                })

    # If graph is empty or disconnected, return informative empty state
    if not nodes_map:
        return f"""
        <div style="height: {height}; display: flex; align-items: center; justify-content: center; background-color: #0d1117; color: #8b949e; border: 1px dashed #30363d; border-radius: 8px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; text-align: center; padding: 20px;">
            <div>
                <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#f85149" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 12px;">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <h4 style="color: #c9d1d9; margin: 0 0 6px 0; font-size: 16px;">No Active Graph Data in FalkorDB</h4>
                <p style="font-size: 13px; max-width: 440px; margin: 0 auto; color: #8b949e; line-height: 1.5;">
                    NexusGraph operates <strong>strictly on connected FalkorDB Cloud data</strong>. 
                    No graph nodes exist in tenant <code style="color: #58a6ff; background: #161b22; padding: 2px 6px; border-radius: 4px;">nexus_{tenant_id}</code>.
                    <br/><br/>
                    Ensure FalkorDB Cloud credentials are configured in the sidebar, then click 
                    <strong style="color: #3fb950;">'⚡ Initialize / Reset Enterprise Graph'</strong> to seed the database.
                </p>
            </div>
        </div>
        """

    return render_pyvis_network(
        nodes=list(nodes_map.values()),
        edges=edges,
        highlight_edges=highlight_set,
        height=height,
    )

