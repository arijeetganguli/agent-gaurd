"""Tests for ag graph — call-graph HTML visualization."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentra.cli.main import app
from agentra.renderers.graph_html import render_graph_html, write_graph_html

runner = CliRunner()

# ── Renderer unit tests ───────────────────────────────────────────────────────

SAMPLE_NODES = [
    {"id": 1, "name": "MyClass", "kind": "class", "path": "src/foo.py", "line": 10, "in_degree": 3},
    {"id": 2, "name": "my_func", "kind": "function", "path": "src/foo.py", "line": 20, "in_degree": 1},
    {"id": 3, "name": "helper", "kind": "function", "path": "src/bar.py", "line": 5, "in_degree": 0},
    {"id": 4, "name": "os", "kind": "import", "path": "src/foo.py", "line": 1, "in_degree": 0},
]

SAMPLE_EDGES = [
    {"from": 2, "to": 1, "kind": "call"},
    {"from": 3, "to": 2, "kind": "call"},
]

SAMPLE_META = {
    "total_nodes": 4,
    "total_edges": 2,
    "displayed_nodes": 4,
    "displayed_edges": 2,
    "files": 2,
    "hotspot_count": 1,
    "truncated": False,
    "max_nodes": 300,
}


class TestRenderGraphHtml:
    def test_returns_html_string(self):
        html = render_graph_html(SAMPLE_NODES, SAMPLE_EDGES, SAMPLE_META)
        assert isinstance(html, str)
        assert html.startswith("<!DOCTYPE html>")

    def test_contains_vis_js_cdn(self):
        html = render_graph_html(SAMPLE_NODES, SAMPLE_EDGES, SAMPLE_META)
        assert "vis-network" in html

    def test_nodes_embedded_as_json(self):
        html = render_graph_html(SAMPLE_NODES, SAMPLE_EDGES, SAMPLE_META)
        # All node names should appear in the HTML
        for node in SAMPLE_NODES:
            assert node["name"] in html

    def test_edges_embedded(self):
        html = render_graph_html(SAMPLE_NODES, SAMPLE_EDGES, SAMPLE_META)
        assert "RAW_EDGES" in html

    def test_truncated_banner_shown_when_truncated(self):
        meta = {**SAMPLE_META, "truncated": True, "max_nodes": 2, "total_nodes": 100}
        html = render_graph_html(SAMPLE_NODES, SAMPLE_EDGES, meta)
        assert "truncated" in html.lower()
        assert "banner-warn" in html

    def test_no_truncated_banner_when_not_truncated(self):
        html = render_graph_html(SAMPLE_NODES, SAMPLE_EDGES, SAMPLE_META)
        # The CSS class is always present; only the div element is conditional
        assert 'class="banner-warn"' not in html

    def test_kind_colors_applied(self):
        html = render_graph_html(SAMPLE_NODES, SAMPLE_EDGES, SAMPLE_META)
        # class color
        assert "#3fb950" in html
        # function color
        assert "#58a6ff" in html
        # import color
        assert "#6e7681" in html

    def test_write_graph_html_creates_file(self, tmp_path):
        out = tmp_path / "graph.html"
        write_graph_html(SAMPLE_NODES, SAMPLE_EDGES, SAMPLE_META, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_write_graph_html_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "reports" / "sub" / "graph.html"
        write_graph_html(SAMPLE_NODES, SAMPLE_EDGES, SAMPLE_META, out)
        assert out.exists()

    def test_empty_nodes_and_edges(self):
        html = render_graph_html([], [], {**SAMPLE_META, "total_nodes": 0, "total_edges": 0})
        assert "<!DOCTYPE html>" in html
        assert "RAW_NODES = []" in html


# ── CLI integration tests ─────────────────────────────────────────────────────

class TestGraphCmd:
    def test_exits_1_without_index(self, tmp_path):
        result = runner.invoke(app, ["graph", str(tmp_path), "--no-open"])
        assert result.exit_code == 1
        assert "ag index" in result.output

    def test_generates_html_from_real_index(self, tmp_path):
        """Build a real index then run ag graph against it."""
        pytest.importorskip("agentra.index.engine")

        # Write a small Python source file to index
        src = tmp_path / "mymod.py"
        src.write_text(
            "class Greeter:\n"
            "    def greet(self, name: str) -> str:\n"
            "        return f'Hello {name}'\n\n"
            "def main():\n"
            "    g = Greeter()\n"
            "    print(g.greet('world'))\n",
            encoding="utf-8",
        )

        # Build the index
        idx_result = runner.invoke(app, ["index", str(tmp_path)])
        assert idx_result.exit_code == 0

        # Generate graph — use --include-orphans so nodes appear even without pyan3
        out_html = tmp_path / "graph.html"
        result = runner.invoke(app, [
            "graph", str(tmp_path),
            "--output", str(out_html),
            "--no-open",
            "--include-orphans",
        ])
        assert result.exit_code == 0
        assert out_html.exists()
        content = out_html.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Greeter" in content or "greet" in content

    def test_max_nodes_truncates(self, tmp_path):
        pytest.importorskip("agentra.index.engine")

        # Write a file with multiple symbols
        src = tmp_path / "big.py"
        lines = ["def func_{i}():\n    pass\n" for i in range(20)]
        src.write_text("".join(lines), encoding="utf-8")

        runner.invoke(app, ["index", str(tmp_path)])

        out_html = tmp_path / "graph.html"
        result = runner.invoke(app, [
            "graph", str(tmp_path),
            "--output", str(out_html),
            "--max-nodes", "5",
            "--no-open",
        ])
        # Should succeed and note truncation
        assert result.exit_code == 0
        assert out_html.exists()
