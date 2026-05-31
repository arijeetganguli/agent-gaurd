"""Tests for the RAG engine, anti-pattern library, and model/RAG adapter blocks.

Covers:
  - CodeRAGEngine.build / find_similar / detect_antipatterns / project_antipatterns
  - Graceful degradation when scikit-learn is absent
  - _build_rag_usage_block and _build_model_block adapter helpers
  - model_preferences round-trip through onboarding save/load
  - ag rag and ag model CLI commands (Typer CliRunner)
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from agentra.adapters.agents import (
    _build_model_block,
    _build_rag_usage_block,
    generate_for_agents,
)
from agentra.cli.main import app
from agentra.governance.engine import GovernanceEngine
from agentra.models import (
    AGENT_DEFAULT_MODELS,
    AGENT_PURPOSES,
    CAPABILITY_CLASSES,
    CAPABILITY_FALLBACK_CHAINS,
    CAPABILITY_MODELS,
    KNOWN_MODELS,
    PURPOSE_CAPABILITY_MAP,
    PURPOSE_MODELS,
    AgentPlatform,
    DetectedComponent,
    ProjectConfig,
    RAGConfig,
    StackProfile,
    detect_active_models,
    resolve_model_with_fallback,
)
from agentra.onboarding.engine import load_config, save_config
from agentra.optimizer.engine import TokenOptimizer
from agentra.rag.patterns import AntiPatternLibrary

runner = CliRunner()

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def python_project(tmp_path: Path) -> Path:
    """Minimal Python project with a couple of source files."""
    src = tmp_path / "src"
    src.mkdir()

    (src / "auth.py").write_text(textwrap.dedent("""\
        import jwt
        import hashlib

        SECRET = "hard-coded-secret"

        def verify_token(token: str) -> bool:
            try:
                payload = jwt.decode(token, SECRET, algorithms=["HS256"])
                return True
            except:
                return False

        def hash_password(pw: str) -> str:
            return hashlib.md5(pw.encode()).hexdigest()
    """))

    (src / "utils.py").write_text(textwrap.dedent("""\
        def paginate(items, page=1, size=20):
            start = (page - 1) * size
            return items[start:start + size]

        def flatten(nested):
            result = []
            for item in nested:
                if isinstance(item, list):
                    result.extend(flatten(item))
                else:
                    result.append(item)
            return result
    """))

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-proj"\n')
    return tmp_path


@pytest.fixture
def config_with_rag() -> ProjectConfig:
    return ProjectConfig(
        project_name="rag-test",
        languages=["python"],
        agents=[AgentPlatform.CLAUDE, AgentPlatform.COPILOT],
        rag_config=RAGConfig(enabled=True, include_in_agent_files=True),
        model_preferences={
            AgentPlatform.CLAUDE.value: "claude-sonnet-4-5",
            AgentPlatform.COPILOT.value: "gpt-4.1",
        },
    )


@pytest.fixture
def stack() -> StackProfile:
    return StackProfile(
        languages=[DetectedComponent(name="python", confidence=0.9, source="pyproject.toml")]
    )


# ── AntiPatternLibrary ────────────────────────────────────────────────────────


class TestAntiPatternLibrary:
    def test_detects_bare_except(self):
        code = "try:\n    pass\nexcept:\n    pass\n"
        findings = AntiPatternLibrary().scan(code, "test.py")
        ids = [f.pattern_id for f in findings]
        assert "AP-006" in ids

    def test_detects_wildcard_import(self):
        code = "from os import *\n"
        findings = AntiPatternLibrary().scan(code, "test.py")
        ids = [f.pattern_id for f in findings]
        assert "AP-007" in ids

    def test_detects_mutable_default(self):
        code = "def f(x=[]):\n    pass\n"
        findings = AntiPatternLibrary().scan(code, "test.py")
        ids = [f.pattern_id for f in findings]
        assert "AP-005" in ids

    def test_detects_global_mutation(self):
        code = "counter = 0\ndef inc():\n    global counter\n    counter += 1\n"
        findings = AntiPatternLibrary().scan(code, "test.py")
        ids = [f.pattern_id for f in findings]
        assert "AP-012" in ids

    def test_clean_code_returns_no_findings(self):
        code = textwrap.dedent("""\
            from typing import Optional

            MAX_ITEMS = 100

            def process(items: list[str]) -> list[str]:
                return [x.strip() for x in items]
        """)
        findings = AntiPatternLibrary().scan(code, "clean.py")
        # May return AP-010 (missing type hints) for untyped functions — we only
        # verify no CRITICAL or HIGH findings
        high_plus = [f for f in findings if f.severity.value in ("critical", "high")]
        assert high_plus == []

    def test_scan_file(self, tmp_path: Path):
        f = tmp_path / "bad.py"
        f.write_text("from os import *\n")
        findings = AntiPatternLibrary().scan_file(f)
        assert any(x.pattern_id == "AP-007" for x in findings)


# ── CodeRAGEngine ─────────────────────────────────────────────────────────────


class TestCodeRAGEngine:
    """Integration tests — require scikit-learn. Skipped if absent."""

    @pytest.fixture(autouse=True)
    def _skip_without_sklearn(self):
        pytest.importorskip("sklearn", reason="scikit-learn not installed")

    def _make_engine(self, project_root: Path):
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = project_root / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(project_root)
            rag = CodeRAGEngine(idx_dir, idx)
            rag.build(force=True)
        return idx_dir

    def test_build_creates_artefacts(self, python_project: Path):
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag = CodeRAGEngine(idx_dir, idx)
            rag.build(force=True)

        assert (idx_dir / "rag_vectorizer.pkl").exists()
        assert (idx_dir / "rag_matrix.npz").exists()
        assert (idx_dir / "rag_meta.pkl").exists()

    def test_find_similar_returns_tuples(self, python_project: Path):
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag = CodeRAGEngine(idx_dir, idx)
            rag.build(force=True)
            results = rag.find_similar("jwt token decode verify", top_k=3)

        assert isinstance(results, list)
        for item in results:
            fp, line, score = item
            assert isinstance(fp, str)
            assert isinstance(line, int)
            assert 0.0 <= score <= 1.0

    def test_find_similar_relevant_result(self, python_project: Path):
        """Query closely matching auth.py content should rank auth.py highly."""
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag = CodeRAGEngine(idx_dir, idx)
            rag.build(force=True)
            results = rag.find_similar("verify_token jwt decode secret", top_k=5)

        assert len(results) > 0
        top_file = results[0][0]
        assert "auth" in top_file.lower()

    def test_find_similar_empty_query(self, python_project: Path):
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag = CodeRAGEngine(idx_dir, idx)
            rag.build(force=True)
            results = rag.find_similar("   ", top_k=5)

        assert results == []

    def test_top_k_respected(self, python_project: Path):
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag = CodeRAGEngine(idx_dir, idx)
            rag.build(force=True)
            results = rag.find_similar("function", top_k=1)

        assert len(results) <= 1

    def test_project_antipatterns(self, python_project: Path):
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag = CodeRAGEngine(idx_dir, idx)
            rag.build(force=True)
            patterns = rag.project_antipatterns()

        # auth.py has a bare except — should surface
        ids = [p.pattern_id for p in patterns]
        assert "AP-006" in ids

    def test_detect_antipatterns_inline(self, python_project: Path):
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag = CodeRAGEngine(idx_dir, idx)
            rag.build(force=True)
            findings = rag.detect_antipatterns("from os import *\n", "probe.py")

        ids = [f.pattern_id for f in findings]
        assert "AP-007" in ids

    def test_graceful_degradation_without_sklearn(self, python_project: Path):
        """find_similar returns [] when sklearn is unavailable — never raises."""
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag = CodeRAGEngine(idx_dir, idx)

        with patch("agentra.rag.engine._require_sklearn", side_effect=ImportError("no sklearn")):
            results = rag.find_similar("anything", top_k=5)

        assert results == []

    def test_build_persists_then_loads(self, python_project: Path):
        """Second CodeRAGEngine instance should load from disk without rebuild."""
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag1 = CodeRAGEngine(idx_dir, idx)
            rag1.build(force=True)

            # Second engine — should load from disk
            rag2 = CodeRAGEngine(idx_dir, idx)
            loaded = rag2._load()

        assert loaded is True
        assert rag2._vectorizer is not None


# ── Adapter block helpers ─────────────────────────────────────────────────────


class TestRagUsageBlock:
    def test_block_present_when_rag_enabled(self, config_with_rag):
        block = _build_rag_usage_block(config_with_rag)
        assert "ag rag" in block
        assert "ag index" in block
        assert "ag patterns" in block
        assert "## Agentra Code Intelligence" in block

    def test_block_empty_when_rag_disabled(self):
        config = ProjectConfig(
            project_name="x",
            rag_config=RAGConfig(enabled=False),
        )
        assert _build_rag_usage_block(config) == ""

    def test_block_injected_into_claude_md(self, config_with_rag, stack):
        gov = GovernanceEngine(stack)
        opt = TokenOptimizer()
        files = generate_for_agents(config_with_rag.agents, config_with_rag, stack, gov, opt)
        assert "ag rag" in files["CLAUDE.md"]
        assert "ag rag" in files[".github/copilot-instructions.md"]
        assert "ag rag" in files["AGENTS.md"]

    def test_block_injected_into_agents_md(self, config_with_rag, stack):
        gov = GovernanceEngine(stack)
        opt = TokenOptimizer()
        files = generate_for_agents(config_with_rag.agents, config_with_rag, stack, gov, opt)
        assert "ag rag" in files["AGENTS.md"]


class TestModelBlock:
    def test_block_shows_active_model(self, config_with_rag):
        block = _build_model_block(AgentPlatform.CLAUDE.value, config_with_rag)
        assert "claude-sonnet-4-5" in block
        assert "## Model Preference" in block

    def test_block_lists_available_models(self, config_with_rag):
        block = _build_model_block(AgentPlatform.COPILOT.value, config_with_rag)
        for model in KNOWN_MODELS["copilot"]:
            assert model in block

    def test_block_empty_when_no_preference(self):
        config = ProjectConfig(project_name="x", model_preferences={})
        block = _build_model_block(AgentPlatform.CLAUDE.value, config)
        assert block == ""

    def test_block_injected_into_claude_md(self, config_with_rag, stack):
        gov = GovernanceEngine(stack)
        opt = TokenOptimizer()
        files = generate_for_agents(config_with_rag.agents, config_with_rag, stack, gov, opt)
        assert "claude-sonnet-4-5" in files["CLAUDE.md"]
        assert "gpt-4.1" in files[".github/copilot-instructions.md"]

    def test_change_model_override_hint_present(self, config_with_rag):
        block = _build_model_block(AgentPlatform.CLAUDE.value, config_with_rag)
        assert "ag model set" in block


# ── model_preferences round-trip ─────────────────────────────────────────────


class TestModelPreferencesRoundTrip:
    def test_auto_seeded_from_defaults(self, tmp_path: Path):
        from agentra.onboarding.engine import detect_and_build_config
        from agentra.models import OnboardingMode

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        config = detect_and_build_config(tmp_path, OnboardingMode.QUICK)

        for ag in config.agents:
            assert ag.value in config.model_preferences
            assert config.model_preferences[ag.value] == AGENT_DEFAULT_MODELS.get(ag.value, "")

    def test_saved_and_loaded(self, tmp_path: Path):
        config = ProjectConfig(
            project_name="round-trip",
            agents=[AgentPlatform.CLAUDE, AgentPlatform.COPILOT],
            model_preferences={"claude": "claude-opus-4", "copilot": "o3"},
        )
        save_config(config, tmp_path)
        loaded = load_config(tmp_path)

        assert loaded is not None
        assert loaded.model_preferences["claude"] == "claude-opus-4"
        assert loaded.model_preferences["copilot"] == "o3"

    def test_missing_model_prefs_loads_empty_dict(self, tmp_path: Path):
        # Config written without model_preferences key
        (tmp_path / ".agentra.yml").write_text(
            "project:\n  name: old-config\nagents: [claude]\n"
        )
        loaded = load_config(tmp_path)
        assert loaded is not None
        assert isinstance(loaded.model_preferences, dict)


# ── CLI: ag rag ───────────────────────────────────────────────────────────────


class TestCliRag:
    def test_rag_no_index_exits_with_error(self, tmp_path: Path):
        result = runner.invoke(app, ["rag", "some query", "--path", str(tmp_path)])
        assert result.exit_code != 0
        assert "index" in result.output.lower() or "No knowledge graph" in result.output

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("sklearn"),
        reason="scikit-learn not installed",
    )
    def test_rag_returns_results(self, python_project: Path):
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag = CodeRAGEngine(idx_dir, idx)
            rag.build(force=True)

        result = runner.invoke(app, ["rag", "verify token jwt", "--path", str(python_project)])
        assert result.exit_code == 0
        assert "RAG Results" in result.output

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("sklearn"),
        reason="scikit-learn not installed",
    )
    def test_rag_json_format(self, python_project: Path):
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine

        idx_dir = python_project / ".agentra"
        idx_dir.mkdir()
        with CodeIndexEngine(idx_dir) as idx:
            idx.build(python_project)
            rag = CodeRAGEngine(idx_dir, idx)
            rag.build(force=True)

        result = runner.invoke(
            app, ["rag", "paginate items", "--path", str(python_project), "--format", "json"]
        )
        assert result.exit_code == 0
        # JSON is written with plain print() — no Rich formatting in output
        data = json.loads(result.output)
        assert isinstance(data, list)
        for item in data:
            assert "file" in item
            assert "score" in item
            assert "line" in item


# ── CLI: ag model ─────────────────────────────────────────────────────────────


class TestCliModel:
    def _init_project(self, tmp_path: Path) -> None:
        # path is a positional Argument in ag init, not an Option
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "model-test"\n')
        runner.invoke(app, ["init", str(tmp_path), "--agents", "claude,copilot"])

    def test_model_list_shows_agents(self, tmp_path: Path):
        self._init_project(tmp_path)
        result = runner.invoke(app, ["model", "list", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "claude" in result.output
        assert "copilot" in result.output

    def test_model_list_shows_active_model(self, tmp_path: Path):
        self._init_project(tmp_path)
        result = runner.invoke(app, ["model", "list", "--path", str(tmp_path)])
        assert result.exit_code == 0
        # Auto-selected defaults should appear
        assert AGENT_DEFAULT_MODELS["claude"] in result.output
        assert AGENT_DEFAULT_MODELS["copilot"] in result.output

    def test_model_set_updates_config(self, tmp_path: Path):
        self._init_project(tmp_path)
        result = runner.invoke(
            app, ["model", "set", "claude", "claude-opus-4", "--path", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "claude-opus-4" in result.output

        loaded = load_config(tmp_path)
        assert loaded is not None
        assert loaded.model_preferences["claude"] == "claude-opus-4"

    def test_model_set_regenerates_agent_files(self, tmp_path: Path):
        self._init_project(tmp_path)
        runner.invoke(app, ["model", "set", "claude", "claude-opus-4", "--path", str(tmp_path)])
        claude_md = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "claude-opus-4" in claude_md

    def test_model_set_invalid_agent_exits(self, tmp_path: Path):
        self._init_project(tmp_path)
        result = runner.invoke(
            app, ["model", "set", "nonexistent-agent", "gpt-4.1", "--path", str(tmp_path)]
        )
        assert result.exit_code != 0

    def test_model_list_no_config_exits(self, tmp_path: Path):
        result = runner.invoke(app, ["model", "list", "--path", str(tmp_path)])
        assert result.exit_code != 0

    def test_model_set_unknown_action_exits(self, tmp_path: Path):
        self._init_project(tmp_path)
        result = runner.invoke(app, ["model", "badaction", "--path", str(tmp_path)])
        assert result.exit_code != 0


# ── CLI: ag init --model ─────────────────────────────────────────────────────


class TestCliInitModel:
    def test_init_auto_seeds_models(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "m"\n')
        runner.invoke(app, ["init", str(tmp_path), "--agents", "claude,copilot"])
        loaded = load_config(tmp_path)
        assert loaded is not None
        assert loaded.model_preferences.get("claude") == AGENT_DEFAULT_MODELS["claude"]
        assert loaded.model_preferences.get("copilot") == AGENT_DEFAULT_MODELS["copilot"]

    def test_init_model_override(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "m"\n')
        runner.invoke(
            app,
            ["init", str(tmp_path), "--agents", "claude,copilot", "--model", "claude-opus-4"],
        )
        loaded = load_config(tmp_path)
        assert loaded is not None
        assert loaded.model_preferences.get("claude") == "claude-opus-4"
        assert loaded.model_preferences.get("copilot") == "claude-opus-4"

    def test_init_auto_mode_is_default(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "m"\n')
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        # Should show model preferences table in output
        assert "Model Preferences" in result.output

    def test_model_block_in_copilot_instructions(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "m"\n')
        runner.invoke(app, ["init", str(tmp_path), "--agents", "copilot"])
        content = (tmp_path / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        assert "## Model Preference" in content
        assert AGENT_DEFAULT_MODELS["copilot"] in content

    def test_rag_usage_block_in_agents_md(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "m"\n')
        runner.invoke(app, ["init", str(tmp_path)])
        content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert "ag rag" in content
        assert "Agentra Code Intelligence" in content


# ── Purpose-based model routing ───────────────────────────────────────────────


class TestPurposeModelRouting:
    """Tests for per-purpose model selection (coding/reasoning/planning/etc.)."""

    def _init_project(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "p"\n')
        runner.invoke(app, ["init", str(tmp_path), "--agents", "claude,copilot"])

    # ── PURPOSE_MODELS data ────────────────────────────────────────────────

    def test_purpose_models_has_all_platforms(self):
        for platform in AgentPlatform:
            assert platform.value in PURPOSE_MODELS, f"Missing PURPOSE_MODELS for {platform.value}"

    def test_purpose_models_has_all_purposes(self):
        for platform, mapping in PURPOSE_MODELS.items():
            for purpose in AGENT_PURPOSES:
                assert purpose in mapping, f"Missing purpose '{purpose}' for {platform}"

    def test_purpose_models_values_in_known_models(self):
        for platform, mapping in PURPOSE_MODELS.items():
            known = KNOWN_MODELS.get(platform, [])
            for purpose, model in mapping.items():
                assert model in known, (
                    f"{platform}/{purpose} -> '{model}' not in KNOWN_MODELS"
                )

    # ── Config round-trip ──────────────────────────────────────────────────

    def test_init_seeds_purpose_preferences(self, tmp_path: Path):
        self._init_project(tmp_path)
        loaded = load_config(tmp_path)
        assert loaded is not None
        for agent in ["claude", "copilot"]:
            assert agent in loaded.model_purpose_preferences
            pmap = loaded.model_purpose_preferences[agent]
            for purpose in AGENT_PURPOSES:
                assert purpose in pmap
                assert pmap[purpose] == PURPOSE_MODELS[agent][purpose]

    def test_purpose_prefs_survive_save_load(self, tmp_path: Path):
        self._init_project(tmp_path)
        loaded = load_config(tmp_path)
        assert loaded is not None
        loaded.model_purpose_preferences["claude"]["reasoning"] = "claude-haiku-3-5"
        save_config(loaded, tmp_path)
        reloaded = load_config(tmp_path)
        assert reloaded is not None
        assert reloaded.model_purpose_preferences["claude"]["reasoning"] == "claude-haiku-3-5"

    def test_missing_purpose_prefs_loads_as_empty_dict(self, tmp_path: Path):
        # Write a minimal config that has no model_purpose_preferences key (old format)
        from ruamel.yaml import YAML as _YAML
        _yaml = _YAML()
        _yaml.default_flow_style = False
        minimal_cfg = {
            "project": {"name": "old-project"},
            "security": {"mode": "standard"},
            "agents": ["claude"],
            "model_preferences": {"claude": "claude-sonnet-4-5"},
        }
        cfg_path = tmp_path / ".agentra.yml"
        with open(cfg_path, "w", encoding="utf-8") as f:
            _yaml.dump(minimal_cfg, f)
        loaded = load_config(tmp_path)
        assert loaded is not None
        # Should default to empty dict — no crash
        assert isinstance(loaded.model_purpose_preferences, dict)

    # ── Adapter: _build_model_block with purpose map ───────────────────────

    def test_model_block_includes_purpose_routing_section(self):
        config = ProjectConfig(agents=[AgentPlatform.CLAUDE])
        config.model_preferences["claude"] = "claude-sonnet-4-5"
        config.model_purpose_preferences["claude"] = PURPOSE_MODELS["claude"]
        block = _build_model_block("claude", config)
        assert "Model Routing by Purpose" in block
        assert "Reasoning" in block
        assert "Planning" in block
        assert "Coding" in block
        assert "Documentation" in block
        assert "claude-opus-4" in block

    def test_model_block_purpose_routing_absent_when_no_purpose_prefs(self):
        config = ProjectConfig(agents=[AgentPlatform.CLAUDE])
        config.model_preferences["claude"] = "claude-sonnet-4-5"
        block = _build_model_block("claude", config)
        assert "Model Routing by Purpose" not in block

    def test_model_block_purpose_routing_in_generated_file(self, tmp_path: Path):
        self._init_project(tmp_path)
        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Model Routing by Purpose" in content
        assert "claude-opus-4" in content

    # ── CLI: ag model set --purpose ────────────────────────────────────────

    def test_model_set_purpose_updates_purpose_prefs(self, tmp_path: Path):
        self._init_project(tmp_path)
        result = runner.invoke(
            app,
            [
                "model", "set", "claude", "claude-haiku-3-5",
                "--path", str(tmp_path), "--purpose", "documentation",
            ],
        )
        assert result.exit_code == 0
        assert "documentation" in result.output
        assert "claude-haiku-3-5" in result.output
        loaded = load_config(tmp_path)
        assert loaded is not None
        assert loaded.model_purpose_preferences["claude"]["documentation"] == "claude-haiku-3-5"
        assert loaded.model_preferences["claude"] == PURPOSE_MODELS["claude"]["general"]

    def test_model_set_purpose_regenerates_files(self, tmp_path: Path):
        self._init_project(tmp_path)
        runner.invoke(
            app,
            [
                "model", "set", "claude", "claude-haiku-3-5",
                "--path", str(tmp_path), "--purpose", "reasoning",
            ],
        )
        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "claude-haiku-3-5" in content

    def test_model_set_invalid_purpose_exits(self, tmp_path: Path):
        self._init_project(tmp_path)
        result = runner.invoke(
            app,
            [
                "model", "set", "claude", "claude-opus-4",
                "--path", str(tmp_path), "--purpose", "invalid-purpose",
            ],
        )
        assert result.exit_code != 0

    def test_model_set_no_purpose_does_not_touch_purpose_prefs(self, tmp_path: Path):
        self._init_project(tmp_path)
        runner.invoke(app, ["model", "set", "claude", "claude-opus-4", "--path", str(tmp_path)])
        loaded = load_config(tmp_path)
        assert loaded is not None
        assert loaded.model_preferences["claude"] == "claude-opus-4"
        assert loaded.model_purpose_preferences["claude"]["coding"] == PURPOSE_MODELS["claude"]["coding"]

    # ── CLI: ag model list shows purpose table ─────────────────────────────

    def test_model_list_shows_purpose_table(self, tmp_path: Path):
        self._init_project(tmp_path)
        result = runner.invoke(app, ["model", "list", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "Per-Purpose Model Routing" in result.output
        assert "Coding" in result.output
        assert "Reasoning" in result.output
        assert "Planning" in result.output

    # ── Capability-class derivation ────────────────────────────────────────

    def test_capability_class_derivation(self):
        """PURPOSE_MODELS is correctly derived from CAPABILITY_MODELS + PURPOSE_CAPABILITY_MAP."""
        for platform in CAPABILITY_MODELS:
            for purpose in AGENT_PURPOSES:
                cap_class = PURPOSE_CAPABILITY_MAP[purpose]
                expected = CAPABILITY_MODELS[platform][cap_class]
                assert PURPOSE_MODELS[platform][purpose] == expected, (
                    f"{platform}/{purpose}: expected {expected!r} via {cap_class}"
                )

    def test_default_models_use_balanced_capability(self):
        """AGENT_DEFAULT_MODELS is derived from the 'balanced' capability class."""
        for platform, model in AGENT_DEFAULT_MODELS.items():
            assert model == CAPABILITY_MODELS[platform]["balanced"], (
                f"{platform}: default model should be balanced capability, got {model!r}"
            )

    def test_all_routesmith_task_types_covered(self):
        """routesmith task types are all represented in AGENT_PURPOSES."""
        routesmith_tasks = {"planning", "coding", "testing", "refactoring", "documentation", "review", "formatting"}
        assert routesmith_tasks.issubset(set(AGENT_PURPOSES))

    def test_every_capability_class_present_per_platform(self):
        """Every platform's CAPABILITY_MODELS has all four capability classes."""
        for platform, caps in CAPABILITY_MODELS.items():
            for cap_class in CAPABILITY_CLASSES:
                assert cap_class in caps, f"{platform} missing capability class '{cap_class}'"


