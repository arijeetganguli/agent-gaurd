"""Agent Integration Adapters — generate optimized configs for each agent platform."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from agentra.governance.engine import GovernanceEngine
from agentra.models import AgentPlatform, ProjectConfig, StackProfile
from agentra.optimizer.engine import TokenOptimizer

if TYPE_CHECKING:
    from agentra.rag.engine import CodeRAGEngine


class AgentAdapter(Protocol):
    """Protocol for agent-specific output adapters."""

    platform: AgentPlatform

    def generate(
        self,
        config: ProjectConfig,
        stack: StackProfile,
        governance: GovernanceEngine,
        optimizer: TokenOptimizer,
        rag_engine: "CodeRAGEngine | None" = None,
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


def _build_rag_usage_block(config: ProjectConfig) -> str:
    """Instructions telling the agent how to use Agentra's RAG and knowledge graph."""
    if not config.rag_config.enabled:
        return ""
    return """\
## Agentra Code Intelligence (RAG + Knowledge Graph)

This project is indexed by Agentra's built-in semantic code search and anti-pattern
detector. **Always consult the knowledge graph before writing new code.**

### Before Implementing Any New Function, Class, or Module
```sh
# Find semantically similar existing code (prevents duplication)
ag rag "<short description of what you want to build>"

# Review known code smells to avoid repeating them
ag patterns
```

### After Completing a Task
```sh
# Verify no new anti-patterns were introduced
ag patterns --severity high

# Rebuild the index when significant new code has been added
ag index
```

### Rules
- If `ag rag` returns a similar chunk (high relevance), **reuse or extend it** — never duplicate.
- Never introduce any pattern listed in the "Known Code Smells" section.
- Run `ag patterns` as a final check before marking a task complete.
"""


def _build_model_block(platform_value: str, config: ProjectConfig) -> str:
    """Emit the recommended model for this agent platform, with per-purpose routing when available."""
    from agentra.models import AGENT_PURPOSES, KNOWN_MODELS

    # Platforms where the host controls model selection — can't switch programmatically
    _host_controlled = {"copilot", "cursor", "windsurf"}

    model = config.model_preferences.get(platform_value, "")
    if not model:
        return ""
    choices = KNOWN_MODELS.get(platform_value, [])
    choices_str = ", ".join(f"`{m}`" for m in choices) if choices else ""
    lines = [
        "## Model Preference",
        f"- **Active model**: `{model}` *(auto-selected by Agentra)*",
    ]
    if choices_str:
        lines.append(f"- **Available models**: {choices_str}")
    lines.append("- To change: `ag model set <platform> <model>` or re-run `ag init --model <model>`")

    if platform_value in _host_controlled:
        lines.append(
            "> **Note**: Model selection on this platform is controlled by the IDE host. "
            "Available models may vary by plan or enterprise policy. "
            "If uncertain which model version is active, state it at the start of your response."
        )

    # Per-purpose routing block
    purpose_map = config.model_purpose_preferences.get(platform_value, {})
    if purpose_map:
        lines.append("")
        lines.append("### Model Routing by Purpose")
        lines.append("Capability-class routing — Agentra picks the right model for each task type:")
        purpose_labels = {
            "planning":      "🗺️  Planning / Architecture",
            "reasoning":     "🧠 Reasoning / Analysis",
            "review":        "🔍 Review / Code Audit",
            "coding":        "💻 Coding / Implementation",
            "testing":       "🧪 Testing / QA",
            "refactoring":   "🔧 Refactoring",
            "documentation": "📝 Documentation",
            "general":       "⚡ General / Default",
            "formatting":    "✨ Formatting / Transform",
        }
        for purpose in AGENT_PURPOSES:
            purpose_model = purpose_map.get(purpose)
            if not purpose_model:
                continue
            label = purpose_labels.get(purpose, purpose.capitalize())
            lines.append(f"- **{label}**: `{purpose_model}`")
        lines.append(
            f"- To override: `ag model set {platform_value} <model> --purpose <purpose>`"
        )

    lines.append("")
    return "\n".join(lines) + "\n"


