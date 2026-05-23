"""Agent Integration Adapters — generate optimized configs for each agent platform."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from agentra.governance.engine import GovernanceEngine
from agentra.models import AgentPlatform, ProjectConfig, StackProfile
from agentra.optimizer.engine import TokenOptimizer


class AgentAdapter(Protocol):
    """Protocol for agent-specific output adapters."""

    platform: AgentPlatform

    def generate(
        self,
        config: ProjectConfig,
        stack: StackProfile,
        governance: GovernanceEngine,
        optimizer: TokenOptimizer,
    ) -> dict[str, str]:
        """Return {filename: content} for this agent platform."""
        ...


# ── Shared helpers ───────────────────────────────────────────────────────────

def _build_header(platform_name: str) -> str:
    return (
        f"# Agentra — {platform_name} Instructions\n"
        f"# Auto-generated. Do not edit manually.\n"
        f"# Regenerate with: ag init\n\n"
    )


def _build_security_block(governance: GovernanceEngine, optimizer: TokenOptimizer) -> str:
    instructions = governance.generate_instructions()
    compressed = optimizer.compress_instructions(instructions)
    return f"## Security & Governance\n{compressed}\n"


def _build_karpathy_block() -> str:
    return """\
## Karpathy Coding Guidelines (Universal — All Code Writing)

### 1. Think Before Coding
- State assumptions explicitly. If uncertain, ask — never guess silently.
- Present multiple interpretations instead of picking one without disclosure.
- If a simpler approach exists, say so and push back when warranted.
- Stop and name what's confusing rather than making assumptions.

### 2. Simplicity First
- Write the minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked. No abstractions for single-use code.
- No "flexibility" that wasn't requested. No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it.

### 3. Surgical Changes
- Touch only what you must. Never improve adjacent code that wasn't in scope.
- Don't refactor things that aren't broken. Match existing style.
- Every changed line must trace directly to the user's request.
- Remove imports/vars/functions YOUR changes made unused — not pre-existing dead code.