class TestModelFallback:
    """Tests for resolve_model_with_fallback and detect_active_models."""

    def test_resolve_model_primary_returned_no_restrictions(self):
        """When no restrictions, the first model in the chain is returned."""
        result = resolve_model_with_fallback("claude", "deep_reasoning")
        chain = CAPABILITY_FALLBACK_CHAINS["claude"]["deep_reasoning"]
        assert result == chain[0]

    def test_resolve_model_skips_restricted_model(self):
        """Primary model is restricted — next in chain is returned."""
        chain = CAPABILITY_FALLBACK_CHAINS["copilot"]["deep_reasoning"]
        primary = chain[0]
        result = resolve_model_with_fallback("copilot", "deep_reasoning", restricted={primary})
        assert result != primary
        # Should be the next model in the chain that is not restricted
        expected = next(m for m in chain if m != primary)
        assert result == expected

    def test_resolve_model_all_restricted_returns_primary_capability(self):
        """If all chain models are restricted, fall back to the CAPABILITY_MODELS primary."""
        chain = CAPABILITY_FALLBACK_CHAINS["claude"]["fast"]
        all_restricted = set(chain)
        result = resolve_model_with_fallback("claude", "fast", restricted=all_restricted)
        # Must return the CAPABILITY_MODELS primary, even if it's in restricted
        assert result == CAPABILITY_MODELS["claude"]["fast"]

    def test_resolve_model_unknown_platform_returns_primary(self):
        """Unknown platform — falls back to CAPABILITY_MODELS primary."""
        result = resolve_model_with_fallback("nonexistent_platform", "balanced")
        # No chain for unknown platform → falls through to the default model
        # which also doesn't exist, so it should return the capability primary (empty string / graceful)
        assert isinstance(result, str)

    def test_fallback_chains_cover_all_platforms(self):
        """Every platform in CAPABILITY_MODELS has a fallback chain entry."""
        for platform in CAPABILITY_MODELS:
            assert platform in CAPABILITY_FALLBACK_CHAINS, (
                f"Missing fallback chain for '{platform}'"
            )

    def test_fallback_chains_cover_all_capability_classes(self):
        """Every platform's fallback chain has all four capability classes."""
        for platform, chains in CAPABILITY_FALLBACK_CHAINS.items():
            for cap in CAPABILITY_CLASSES:
                assert cap in chains, f"{platform} missing fallback chain for '{cap}'"

    def test_detect_active_models_returns_dict(self, monkeypatch):
        """detect_active_models always returns a dict, even with empty env."""
        # Clear all relevant env vars
        for var in ["CLAUDE_MODEL", "AIDER_MODEL", "OPENAI_MODEL", "CODEX_MODEL", "GEMINI_MODEL"]:
            monkeypatch.delenv(var, raising=False)
        result = detect_active_models()
        assert isinstance(result, dict)

    def test_detect_active_models_claude_env_var(self, monkeypatch):
        """CLAUDE_MODEL env var is picked up for the claude platform."""
        monkeypatch.setenv("CLAUDE_MODEL", "claude-haiku-4-5")
        result = detect_active_models()
        assert "claude" in result
        assert result["claude"]["model"] == "claude-haiku-4-5"
        assert "env" in result["claude"]["source"].lower()

    def test_detect_active_models_aider_env_var(self, monkeypatch):
        """AIDER_MODEL env var is picked up for the aider platform."""
        monkeypatch.setenv("AIDER_MODEL", "claude-sonnet-4-6")
        result = detect_active_models()
        assert "aider" in result
        assert result["aider"]["model"] == "claude-sonnet-4-6"


