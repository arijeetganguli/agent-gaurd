"""Tests for Benchmarking and Report Generation."""

from pathlib import Path

import pytest

from agentra.benchmarks.runner import BenchmarkRunner
from agentra.renderers.html import HtmlRenderer
from agentra.renderers.markdown import MarkdownRenderer


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a sample project for benchmarking."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "bench-test"\ndependencies = ["fastapi", "openai"]\n'
    )
    (tmp_path / "requirements.txt").write_text("fastapi\nopenai\npsycopg2\n")
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    return tmp_path


class TestBenchmarkRunner:
    def test_run_produces_report(self, sample_project: Path):
        runner = BenchmarkRunner(sample_project)
        report = runner.run()
        assert report.project_name == sample_project.name
        assert len(report.skill_benchmarks) > 0

    def test_skill_benchmarks_have_metrics(self, sample_project: Path):
        runner = BenchmarkRunner(sample_project)
        report = runner.run()
        for sb in report.skill_benchmarks:
            assert sb.skill_name
            assert sb.skill_id
            assert len(sb.metrics) > 0

    def test_governance_benchmark_present(self, sample_project: Path):
        runner = BenchmarkRunner(sample_project)
        report = runner.run()
        ids = [sb.skill_id for sb in report.skill_benchmarks]
        assert "governance-engine" in ids

    def test_optimization_benchmark_present(self, sample_project: Path):
        runner = BenchmarkRunner(sample_project)
        report = runner.run()
        ids = [sb.skill_id for sb in report.skill_benchmarks]
        assert "optimization-engine" in ids


class TestMarkdownRenderer:
    def test_render_to_file(self, sample_project: Path):
        runner = BenchmarkRunner(sample_project)
        report = runner.run()

        renderer = MarkdownRenderer()
        out = sample_project / "report.md"
        renderer.render(report, out)

        assert out.exists()
        content = out.read_text()
        assert "# Agentra" in content
        assert "Benchmark Report" in content
        assert "Skill Benchmarks" in content

    def test_render_string(self, sample_project: Path):
        runner = BenchmarkRunner(sample_project)
        report = runner.run()
        renderer = MarkdownRenderer()
        md = renderer.render_string(report)
        assert len(md) > 100


class TestHtmlRenderer:
    def test_render_to_file(self, sample_project: Path):
        runner = BenchmarkRunner(sample_project)
        report = runner.run()

        renderer = HtmlRenderer()
        out = sample_project / "report.html"
        renderer.render(report, out)

        assert out.exists()
        content = out.read_text()
        assert "<!DOCTYPE html>" in content
        assert "Agentra" in content
        assert "Skill Benchmarks" in content

    def test_html_contains_metrics(self, sample_project: Path):
        runner = BenchmarkRunner(sample_project)
        report = runner.run()
        renderer = HtmlRenderer()
        html = renderer.render_string(report)
        assert "metric-bar" in html
        assert "VERIFIED" in html or "UNVERIFIED" in html
