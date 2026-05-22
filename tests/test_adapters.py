"""Tests for the Agent Integration Adapters."""

from pathlib import Path

import pytest

from agent_guard.adapters.agents import generate_for_agents, write_agent_files
from agent_guard.detection.engine import StackDetector
from agent_guard.governance.engine import GovernanceEngine
from agent_guard.models import AgentPlatform, ProjectConfig, StackProfile, TokenBudget
from agent_guard.optimizer.engine import TokenOptimizer


@pytest.fixture
def config() -> ProjectConfig:
    return ProjectConfig(
        project_name="test-project",
        languages=["python"],
        frameworks=["fastapi"],
        agents=[AgentPlatform.CLAUDE, AgentPlatform.CURSOR, AgentPlatform.COPILOT],
        skills=["fastapi", "karpathy"],
    )


@pytest.fixture
def stack() -> StackProfile:
    from agent_guard.models import DetectedComponent
    return StackProfile(
        languages=[DetectedComponent(name="python", confidence=0.9, source="pyproject.toml")],
        frameworks=[DetectedComponent(name="fastapi", confidence=0.85, source="requirements.txt")],
    )


class TestAdapters:
    def test_generates_claude_md(self, config, stack):
        gov = GovernanceEngine(stack)
        opt = TokenOptimizer()
        files = generate_for_agents(config.agents, config, stack, gov, opt)
        assert "CLAUDE.md" in files
        assert "Agent Guard" in files["CLAUDE.md"]

    def test_generates_cursorrules(self, config, stack):
        gov = GovernanceEngine(stack)
        opt = TokenOptimizer()
        files = generate_for_agents(config.agents, config, stack, gov, opt)
        assert ".cursorrules" in files

    def test_generates_copilot(self, config, stack):
        gov = GovernanceEngine(stack)
        opt = TokenOptimizer()
        files = generate_for_agents(config.agents, config, stack, gov, opt)
        assert ".github/copilot-instructions.md" in files

    def test_always_generates_agents_md(self, config, stack):
        gov = GovernanceEngine(stack)
        opt = TokenOptimizer()
        files = generate_for_agents(config.agents, config, stack, gov, opt)
        assert "AGENTS.md" in files

    def test_write_files(self, config, stack, tmp_path):
        gov = GovernanceEngine(stack)
        opt = TokenOptimizer()
        files = generate_for_agents(config.agents, config, stack, gov, opt)
        written = write_agent_files(tmp_path, files)
        assert len(written) > 0
        for f in written:
            assert f.exists()

    def test_generated_content_has_security(self, config, stack):
        gov = GovernanceEngine(stack)
        opt = TokenOptimizer()
        files = generate_for_agents(config.agents, config, stack, gov, opt)
        for _, content in files.items():
            assert "Security" in content or "security" in content or "conventions" in content.lower()