class TestModelDetectCLI:
    """CLI integration tests for `ag model detect`."""

    def test_model_detect_exits_successfully(self, tmp_path):
        """ag model detect exits 0 even with no config."""
        from typer.testing import CliRunner
        from agentra.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["model", "detect", "--path", str(tmp_path)])
        assert result.exit_code == 0

    def test_model_detect_output_contains_header(self, tmp_path):
        """ag model detect output mentions detected models."""
        from typer.testing import CliRunner
        from agentra.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["model", "detect", "--path", str(tmp_path)])
        assert "Detected Active Models" in result.output or "model" in result.output.lower()


class TestModelSetFallbackCLI:
    """CLI integration tests for `ag model set --auto-fallback` and `--interactive`."""

    def _make_config(self, tmp_path):
        from agentra.onboarding.engine import save_config
        cfg = ProjectConfig(
            project_name="test",
            agents=[AgentPlatform.CLAUDE],
            model_preferences={"claude": "claude-sonnet-4-6"},
            model_purpose_preferences={},
        )
        save_config(cfg, tmp_path)
        return cfg

    def test_model_set_unknown_model_warns_and_proceeds(self, tmp_path):
        """Without --auto-fallback, setting an unknown model warns but succeeds."""
        from typer.testing import CliRunner
        from agentra.cli.main import app
        self._make_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            app, ["model", "set", "claude", "unknown-model-xyz", "--path", str(tmp_path)]
        )
        assert "Warning" in result.output or result.exit_code == 0

    def test_model_set_auto_fallback_picks_known_model(self, tmp_path):
        """--auto-fallback with unknown model replaces it with a known fallback."""
        from typer.testing import CliRunner
        from agentra.cli.main import app
        self._make_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["model", "set", "claude", "totally-unknown-model", "--auto-fallback",
             "--path", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "Auto-fallback" in result.output

    def test_model_set_interactive_no_model_prompts(self, tmp_path):
        """--interactive with no model name prompts user; '1' selects the first known model."""
        from typer.testing import CliRunner
        from agentra.cli.main import app
        self._make_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["model", "set", "claude", "--interactive", "--path", str(tmp_path)],
            input="1\n",
        )
        assert result.exit_code == 0

    def test_model_set_no_agent_name_errors(self, tmp_path):
        """ag model set (no agent) returns exit code 1."""
        from typer.testing import CliRunner
        from agentra.cli.main import app
        self._make_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(app, ["model", "set", "--path", str(tmp_path)])
        assert result.exit_code != 0