### 4. Goal-Driven Execution
- Transform tasks into verifiable goals with explicit success criteria.
- For multi-step tasks, state a brief plan with verify steps before starting.
- "Fix the bug" → "Write a test that reproduces it, then make it pass."
"""


def _build_stack_block(stack: StackProfile) -> str:
    lines = ["## Detected Stack"]
    for cat, label in [
        ("languages", "Languages"),
        ("frameworks", "Frameworks"),
        ("databases", "Databases"),
        ("sdks", "SDKs"),
        ("infrastructure", "Infrastructure"),
    ]:
        components = getattr(stack, cat)
        if components:
            names = ", ".join(c.name for c in components)
            lines.append(f"- **{label}**: {names}")
    return "\n".join(lines) + "\n"


def _build_skills_block(config: ProjectConfig) -> str:
    if not config.skills:
        return ""
    lines = ["## Active Skills"]
    for s in config.skills:
        lines.append(f"- {s}")
    return "\n".join(lines) + "\n"


# ── Claude Adapter ───────────────────────────────────────────────────────────

class ClaudeAdapter:
    platform = AgentPlatform.CLAUDE

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer) -> dict[str, str]:
        parts = [
            _build_header("Claude Code (CLAUDE.md)"),
            _build_karpathy_block() if config.karpathy_guidelines else "",
            _build_stack_block(stack),
            _build_security_block(governance, optimizer),
            _build_skills_block(config),
        ]
        return {"CLAUDE.md": "\n".join(p for p in parts if p)}


# ── Cursor Adapter ───────────────────────────────────────────────────────────

class CursorAdapter:
    platform = AgentPlatform.CURSOR

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer) -> dict[str, str]:
        parts = [
            _build_header("Cursor (.cursorrules)"),
            _build_karpathy_block() if config.karpathy_guidelines else "",
            _build_stack_block(stack),
            _build_security_block(governance, optimizer),
            _build_skills_block(config),
        ]
        return {".cursorrules": "\n".join(p for p in parts if p)}


# ── GitHub Copilot Adapter ───────────────────────────────────────────────────

class CopilotAdapter:
    platform = AgentPlatform.COPILOT

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer) -> dict[str, str]:
        parts = [
            _build_header("GitHub Copilot"),
            _build_karpathy_block() if config.karpathy_guidelines else "",
            _build_stack_block(stack),
            _build_security_block(governance, optimizer),
            _build_skills_block(config),
        ]
        return {".github/copilot-instructions.md": "\n".join(p for p in parts if p)}


# ── Aider Adapter ────────────────────────────────────────────────────────────

class AiderAdapter:
    platform = AgentPlatform.AIDER

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer) -> dict[str, str]:
        parts = [
            _build_header("Aider (.aider.conf.yml)"),
            _build_stack_block(stack),
            _build_security_block(governance, optimizer),
        ]
        content = "\n".join(parts)
        # Wrap in YAML conventions block
        yaml_content = "# Aider conventions\nconventions: |\n"
        for line in content.splitlines():
            yaml_content += f"  {line}\n"
        return {".aider.conf.yml": yaml_content}


# ── Windsurf Adapter ─────────────────────────────────────────────────────────

class WindsurfAdapter:
    platform = AgentPlatform.WINDSURF

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer) -> dict[str, str]:
        parts = [
            _build_header("Windsurf"),
            _build_karpathy_block() if config.karpathy_guidelines else "",
            _build_stack_block(stack),
            _build_security_block(governance, optimizer),
            _build_skills_block(config),
        ]
        return {".windsurfrules": "\n".join(p for p in parts if p)}


# ── Continue.dev Adapter ─────────────────────────────────────────────────────

class ContinueAdapter:
    platform = AgentPlatform.CONTINUE

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer) -> dict[str, str]:
        import json
        instructions = governance.generate_instructions()
        compressed = optimizer.compress_instructions(instructions)
        cfg = {
            "systemMessage": compressed[:4000],
            "models": [],
        }
        return {".continue/config.json": json.dumps(cfg, indent=2)}


# ── AGENTS.md Adapter (universal) ────────────────────────────────────────────

class AgentsMdAdapter:
    platform = AgentPlatform.CLAUDE  # generic

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer) -> dict[str, str]:
        parts = [
            _build_header("AGENTS.md — Universal Agent Instructions"),
            _build_karpathy_block() if config.karpathy_guidelines else "",
            _build_stack_block(stack),
            _build_security_block(governance, optimizer),
            _build_skills_block(config),
            "\n## Execution Safety\n"
            "- Always dry-run destructive commands first\n"
            "- Never execute code that modifies production data without approval\n"
            "- Sandbox all generated code execution\n"
            "- Create rollback scripts before schema changes\n",
        ]
        return {"AGENTS.md": "\n".join(p for p in parts if p)}


# ── Registry ─────────────────────────────────────────────────────────────────

ADAPTER_REGISTRY: dict[AgentPlatform, AgentAdapter] = {
    AgentPlatform.CLAUDE: ClaudeAdapter(),
    AgentPlatform.CURSOR: CursorAdapter(),
    AgentPlatform.COPILOT: CopilotAdapter(),
    AgentPlatform.AIDER: AiderAdapter(),
    AgentPlatform.WINDSURF: WindsurfAdapter(),
    AgentPlatform.CONTINUE: ContinueAdapter(),
}


def generate_for_agents(
    agents: list[AgentPlatform],
    config: ProjectConfig,
    stack: StackProfile,
    governance: GovernanceEngine,
    optimizer: TokenOptimizer,
) -> dict[str, str]:
    """Generate config files for all requested agents. Returns {path: content}."""
    outputs: dict[str, str] = {}
    for agent in agents:
        adapter = ADAPTER_REGISTRY.get(agent)
        if adapter:
            outputs.update(adapter.generate(config, stack, governance, optimizer))
    # Always include AGENTS.md
    agents_adapter = AgentsMdAdapter()
    outputs.update(agents_adapter.generate(config, stack, governance, optimizer))
    return outputs


def write_agent_files(output_dir: Path, files: dict[str, str]) -> list[Path]:
    """Write generated agent files to disk."""
    written: list[Path] = []
    for rel_path, content in files.items():
        fp = output_dir / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        written.append(fp)
    return written


def generate_claude_plugin(output_dir: Path, config: ProjectConfig | None = None) -> list[Path]:
    """Generate a Claude Code plugin package at output_dir."""
    from agentra.plugin.generator import PluginGenerator
    generator = PluginGenerator()
    return generator.generate(output_dir, config)