def _build_codebase_patterns_block(rag_engine: "CodeRAGEngine | None") -> str:
    """
    Inject project-specific patterns and known code smells into agent files.
    Returns an empty string when no RAG index is available.
    """
    if rag_engine is None:
        return ""

    try:
        top_patterns = rag_engine.top_patterns_summary(3)
        antipatterns = rag_engine.project_antipatterns()

        if not top_patterns and not antipatterns:
            return ""

        lines = ["## Codebase Patterns (auto-indexed)"]
        lines.append("")
        lines.append(
            "> These patterns were extracted from this codebase by the Agentra knowledge graph. "
            "Follow established patterns and avoid repeating the flagged smells."
        )
        lines.append("")

        if top_patterns:
            lines.append("### Established Patterns")
            lines.append("Follow these patterns when adding new code:")
            lines.extend(top_patterns)
            lines.append("")

        if antipatterns:
            # Show top-5 highest-severity smells only to keep tokens low
            sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            top_smells = sorted(antipatterns, key=lambda x: sev_order.get(x.severity.value, 5))[:5]
            lines.append("### Known Code Smells (do NOT repeat these)")
            for ap in top_smells:
                short_path = ap.file_path.split("/")[-1] if "/" in ap.file_path else ap.file_path.split("\\")[-1]
                lines.append(
                    f"- **[{ap.severity.value.upper()}] {ap.name}** in `{short_path}:{ap.line}` — "
                    f"{ap.suggestion}"
                )
            lines.append("")

        return "\n".join(lines) + "\n"

    except Exception:  # noqa: BLE001
        return ""


def _build_testing_block(stack: StackProfile) -> str:
    """Build testing instructions with framework recommendations based on detected stack."""
    # Map languages/frameworks to test frameworks
    test_frameworks: list[str] = []
    lang_names = {c.name.lower() for c in stack.languages}
    fw_names = {c.name.lower() for c in stack.frameworks}
    all_names = lang_names | fw_names

    if "python" in lang_names:
        test_frameworks.append("pytest (Python)")
    if "typescript" in lang_names or "javascript" in lang_names:
        if "react" in fw_names or "next.js" in fw_names or "nextjs" in fw_names:
            test_frameworks.append("Vitest or Jest + React Testing Library (React/Next.js)")
        elif "vue" in fw_names or "nuxt" in fw_names:
            test_frameworks.append("Vitest (Vue/Nuxt)")
        elif "angular" in fw_names:
            test_frameworks.append("Jest or Karma + Jasmine (Angular)")
        else:
            test_frameworks.append("Vitest or Jest (JavaScript/TypeScript)")
        if any(fw in all_names for fw in ("express", "fastify", "nestjs", "nest.js")):
            test_frameworks.append("Supertest (HTTP integration tests)")
        if any(fw in all_names for fw in ("playwright", "cypress")):
            test_frameworks.append("Playwright or Cypress (E2E)")
    if "rust" in lang_names:
        test_frameworks.append("cargo test (Rust built-in)")
    if "go" in lang_names or "golang" in lang_names:
        test_frameworks.append("go test (Go built-in)")
    if "java" in lang_names or "kotlin" in lang_names:
        if "spring" in fw_names or "spring boot" in fw_names:
            test_frameworks.append("JUnit 5 + Spring Boot Test (Java/Kotlin)")
        else:
            test_frameworks.append("JUnit 5 (Java/Kotlin)")
    if "c#" in lang_names or "csharp" in lang_names or ".net" in all_names:
        test_frameworks.append("xUnit or NUnit (.NET)")
    if "ruby" in lang_names:
        if "rails" in fw_names:
            test_frameworks.append("RSpec + FactoryBot (Rails)")
        else:
            test_frameworks.append("RSpec or Minitest (Ruby)")
    if "swift" in lang_names:
        test_frameworks.append("XCTest (Swift)")
    if "php" in lang_names:
        test_frameworks.append("PHPUnit (PHP)")

    # FastAPI-specific
    if "fastapi" in fw_names:
        test_frameworks.append("httpx + pytest (FastAPI async testing)")
    # Django-specific
    if "django" in fw_names:
        test_frameworks.append("Django TestCase + pytest-django")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for tf in test_frameworks:
        if tf not in seen:
            seen.add(tf)
            unique.append(tf)

    lines = [
        "## Testing Requirements",
        "",
        "### TDD Mandate — Always Follow Test-Driven Development",
        "**TDD is non-negotiable.** Every feature, fix, and refactor follows this cycle:",
        "1. **Red** — Write a failing test that defines the expected behaviour.",
        "2. **Green** — Write the minimum code to make it pass. Nothing more.",
        "3. **Refactor** — Clean up without breaking the test.",
        "",
        "Never write implementation code before a test exists for it.",
        "",
        "### Mandatory Testing Workflow",
        "- **Always write tests** for any new or modified code before considering a task complete.",
        "- **Run the full relevant test suite** after every code change to catch regressions immediately.",
        "- Follow the Red-Green-Refactor cycle: write a failing test first, make it pass, then clean up.",
        "- For bug fixes, write a test that reproduces the bug before writing the fix.",
        "- Aim for meaningful coverage — test behavior and edge cases, not just lines.",
        "- Keep tests fast, isolated, and deterministic. Mock external dependencies.",
        "- Never skip or disable failing tests to make a build pass — fix the root cause.",
    ]

    if unique:
        lines.append("")
        lines.append("### Recommended Test Frameworks (based on detected stack)")
        for tf in unique:
            lines.append(f"- {tf}")

    lines.append("")
    return "\n".join(lines) + "\n"


