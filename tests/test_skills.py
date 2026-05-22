"""Tests for the Skill System."""

import pytest

from agent_guard.skills.registry import BUILTIN_SKILLS, SkillRegistry


class TestSkillRegistry:
    def test_builtin_skills_loaded(self):
        registry = SkillRegistry()
        assert len(registry.list_all()) > 0

    def test_all_skills_have_required_fields(self):
        for skill_id, skill in BUILTIN_SKILLS.items():
            assert skill.id == skill_id
            assert skill.name
            assert skill.description
            assert skill.instructions
            assert len(skill.stacks) > 0

    def test_resolve_for_python_stack(self):
        registry = SkillRegistry()
        skills = registry.resolve_for_stack(["python", "fastapi"])
        skill_ids = [s.id for s in skills]
        assert "fastapi" in skill_ids
        assert "karpathy" in skill_ids  # "all" stack

    def test_resolve_for_terraform(self):
        registry = SkillRegistry()
        skills = registry.resolve_for_stack(["terraform"])
        skill_ids = [s.id for s in skills]
        assert "terraform" in skill_ids

    def test_get_instructions(self):
        registry = SkillRegistry()
        instructions = registry.get_instructions(["fastapi", "karpathy"])
        assert "FastAPI" in instructions
        assert "Karpathy" in instructions

    def test_register_custom_skill(self):
        from agent_guard.models import Skill
        registry = SkillRegistry()
        custom = Skill(
            id="custom-test",
            name="Custom Test",
            description="A test skill",
            stacks=["python"],
            instructions="Do custom things.",
        )
        registry.register(custom)
        assert registry.get("custom-test") is not None

    def test_get_nonexistent(self):
        registry = SkillRegistry()
        assert registry.get("nonexistent") is None
