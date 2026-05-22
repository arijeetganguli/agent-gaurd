"""Tests for the Onboarding Engine."""

from pathlib import Path

import pytest

from agentra.models import OnboardingMode, SecurityMode
from agentra.onboarding.engine import detect_and_build_config, load_config, save_config


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "onboard-test"\ndependencies = ["fastapi"]\n')
    (tmp_path / "requirements.txt").write_text("fastapi\n")
    return tmp_path


class TestOnboarding:
    def test_quick_mode(self, project: Path):
        config = detect_and_build_config(project, OnboardingMode.QUICK)
        assert config.project_name == project.name
        assert config.security_mode == SecurityMode.STANDARD

    def test_enterprise_mode(self, project: Path):
        config = detect_and_build_config(project, OnboardingMode.ENTERPRISE)
        assert config.security_mode == SecurityMode.ENTERPRISE
        assert len(config.compliance) > 0

    def test_save_and_load(self, project: Path):
        config = detect_and_build_config(project)
        save_config(config, project)

        loaded = load_config(project)
        assert loaded is not None
        assert loaded.project_name == config.project_name

    def test_load_missing_config(self, tmp_path: Path):
        result = load_config(tmp_path)
        assert result is None