# ── Claude Adapter ───────────────────────────────────────────────────────────

class ClaudeAdapter:
    platform = AgentPlatform.CLAUDE

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer,
                 rag_engine: "CodeRAGEngine | None" = None) -> dict[str, str]:
        parts = [
            _build_header("Claude Code (CLAUDE.md)"),
            _build_model_block(AgentPlatform.CLAUDE.value, config),
            _build_karpathy_block() if config.karpathy_guidelines else "",
            _build_stack_block(stack),
            _build_testing_block(stack),
            _build_security_block(governance, optimizer),
            _build_codebase_patterns_block(rag_engine) if config.rag_config.include_in_agent_files else "",
            _build_rag_usage_block(config),
            _build_skills_block(config),
        ]
        return {"CLAUDE.md": "\n".join(p for p in parts if p)}


# ── Cursor Adapter ───────────────────────────────────────────────────────────

class CursorAdapter:
    platform = AgentPlatform.CURSOR

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer,
                 rag_engine: "CodeRAGEngine | None" = None) -> dict[str, str]:
        parts = [
            _build_header("Cursor (.cursorrules)"),
            _build_model_block(AgentPlatform.CURSOR.value, config),
            _build_karpathy_block() if config.karpathy_guidelines else "",
            _build_stack_block(stack),
            _build_testing_block(stack),
            _build_security_block(governance, optimizer),
            _build_codebase_patterns_block(rag_engine) if config.rag_config.include_in_agent_files else "",
            _build_rag_usage_block(config),
            _build_skills_block(config),
        ]
        return {".cursorrules": "\n".join(p for p in parts if p)}


# ── GitHub Copilot Adapter ───────────────────────────────────────────────────

class CopilotAdapter:
    platform = AgentPlatform.COPILOT

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer,
                 rag_engine: "CodeRAGEngine | None" = None) -> dict[str, str]:
        parts = [
            _build_header("GitHub Copilot"),
            _build_model_block(AgentPlatform.COPILOT.value, config),
            _build_karpathy_block() if config.karpathy_guidelines else "",
            _build_stack_block(stack),
            _build_testing_block(stack),
            _build_security_block(governance, optimizer),
            _build_codebase_patterns_block(rag_engine) if config.rag_config.include_in_agent_files else "",
            _build_rag_usage_block(config),
            _build_skills_block(config),
        ]
        return {".github/copilot-instructions.md": "\n".join(p for p in parts if p)}


