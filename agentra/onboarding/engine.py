"""Onboarding Engine — effortless project setup with intelligent defaults."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from agentra.detection.engine import StackDetector
from agentra.models import (
    AgentPlatform,
    ComplianceFramework,
    OnboardingMode,
    ProjectConfig,
    SecurityMode,
    TokenBudget,
)

yaml = YAML()
yaml.default_flow_style = False

CONFIG_FILE = ".agentra.yml"


def detect_and_build_config(project_root: Path, mode: OnboardingMode = OnboardingMode.QUICK) -> ProjectConfig:
    """Auto-detect stack and build initial config."""
    detector = StackDetector(project_root)
    stack = detector.detect()

    config = ProjectConfig(
        project_name=project_root.name,
        languages=[c.name for c in stack.languages],
        frameworks=[c.name for c in stack.frameworks],
        sdks=[c.name for c in stack.sdks],
        databases=[c.name for c in stack.databases],
        cloud_providers=[c.name for c in stack.cloud_providers],
        skills=[c.name for c in stack.all_components if c.confidence >= 0.6],
    )

    # Apply mode-specific defaults
    if mode == OnboardingMode.ENTERPRISE:
        config.security_mode = SecurityMode.ENTERPRISE
        config.compliance = [ComplianceFramework.SOC2, ComplianceFramework.ISO27001]
        config.token_budget = TokenBudget(input_limit=16000, output_limit=6000, reserved_system=3000)
    elif mode == OnboardingMode.GUIDED:
        config.security_mode = SecurityMode.STRICT
        config.compliance = list(ComplianceFramework)
    elif mode == OnboardingMode.CI:
        config.minimal_context = True
        config.token_budget = TokenBudget(input_limit=8000, output_limit=3000, reserved_system=1500)

    # Auto-detect agents
    for agent_file, platform in [
        ("CLAUDE.md", AgentPlatform.CLAUDE),
        (".cursorrules", AgentPlatform.CURSOR),
        (".github/copilot-instructions.md", AgentPlatform.COPILOT),
        (".aider.conf.yml", AgentPlatform.AIDER),
        (".windsurfrules", AgentPlatform.WINDSURF),
    ]:
        if (project_root / agent_file).exists():
            config.agents.append(platform)

    # Default to Claude + Copilot if none detected
    if not config.agents:
        config.agents = [AgentPlatform.CLAUDE, AgentPlatform.COPILOT]

    # Karpathy guidelines on by default for all modes
    config.karpathy_guidelines = True
    config.scanner_enabled = True

    return config


def save_config(config: ProjectConfig, project_root: Path) -> Path:
    """Save config to .agentra.yml."""
    cfg_path = project_root / CONFIG_FILE
    data = {
        "project": {
            "name": config.project_name,
            "languages": config.languages,
            "frameworks": config.frameworks,
            "sdks": config.sdks,
            "databases": config.databases,
        },
        "security": {
            "mode": config.security_mode.value,
            "edr_safe": config.edr_safe,
            "compliance": [c.value for c in config.compliance],
        },
        "optimization": {
            "minimal_context": config.minimal_context,
            "token_budget": {
                "input": config.token_budget.input_limit,
                "output": config.token_budget.output_limit,
            },
        },
        "agents": [a.value for a in config.agents],
        "skills": config.skills,
        "karpathy_guidelines": config.karpathy_guidelines,
        "scanner_enabled": config.scanner_enabled,
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    return cfg_path


def load_config(project_root: Path) -> ProjectConfig | None:
    """Load config from .agentra.yml if it exists."""
    cfg_path = project_root / CONFIG_FILE
    if not cfg_path.exists():
        return None

    with open(cfg_path, encoding="utf-8") as f:
        data = yaml.load(f)

    if not data:
        return None

    project = data.get("project", {})
    security = data.get("security", {})
    optimization = data.get("optimization", {})
    budget_data = optimization.get("token_budget", {})

    return ProjectConfig(
        project_name=project.get("name", ""),
        languages=project.get("languages", []),
        frameworks=project.get("frameworks", []),
        sdks=project.get("sdks", []),
        databases=project.get("databases", []),
        security_mode=SecurityMode(security.get("mode", "standard")),
        edr_safe=security.get("edr_safe", True),
        minimal_context=optimization.get("minimal_context", True),
        token_budget=TokenBudget(
            input_limit=budget_data.get("input", 12000),
            output_limit=budget_data.get("output", 4000),
        ),
        karpathy_guidelines=data.get("karpathy_guidelines", True),
        scanner_enabled=data.get("scanner_enabled", True),
        agents=[AgentPlatform(a) for a in data.get("agents", [])],
        skills=data.get("skills", []),
        compliance=[ComplianceFramework(c) for c in security.get("compliance", [])],
    )
