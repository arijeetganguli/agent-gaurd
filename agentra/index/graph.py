"""GraphQueryEngine — networkx-based call-graph queries over the SQLite code index."""

from __future__ import annotations

from pathlib import Path

from agentra.index.engine import CodeIndexEngine


class GraphQueryEngine:
    """
    Loads the symbol edge table from SQLite into a networkx DiGraph
    on demand and exposes higher-level graph queries.

    networkx is an optional enterprise dependency.  All public methods
    degrade gracefully if networkx is not installed.
    """

    def __init__(self, index_engine: CodeIndexEngine) -> None:
        self._engine = index_engine
        self._graph: object | None = None  # nx.DiGraph when loaded

    def _require_nx(self):
        try:
            import networkx as nx  # type: ignore[import]
            return nx
        except ImportError as e:
            raise ImportError(
                "networkx is required for graph queries. "
                "Install it with: pip install agentra[enterprise]"
            ) from e

    def _load_graph(self):
        nx = self._require_nx()
        G = nx.DiGraph()

        # Add symbol nodes
        rows = self._engine._conn.execute(
            "SELECT s.id, s.name, s.kind, f.path FROM symbols s JOIN files f ON s.file_id = f.id"
        ).fetchall()
        for sym_id, name, kind, path in rows:
            G.add_node(sym_id, name=name, kind=kind, path=path)

        # Add call edges
        edges = self._engine._conn.execute(
            "SELECT src_symbol_id, dst_name, edge_type FROM edges"
        ).fetchall()

        # Build name → id lookup
        name_to_ids: dict[str, list[int]] = {}
        for sym_id, name, _kind, _path in rows:
            name_to_ids.setdefault(name, []).append(sym_id)

        for src_id, dst_name, edge_type in edges:
            for dst_id in name_to_ids.get(dst_name, []):
                G.add_edge(src_id, dst_id, kind=edge_type)

        self._graph = G
        return G

    def build_call_graph(self):
        """Build and return the call graph as a networkx DiGraph."""
        return self._load_graph()

    def find_hotspots(self, top_n: int = 10) -> list[tuple[str, str, int]]:
        """Return the top-N most-called symbols: (name, file_path, in_degree)."""
        G = self._load_graph()
        nx = self._require_nx()
        ranked = sorted(G.in_degree(), key=lambda x: x[1], reverse=True)[:top_n]
        result = []
        for node_id, in_deg in ranked:
            if in_deg == 0:
                continue
            attrs = G.nodes[node_id]
            result.append((attrs.get("name", "?"), attrs.get("path", "?"), in_deg))
        return result

    def find_orphans(self) -> list[tuple[str, str]]:
        """Return symbols with no callers and no callees: (name, file_path)."""
        G = self._load_graph()
        result = []
        for node_id in G.nodes:
            if G.in_degree(node_id) == 0 and G.out_degree(node_id) == 0:
                attrs = G.nodes[node_id]
                name = attrs.get("name", "?")
                # Skip imports and very short names
                if len(name) > 3 and attrs.get("kind") not in ("import",):
                    result.append((name, attrs.get("path", "?")))
        return result[:50]

    def find_cycles(self) -> list[list[str]]:
        """Detect circular dependencies. Returns list of cycles (symbol names)."""
        G = self._load_graph()
        nx = self._require_nx()
        try:
            cycles_raw = list(nx.simple_cycles(G))
        except Exception:  # noqa: BLE001
            return []

        result = []
        for cycle in cycles_raw[:20]:
            names = [G.nodes[n].get("name", "?") for n in cycle]
            result.append(names)
        return result
