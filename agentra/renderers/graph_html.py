"""Graph HTML renderer — self-contained interactive call-graph visualization.

Produces a single HTML file with a vis.js Network force-directed graph.
Requires an internet connection to load vis.js from CDN when opened in a browser.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_KIND_COLORS = {
    "function": "#58a6ff",
    "method":   "#79c0ff",
    "class":    "#3fb950",
    "import":   "#6e7681",
    "variable": "#d29922",
}
_KIND_SHAPES = {
    "function": "dot",
    "method":   "dot",
    "class":    "diamond",
    "import":   "square",
    "variable": "triangle",
}
_DEFAULT_COLOR = "#8b949e"
_DEFAULT_SHAPE = "dot"


def _node_size(in_degree: int) -> int:
    """Scale node size logarithmically by in-degree."""
    if in_degree == 0:
        return 8
    return min(8 + in_degree * 3, 36)


def _node_mass(in_degree: int) -> float:
    """Higher-degree nodes get more mass so they push neighbours outward."""
    return max(1.0, 1.0 + in_degree * 0.3)


def render_graph_html(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    meta: dict[str, Any],
) -> str:
    """Return a self-contained HTML string visualizing the call graph.

    Args:
        nodes: list of {"id", "name", "kind", "path", "line", "in_degree"}
        edges: list of {"from", "to", "kind"}
        meta:  {"total_nodes", "total_edges", "files", "truncated", "max_nodes"}
    """
    # Build vis.js node/edge datasets
    vis_nodes = []
    for n in nodes:
        kind = n.get("kind", "")
        color = _KIND_COLORS.get(kind, _DEFAULT_COLOR)
        shape = _KIND_SHAPES.get(kind, _DEFAULT_SHAPE)
        in_deg = n.get("in_degree", 0)
        size = _node_size(in_deg)
        short_path = Path(n.get("path", "")).name
        vis_nodes.append({
            "id": n["id"],
            "label": n["name"],
            "title": f"{n['name']}<br>{n.get('kind','')}<br>{n.get('path','')}: L{n.get('line',0)}",
            "color": {"background": color, "border": color, "highlight": {"background": "#fff", "border": color}},
            "shape": shape,
            "size": size,
            "mass": _node_mass(in_deg),
            "font": {"color": "#e6edf3", "size": 11},
            "_kind": kind,
            "_file": short_path,
            "_path": n.get("path", ""),
            "_in_degree": in_deg,
        })

    vis_edges = []
    for e in edges:
        vis_edges.append({
            "from": e["from"],
            "to": e["to"],
            "arrows": "to",
            "color": {"color": "#30363d", "highlight": "#58a6ff"},
            "width": 1,
        })

    nodes_js = json.dumps(vis_nodes)
    edges_js = json.dumps(vis_edges)
    meta_js = json.dumps(meta)

    truncated_banner = ""
    if meta.get("truncated"):
        truncated_banner = (
            f'<div class="banner-warn">Graph truncated to {meta.get("max_nodes")} nodes '
            f'(total: {meta.get("total_nodes")}). Use <code>--max-nodes</code> to adjust.</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agentra — Code Graph</title>
<script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/dist/vis-network.min.js"></script>
<style>
:root {{
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --text-dim: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --red: #f85149; --yellow: #d29922;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
       background: var(--bg); color: var(--text); display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}
header {{ padding: .75rem 1.25rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 1rem; flex-shrink: 0; }}
header h1 {{ font-size: 1.1rem; font-weight: 600; }}
header .subtitle {{ color: var(--text-dim); font-size: .85rem; }}
.layout {{ display: flex; flex: 1; overflow: hidden; }}
#sidebar {{
  width: 280px; flex-shrink: 0; background: var(--surface); border-right: 1px solid var(--border);
  overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 1rem;
}}
#graph-container {{ flex: 1; position: relative; }}
#graph {{ width: 100%; height: 100%; }}
.section-title {{ font-size: .75rem; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--text-dim); margin-bottom: .5rem; }}
.stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; }}
.stat {{ background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: .5rem; text-align: center; }}
.stat-value {{ font-size: 1.25rem; font-weight: 700; color: var(--accent); }}
.stat-label {{ font-size: .7rem; color: var(--text-dim); }}
.legend {{ display: flex; flex-direction: column; gap: .35rem; }}
.legend-item {{ display: flex; align-items: center; gap: .5rem; font-size: .8rem; }}
.legend-dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}
.legend-diamond {{ width: 12px; height: 12px; transform: rotate(45deg); flex-shrink: 0; }}
.legend-square {{ width: 12px; height: 12px; flex-shrink: 0; }}
input[type=text] {{
  width: 100%; padding: .4rem .6rem; background: var(--bg); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); font-size: .85rem; outline: none;
}}
input[type=text]:focus {{ border-color: var(--accent); }}
select {{
  width: 100%; padding: .4rem .6rem; background: var(--bg); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); font-size: .85rem; outline: none;
}}
.hotspot-list {{ display: flex; flex-direction: column; gap: .3rem; max-height: 200px; overflow-y: auto; }}
.hotspot-item {{ background: var(--bg); border: 1px solid var(--border); border-radius: 5px; padding: .35rem .5rem; font-size: .78rem; cursor: pointer; }}
.hotspot-item:hover {{ border-color: var(--accent); color: var(--accent); }}
.hotspot-badge {{ float: right; background: rgba(88,166,255,.15); color: var(--accent); border-radius: 10px; padding: 1px 6px; font-size: .7rem; }}
#node-detail {{ background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: .75rem; font-size: .8rem; line-height: 1.6; display: none; }}
#node-detail.active {{ display: block; }}
#node-detail .detail-name {{ font-weight: 600; font-size: .95rem; color: var(--accent); word-break: break-all; }}
#node-detail .detail-meta {{ color: var(--text-dim); margin-top: .2rem; }}
.btn {{ padding: .35rem .75rem; background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
        color: var(--text); font-size: .8rem; cursor: pointer; }}
.btn:hover {{ border-color: var(--accent); color: var(--accent); }}
.btn-row {{ display: flex; gap: .5rem; }}
.banner-warn {{ background: rgba(210,153,34,.15); border: 1px solid var(--yellow); border-radius: 6px;
                color: var(--yellow); font-size: .8rem; padding: .5rem .75rem; }}
#loading {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
            background: var(--bg); color: var(--text-dim); font-size: .9rem; z-index: 10; }}
</style>
</head>
<body>

<header>
  <h1>Agentra — Code Graph</h1>
  <span class="subtitle" id="header-meta">Loading…</span>
</header>

<div class="layout">
  <div id="sidebar">

    <div>
      <div class="section-title">Stats</div>
      <div class="stat-grid" id="stats"></div>
    </div>

    {truncated_banner}

    <div>
      <div class="section-title">Filter</div>
      <input type="text" id="filter-name" placeholder="Search by name…" />
      <select id="filter-kind" style="margin-top:.4rem">
        <option value="">All kinds</option>
        <option value="function">function</option>
        <option value="method">method</option>
        <option value="class">class</option>
        <option value="import">import</option>
        <option value="variable">variable</option>
      </select>
    </div>

    <div>
      <div class="section-title">Legend</div>
      <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background:#58a6ff"></div> function</div>
        <div class="legend-item"><div class="legend-dot" style="background:#79c0ff"></div> method</div>
        <div class="legend-item"><div class="legend-diamond" style="background:#3fb950"></div> class</div>
        <div class="legend-item"><div class="legend-square" style="background:#6e7681"></div> import</div>
        <div class="legend-item"><div class="legend-dot" style="background:#d29922"></div> variable</div>
      </div>
      <div style="margin-top:.5rem;font-size:.75rem;color:var(--text-dim)">Node size = call-in count</div>
    </div>

    <div>
      <div class="section-title">Top Hotspots</div>
      <div class="hotspot-list" id="hotspot-list"></div>
    </div>

    <div>
      <div class="section-title">Selected Node</div>
      <div id="node-detail">
        <div class="detail-name" id="d-name">—</div>
        <div class="detail-meta" id="d-meta"></div>
      </div>
    </div>

    <div class="btn-row">
      <button class="btn" id="btn-fit">Fit all</button>
      <button class="btn" id="btn-reset">Reset filter</button>
    </div>

  </div>

  <div id="graph-container">
    <div id="loading">Building graph layout…</div>
    <div id="graph"></div>
  </div>
</div>

<script>
const RAW_NODES = {nodes_js};
const RAW_EDGES = {edges_js};
const META = {meta_js};

// ── Stats ──────────────────────────────────────────────────────────────
const statsEl = document.getElementById('stats');
const headerMeta = document.getElementById('header-meta');
const statDefs = [
  ['Nodes', META.displayed_nodes || RAW_NODES.length],
  ['Edges', META.displayed_edges || RAW_EDGES.length],
  ['Files', META.files || 0],
  ['Hotspots', META.hotspot_count || 0],
];
statDefs.forEach(([label, value]) => {{
  statsEl.innerHTML += `<div class="stat"><div class="stat-value">${{value}}</div><div class="stat-label">${{label}}</div></div>`;
}});
headerMeta.textContent = `${{META.displayed_nodes || RAW_NODES.length}} nodes · ${{META.displayed_edges || RAW_EDGES.length}} edges · ${{META.files || 0}} files`;

// ── Hotspots sidebar ───────────────────────────────────────────────────
const hotspotEl = document.getElementById('hotspot-list');
const _seenLabels = new Set();
const hotspots = [...RAW_NODES]
  .filter(n => n._in_degree > 0 && !n.label.startsWith('__'))
  .sort((a, b) => b._in_degree - a._in_degree)
  .filter(n => {{ if (_seenLabels.has(n.label)) return false; _seenLabels.add(n.label); return true; }})
  .slice(0, 15);
hotspots.forEach(n => {{
  const el = document.createElement('div');
  el.className = 'hotspot-item';
  el.innerHTML = `${{n.label}}<span class="hotspot-badge">${{n._in_degree}}</span>`;
  el.onclick = () => network && network.focus(n.id, {{scale: 1.5, animation: true}});
  hotspotEl.appendChild(el);
}});

// ── vis.js Network ─────────────────────────────────────────────────────
let allNodes = new vis.DataSet(RAW_NODES);
let allEdges = new vis.DataSet(RAW_EDGES);

const options = {{
  physics: {{
    solver: 'forceAtlas2Based',
    forceAtlas2Based: {{
      gravitationalConstant: -120,
      centralGravity: 0.001,
      springLength: 220,
      springConstant: 0.04,
      damping: 0.6,
      avoidOverlap: 1.0,
    }},
    stabilization: {{ iterations: 400, updateInterval: 25 }},
  }},
  interaction: {{ hover: true, tooltipDelay: 150, hideEdgesOnDrag: true }},
  edges: {{ smooth: {{ type: 'dynamic' }}, color: {{ opacity: 0.35 }} }},
  nodes: {{ borderWidth: 1, mass: 2 }},
}};

const container = document.getElementById('graph');
const network = new vis.Network(container, {{ nodes: allNodes, edges: allEdges }}, options);

network.once('stabilizationIterationsDone', () => {{
  document.getElementById('loading').style.display = 'none';
  network.fit();
}});

// ── Node click detail ──────────────────────────────────────────────────
const nodeDetail = document.getElementById('node-detail');
network.on('click', params => {{
  if (params.nodes.length === 0) return;
  const id = params.nodes[0];
  const node = RAW_NODES.find(n => n.id === id);
  if (!node) return;
  nodeDetail.classList.add('active');
  document.getElementById('d-name').textContent = node.label;
  document.getElementById('d-meta').innerHTML =
    `Kind: <strong>${{node._kind}}</strong><br>` +
    `File: <strong>${{node._file}}</strong><br>` +
    `Callers: <strong>${{node._in_degree}}</strong>`;
}});

// ── Filter ─────────────────────────────────────────────────────────────
function applyFilter() {{
  const name = document.getElementById('filter-name').value.toLowerCase();
  const kind = document.getElementById('filter-kind').value;

  const visibleIds = new Set();
  RAW_NODES.forEach(n => {{
    const nameMatch = !name || n.label.toLowerCase().includes(name);
    const kindMatch = !kind || n._kind === kind;
    if (nameMatch && kindMatch) visibleIds.add(n.id);
  }});

  const updates = RAW_NODES.map(n => ({{
    id: n.id,
    hidden: !visibleIds.has(n.id),
  }}));
  allNodes.update(updates);

  const edgeUpdates = RAW_EDGES.map(e => ({{
    id: e.id || `${{e.from}}-${{e.to}}`,
    hidden: !visibleIds.has(e.from) || !visibleIds.has(e.to),
  }}));
  allEdges.update(edgeUpdates);
}}

document.getElementById('filter-name').addEventListener('input', applyFilter);
document.getElementById('filter-kind').addEventListener('change', applyFilter);

document.getElementById('btn-fit').addEventListener('click', () => network.fit({{animation: true}}));
document.getElementById('btn-reset').addEventListener('click', () => {{
  document.getElementById('filter-name').value = '';
  document.getElementById('filter-kind').value = '';
  applyFilter();
  network.fit({{animation: true}});
}});
</script>
</body>
</html>"""


def write_graph_html(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    meta: dict[str, Any],
    output_path: Path,
) -> None:
    """Render and write the graph HTML to disk."""
    html = render_graph_html(nodes, edges, meta)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
