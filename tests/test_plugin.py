"""Tests for the Claude Code plugin generator."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from agentra.plugin.generator import PluginGenerator


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def generated_plugin(tmp_path: Path):
    """Generate a plugin package into a temp directory."""
    gen = PluginGenerator()
    written = gen.generate(tmp_path)
    return tmp_path, written


# ── File Structure Tests ──────────────────────────────────────────────────────

class TestPluginFileStructure:
    def test_generates_plugin_json(self, generated_plugin):
        output_dir, written = generated_plugin
        assert (output_dir / ".claude-plugin" / "plugin.json").exists()

    def test_generates_pre_tool_use_hook(self, generated_plugin):
        output_dir, _ = generated_plugin
        assert (output_dir / "hooks" / "pre-tool-use.sh").exists()

    def test_generates_guardian_skill(self, generated_plugin):
        output_dir, _ = generated_plugin
        assert (output_dir / "skills" / "agentra-guardian" / "SKILL.md").exists()

    def test_generates_scan_skill(self, generated_plugin):
        output_dir, _ = generated_plugin
        assert (output_dir / "skills" / "agentra-scan" / "SKILL.md").exists()

    def test_generates_enforce_skill(self, generated_plugin):
        output_dir, _ = generated_plugin
        assert (output_dir / "skills" / "agentra-enforce" / "SKILL.md").exists()

    def test_generates_prebuild_skill(self, generated_plugin):
        output_dir, _ = generated_plugin
        assert (output_dir / "skills" / "agentra-prebuild" / "SKILL.md").exists()

    def test_generates_readme(self, generated_plugin):
        output_dir, _ = generated_plugin
        assert (output_dir / "README.md").exists()

    def test_returns_list_of_paths(self, generated_plugin):
        _, written = generated_plugin
        assert isinstance(written, list)
        assert len(written) >= 7  # at least 7 files
        for p in written:
            assert isinstance(p, Path)
            assert p.exists()


# ── plugin.json Validation ────────────────────────────────────────────────────

class TestPluginJson:
    def test_valid_json(self, generated_plugin):
        output_dir, _ = generated_plugin
        content = (output_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_required_fields(self, generated_plugin):
        output_dir, _ = generated_plugin
        data = json.loads(
            (output_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        assert "name" in data
        assert "description" in data
        assert "author" in data

    def test_name_is_agentra(self, generated_plugin):
        output_dir, _ = generated_plugin
        data = json.loads(
            (output_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        assert data["name"] == "agentra"

    def test_author_has_url(self, generated_plugin):
        output_dir, _ = generated_plugin
        data = json.loads(
            (output_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        assert "url" in data["author"]


# ── Hook Script Tests ─────────────────────────────────────────────────────────

class TestPreToolUseHook:
    def test_is_shell_script(self, generated_plugin):
        output_dir, _ = generated_plugin
        content = (output_dir / "hooks" / "pre-tool-use.sh").read_text(encoding="utf-8")
        assert content.startswith("#!/")

    def test_references_ag_scan(self, generated_plugin):
        output_dir, _ = generated_plugin
        content = (output_dir / "hooks" / "pre-tool-use.sh").read_text(encoding="utf-8")
        assert "ag scan" in content or "agentra scan" in content

    def test_exits_on_critical(self, generated_plugin):
        output_dir, _ = generated_plugin
        content = (output_dir / "hooks" / "pre-tool-use.sh").read_text(encoding="utf-8")
        # Hook should block with non-zero exit
        assert "exit 1" in content

    def test_is_executable_on_unix(self, generated_plugin):
        """Check executable bit is set (meaningful only on Unix, skipped on Windows)."""
        import platform
        if platform.system() == "Windows":
            pytest.skip("chmod not applicable on Windows")
        output_dir, _ = generated_plugin
        hook = output_dir / "hooks" / "pre-tool-use.sh"
        mode = hook.stat().st_mode
        assert mode & stat.S_IXUSR, "pre-tool-use.sh should be executable"


# ── Skill SKILL.md Tests ──────────────────────────────────────────────────────

class TestSkillFiles:
    def test_guardian_has_yaml_frontmatter(self, generated_plugin):
        output_dir, _ = generated_plugin
        content = (output_dir / "skills" / "agentra-guardian" / "SKILL.md").read_text(encoding="utf-8")
        assert content.startswith("---"), "SKILL.md should start with YAML frontmatter"

    def test_guardian_contains_karpathy_guidelines(self, generated_plugin):
        output_dir, _ = generated_plugin
        content = (output_dir / "skills" / "agentra-guardian" / "SKILL.md").read_text(encoding="utf-8")
        assert "Karpathy" in content or "Think Before Coding" in content

    def test_scan_skill_contains_slash_command(self, generated_plugin):
        output_dir, _ = generated_plugin
        content = (output_dir / "skills" / "agentra-scan" / "SKILL.md").read_text(encoding="utf-8")
        assert "agentra-scan" in content

    def test_all_skills_non_empty(self, generated_plugin):
        output_dir, _ = generated_plugin
        skill_dirs = (output_dir / "skills").iterdir()
        for skill_dir in skill_dirs:
            md = skill_dir / "SKILL.md"
            assert md.exists()
            assert len(md.read_text(encoding="utf-8").strip()) > 100, (
                f"{skill_dir.name}/SKILL.md is too short"
            )


# ── PluginGenerator API Tests ─────────────────────────────────────────────────

class TestPluginGeneratorApi:
    def test_generate_creates_parent_dirs(self, tmp_path: Path):
        nested = tmp_path / "deep" / "nested" / "plugin"
        gen = PluginGenerator()
        written = gen.generate(nested)
        assert len(written) > 0
        assert nested.exists()

    def test_generate_with_config(self, tmp_path: Path):
        from agentra.models import ProjectConfig
        config = ProjectConfig(project_name="test-proj")
        gen = PluginGenerator()
        written = gen.generate(tmp_path, config=config)
        assert len(written) > 0

    def test_generate_idempotent(self, tmp_path: Path):
        gen = PluginGenerator()
        first = gen.generate(tmp_path)
        second = gen.generate(tmp_path)
        # Both should produce the same count of files
        assert len(first) == len(second)

    def test_readme_mentions_agentra(self, tmp_path: Path):
        gen = PluginGenerator()
        gen.generate(tmp_path)
        readme = (tmp_path / "README.md").read_text(encoding="utf-8")
        assert "Agentra" in readme or "agentra" in readme