# ── Aider Adapter ────────────────────────────────────────────────────────────

class AiderAdapter:
    platform = AgentPlatform.AIDER

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer,
                 rag_engine: "CodeRAGEngine | None" = None) -> dict[str, str]:
        parts = [
            _build_header("Aider (.aider.conf.yml)"),
            _build_model_block(AgentPlatform.AIDER.value, config),
            _build_stack_block(stack),
            _build_testing_block(stack),
            _build_security_block(governance, optimizer),
            _build_codebase_patterns_block(rag_engine) if config.rag_config.include_in_agent_files else "",
            _build_rag_usage_block(config),
        ]
        content = "\n".join(p for p in parts if p)
        # Wrap in YAML conventions block
        yaml_content = "# Aider conventions\nconventions: |\n"
        for line in content.splitlines():
            yaml_content += f"  {line}\n"
        return {".aider.conf.yml": yaml_content}


# ── Windsurf Adapter ─────────────────────────────────────────────────────────

class WindsurfAdapter:
    platform = AgentPlatform.WINDSURF

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer,
                 rag_engine: "CodeRAGEngine | None" = None) -> dict[str, str]:
        parts = [
            _build_header("Windsurf"),
            _build_model_block(AgentPlatform.WINDSURF.value, config),
            _build_karpathy_block() if config.karpathy_guidelines else "",
            _build_stack_block(stack),
            _build_testing_block(stack),
            _build_security_block(governance, optimizer),
            _build_codebase_patterns_block(rag_engine) if config.rag_config.include_in_agent_files else "",
            _build_rag_usage_block(config),
            _build_skills_block(config),
        ]
        return {".windsurfrules": "\n".join(p for p in parts if p)}


# ── Continue.dev Adapter ─────────────────────────────────────────────────────

class ContinueAdapter:
    platform = AgentPlatform.CONTINUE

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer,
                 rag_engine: "CodeRAGEngine | None" = None) -> dict[str, str]:
        import json
        instructions = governance.generate_instructions()
        compressed = optimizer.compress_instructions(instructions)
        patterns_block = _build_codebase_patterns_block(rag_engine) if config.rag_config.include_in_agent_files else ""
        rag_block = _build_rag_usage_block(config)
        system_msg = "\n".join(p for p in [compressed, patterns_block, rag_block] if p)
        model = config.model_preferences.get(AgentPlatform.CONTINUE.value, "")
        models_cfg = [{"title": model, "model": model, "provider": "ollama"}] if model else []
        cfg = {
            "systemMessage": system_msg[:4000],
            "models": models_cfg,
        }
        return {".continue/config.json": json.dumps(cfg, indent=2)}


# ── AGENTS.md Adapter (universal) ────────────────────────────────────────────

class AgentsMdAdapter:
    platform = AgentPlatform.CLAUDE  # generic

    def generate(self, config: ProjectConfig, stack: StackProfile,
                 governance: GovernanceEngine, optimizer: TokenOptimizer,
                 rag_engine: "CodeRAGEngine | None" = None) -> dict[str, str]:
        parts = [
            _build_header("AGENTS.md \u2014 Universal Agent Instructions"),
            _build_karpathy_block() if config.karpathy_guidelines else "",
            _build_stack_block(stack),
            _build_testing_block(stack),
            _build_security_block(governance, optimizer),
            _build_codebase_patterns_block(rag_engine) if config.rag_config.include_in_agent_files else "",
            _build_rag_usage_block(config),
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
    rag_engine: "CodeRAGEngine | None" = None,
) -> dict[str, str]:
    """Generate config files for all requested agents. Returns {path: content}."""
    outputs: dict[str, str] = {}
    for agent in agents:
        adapter = ADAPTER_REGISTRY.get(agent)
        if adapter:
            outputs.update(adapter.generate(config, stack, governance, optimizer, rag_engine))
    # Always include AGENTS.md
    agents_adapter = AgentsMdAdapter()
    outputs.update(agents_adapter.generate(config, stack, governance, optimizer, rag_engine))
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
