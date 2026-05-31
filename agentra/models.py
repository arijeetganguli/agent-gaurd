"""Core data models for Agentra."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

# ── Enums ────────────────────────────────────────────────────────────────────

class Severity(enum.StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class PolicyCategory(enum.StrEnum):
    DATABASE = "database"
    EXECUTION = "execution"
    SECRET = "secret"  # noqa: S105
    GIT = "git"
    INFRASTRUCTURE = "infrastructure"
    PROMPT_INJECTION = "prompt_injection"
    RUNTIME = "runtime"
    VULNERABILITY = "vulnerability"


class ScanTarget(enum.StrEnum):
    SAST = "sast"
    DEPS = "deps"
    OWASP = "owasp"
    ALL = "all"


class ComplianceFramework(enum.StrEnum):
    SOC2 = "SOC2"
    ISO27001 = "ISO27001"
    PCI_DSS = "PCI_DSS"
    HIPAA = "HIPAA"
    NIST = "NIST"


class AgentPlatform(enum.StrEnum):
    CLAUDE = "claude"
    CURSOR = "cursor"
    COPILOT = "copilot"
    AIDER = "aider"
    WINDSURF = "windsurf"
    CONTINUE = "continue"
    ROO_CODE = "roo_code"
    OPENAI_CODEX = "openai_codex"


class SecurityMode(enum.StrEnum):
    STANDARD = "standard"
    ENTERPRISE = "enterprise"
    STRICT = "strict"


class OnboardingMode(enum.StrEnum):
    QUICK = "quick"
    GUIDED = "guided"
    ENTERPRISE = "enterprise"
    CI = "ci"


# ── Stack Detection ─────────────────────────────────────────────────────────

class DetectedComponent(BaseModel):
    name: str
    version: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = ""  # e.g. "pyproject.toml", "Dockerfile"


class StackProfile(BaseModel):
    languages: list[DetectedComponent] = Field(default_factory=list)
    frameworks: list[DetectedComponent] = Field(default_factory=list)
    databases: list[DetectedComponent] = Field(default_factory=list)
    cloud_providers: list[DetectedComponent] = Field(default_factory=list)
    sdks: list[DetectedComponent] = Field(default_factory=list)
    infrastructure: list[DetectedComponent] = Field(default_factory=list)
    ci_cd: list[DetectedComponent] = Field(default_factory=list)
    agents: list[DetectedComponent] = Field(default_factory=list)

    @property
    def all_components(self) -> list[DetectedComponent]:
        return (
            self.languages + self.frameworks + self.databases
            + self.cloud_providers + self.sdks + self.infrastructure
            + self.ci_cd + self.agents
        )

    @property
    def low_confidence(self) -> list[DetectedComponent]:
        return [c for c in self.all_components if c.confidence < 0.6]


# ── Security Policies ────────────────────────────────────────────────────────

class PolicyRule(BaseModel):
    id: str
    name: str
    description: str
    severity: Severity
    category: PolicyCategory
    pattern: str = ""  # regex or keyword pattern
    instruction: str = ""  # what to tell the agent
    environments: list[str] = Field(default_factory=lambda: ["all"])
    compliance: list[ComplianceFramework] = Field(default_factory=list)
    token_cost: int = 0  # estimated tokens for this rule
    enabled: bool = True
    stacks: list[str] = Field(default_factory=lambda: ["all"])


class PolicyViolation(BaseModel):
    rule: PolicyRule
    file_path: str | None = None
    line: int | None = None
    context: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GovernanceResult(BaseModel):
    violations: list[PolicyViolation] = Field(default_factory=list)
    risk_score: float = 0.0
    blast_radius: str = "low"
    passed: bool = True
    explanation: str = ""


# ── Token Optimization ───────────────────────────────────────────────────────

class TokenBudget(BaseModel):
    input_limit: int = 12000
    output_limit: int = 4000
    reserved_system: int = 2000


class OptimizationResult(BaseModel):
    original_tokens: int = 0
    optimized_tokens: int = 0
    reduction_pct: float = 0.0
    rules_included: int = 0
    rules_excluded: int = 0
    context_sections: list[str] = Field(default_factory=list)


# ── Skills ───────────────────────────────────────────────────────────────────

class Skill(BaseModel):
    id: str
    name: str
    description: str
    stacks: list[str] = Field(default_factory=list)
    instructions: str = ""
    templates: dict[str, str] = Field(default_factory=dict)
    policies: list[str] = Field(default_factory=list)
    optimization_rules: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


# ── Benchmarking ─────────────────────────────────────────────────────────────

class BenchmarkMetric(BaseModel):
    name: str
    before: float
    after: float
    unit: str = ""
    improvement_pct: float = 0.0
    description: str = ""


class SkillBenchmark(BaseModel):
    skill_id: str
    skill_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metrics: list[BenchmarkMetric] = Field(default_factory=list)
    verification_passed: bool = False
    verification_details: str = ""


class BenchmarkReport(BaseModel):
    project_name: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stack: StackProfile = Field(default_factory=StackProfile)
    governance: GovernanceResult = Field(default_factory=GovernanceResult)
    optimization: OptimizationResult = Field(default_factory=OptimizationResult)
    skill_benchmarks: list[SkillBenchmark] = Field(default_factory=list)


# ── Configuration ────────────────────────────────────────────────────────────

class IndexConfig(BaseModel):
    path: str = ".agentra"
    enabled: bool = True
    exclude: list[str] = Field(default_factory=lambda: ["node_modules", ".venv", "venv", "dist", "build", "__pycache__"])


class RAGConfig(BaseModel):
    enabled: bool = True
    top_k: int = 5
    antipatterns: bool = True
    include_in_agent_files: bool = True


# ── Model Preferences ────────────────────────────────────────────────────────

# Canonical model names per platform — updated to current 2026 releases.
# Ordered from most capable to fastest within each host.
KNOWN_MODELS: dict[str, list[str]] = {
    "claude": [
        "claude-opus-4-7",      # deep reasoning, planning, review
        "claude-sonnet-4-6",    # coding, documentation, balanced
        "claude-haiku-4-5",     # formatting, fast transforms
    ],
    "copilot": [
        "gpt-5.5",              # deep reasoning (o-series equivalent)
        "claude-4-7",           # deep reasoning alternative
        "gpt-5.3-codex",        # coding / implementation
        "gpt-5.4",              # balanced / documentation
        "gemini-3.1-pro",       # planning alternative
    ],
    "cursor": [
        "claude-4-7",           # deep reasoning
        "gpt-5.5",              # deep reasoning alternative
        "gpt-5.3-codex",        # coding
        "gemini-3.1-pro",       # balanced / planning
    ],
    "windsurf": [
        "gemini-3.1-pro",       # deep reasoning / planning
        "claude-sonnet-4-6",    # coding / balanced
        "gemini-3.1-flash",     # fast / formatting
    ],
    "aider": [
        "claude-4-7",           # deep reasoning (dynamic switch)
        "claude-sonnet-4-6",    # coding / balanced (dynamic switch)
        "gpt-5.5",              # deep reasoning alternative
        "gemini-3.1-pro",       # balanced / fast alternative
    ],
    "continue": [
        "claude-sonnet-4-6",    # best API-backed model
        "codellama",            # coding (local)
        "llama3",               # balanced (local)
        "mistral",              # fast / formatting (local)
        "gemini-3.1-flash",     # fast (API)
    ],
    "roo_code": [
        "claude-opus-4-7",      # deep reasoning
        "claude-sonnet-4-6",    # coding / balanced
        "gpt-5.5",              # deep reasoning alternative
    ],
    "openai_codex": [
        "gpt-5.5",              # deep reasoning
        "gpt-5.3-codex",        # coding / implementation
        "gpt-5.4",              # balanced / documentation
    ],
}

# ── Capability-Class Routing (inspired by routesmith) ───────────────────────
# Abstract capability classes decouple task intent from model names.
# Each host adapter maps capability → best native model for that host.
CAPABILITY_CLASSES: list[str] = ["deep_reasoning", "coding", "balanced", "fast"]

# Maps each user-facing purpose to the abstract capability class it needs
PURPOSE_CAPABILITY_MAP: dict[str, str] = {
    "planning":      "deep_reasoning",  # architecture, project design
    "reasoning":     "deep_reasoning",  # analysis, inference
    "review":        "deep_reasoning",  # code review, audit
    "coding":        "coding",          # implementation, feature work
    "testing":       "coding",          # writing tests, QA
    "refactoring":   "coding",          # structural changes, cleanup
    "documentation": "balanced",        # docs, explanations, READMEs
    "general":       "balanced",        # default / catch-all
    "formatting":    "fast",            # linting fixes, style transforms
}

# Best host-native model per capability class — chosen from what each host supports
CAPABILITY_MODELS: dict[str, dict[str, str]] = {
    "claude": {
        "deep_reasoning": "claude-opus-4-7",
        "coding":         "claude-sonnet-4-6",
        "balanced":       "claude-sonnet-4-6",
        "fast":           "claude-haiku-4-5",
    },
    "copilot": {
        "deep_reasoning": "gpt-5.5",
        "coding":         "gpt-5.3-codex",
        "balanced":       "gpt-5.4",
        "fast":           "gpt-5.4",
    },
    "cursor": {
        "deep_reasoning": "claude-4-7",
        "coding":         "gpt-5.3-codex",
        "balanced":       "gemini-3.1-pro",
        "fast":           "gemini-3.1-pro",
    },
    "windsurf": {
        "deep_reasoning": "gemini-3.1-pro",
        "coding":         "claude-sonnet-4-6",
        "balanced":       "claude-sonnet-4-6",
        "fast":           "gemini-3.1-flash",
    },
    "aider": {
        "deep_reasoning": "claude-4-7",
        "coding":         "claude-sonnet-4-6",
        "balanced":       "claude-sonnet-4-6",
        "fast":           "gemini-3.1-pro",
    },
    "continue": {
        "deep_reasoning": "claude-sonnet-4-6",
        "coding":         "codellama",
        "balanced":       "llama3",
        "fast":           "mistral",
    },
    "roo_code": {
        "deep_reasoning": "claude-opus-4-7",
        "coding":         "claude-sonnet-4-6",
        "balanced":       "claude-sonnet-4-6",
        "fast":           "claude-sonnet-4-6",
    },
    "openai_codex": {
        "deep_reasoning": "gpt-5.5",
        "coding":         "gpt-5.3-codex",
        "balanced":       "gpt-5.4",
        "fast":           "gpt-5.4",
    },
}

# User-facing purpose names — superset of routesmith task types
AGENT_PURPOSES: list[str] = [
    "planning", "reasoning", "review",
    "coding", "testing", "refactoring",
    "documentation", "general", "formatting",
]

# Derived: purpose → capability class → platform model (no hardcoding)
PURPOSE_MODELS: dict[str, dict[str, str]] = {
    platform: {
        purpose: CAPABILITY_MODELS[platform][PURPOSE_CAPABILITY_MAP[purpose]]
        for purpose in AGENT_PURPOSES
    }
    for platform in CAPABILITY_MODELS
}

# Derived: default model = balanced capability (good all-rounder for each host)
AGENT_DEFAULT_MODELS: dict[str, str] = {
    platform: CAPABILITY_MODELS[platform]["balanced"]
    for platform in CAPABILITY_MODELS
}

# ── Fallback chains ──────────────────────────────────────────────────────────
# When the primary model for a capability class is unavailable (enterprise
# restriction, plan limit, rollout gate), try these alternatives in order.
CAPABILITY_FALLBACK_CHAINS: dict[str, dict[str, list[str]]] = {
    "claude": {
        "deep_reasoning": ["claude-opus-4-7", "claude-sonnet-4-6"],
        "coding":         ["claude-sonnet-4-6", "claude-haiku-4-5"],
        "balanced":       ["claude-sonnet-4-6", "claude-haiku-4-5"],
        "fast":           ["claude-haiku-4-5", "claude-sonnet-4-6"],
    },
    "copilot": {
        "deep_reasoning": ["gpt-5.5", "claude-opus-4.7", "gemini-3.1-pro", "gpt-5.4"],
        "coding":         ["gpt-5.3-codex", "gpt-5.5", "gpt-5.4"],
        "balanced":       ["gpt-5.4", "gpt-5.5", "gemini-3.1-pro"],
        "fast":           ["gpt-5-mini", "gpt-5.4"],
    },
    "cursor": {
        "deep_reasoning": ["claude-4-7", "gpt-5.5", "gemini-3.1-pro"],
        "coding":         ["gpt-5.3-codex", "claude-4-7", "gemini-3.1-pro"],
        "balanced":       ["gemini-3.1-pro", "claude-sonnet-4-6"],
        "fast":           ["gemini-3.1-pro", "claude-sonnet-4-6"],
    },
    "windsurf": {
        "deep_reasoning": ["gemini-3.1-pro", "claude-sonnet-4-6"],
        "coding":         ["claude-sonnet-4-6", "gemini-3.1-flash"],
        "balanced":       ["claude-sonnet-4-6", "gemini-3.1-flash"],
        "fast":           ["gemini-3.1-flash", "claude-sonnet-4-6"],
    },
    "aider": {
        "deep_reasoning": ["claude-4-7", "gpt-5.5", "gemini-3.1-pro"],
        "coding":         ["claude-sonnet-4-6", "claude-4-7", "gemini-3.1-pro"],
        "balanced":       ["claude-sonnet-4-6", "gemini-3.1-pro"],
        "fast":           ["gemini-3.1-pro", "claude-sonnet-4-6"],
    },
    "continue": {
        "deep_reasoning": ["claude-sonnet-4-6", "llama3"],
        "coding":         ["codellama", "claude-sonnet-4-6"],
        "balanced":       ["llama3", "claude-sonnet-4-6"],
        "fast":           ["mistral", "llama3"],
    },
    "roo_code": {
        "deep_reasoning": ["claude-opus-4-7", "claude-sonnet-4-6", "gpt-5.5"],
        "coding":         ["claude-sonnet-4-6", "gpt-5.5"],
        "balanced":       ["claude-sonnet-4-6", "gpt-5.5"],
        "fast":           ["claude-sonnet-4-6"],
    },
    "openai_codex": {
        "deep_reasoning": ["gpt-5.5", "gpt-5.4"],
        "coding":         ["gpt-5.3-codex", "gpt-5.5"],
        "balanced":       ["gpt-5.4", "gpt-5.5"],
        "fast":           ["gpt-5.4"],
    },
}


def resolve_model_with_fallback(
    platform: str,
    capability_class: str,
    restricted: set[str] | None = None,
) -> str:
    """Return the best available model for (platform, capability_class).

    Skips any model in `restricted` (e.g. enterprise-blocked models) and
    returns the next best from the fallback chain. Falls back to the primary
    CAPABILITY_MODELS entry if the chain is exhausted.
    """
    chain = CAPABILITY_FALLBACK_CHAINS.get(platform, {}).get(capability_class, [])
    excluded = restricted or set()
    for model in chain:
        if model not in excluded:
            return model
    # Gracefully handle unknown platforms — return primary from chain or empty string
    primary = CAPABILITY_MODELS.get(platform, {}).get(capability_class, "")
    return primary


# ── Model detection helpers ──────────────────────────────────────────────────

def detect_active_models() -> dict[str, dict[str, str]]:
    """Probe the local environment for the currently active model per platform.

    Returns a dict: platform → {"model": str, "source": str}.
    Only platforms where evidence is found are included.
    """
    import json as _json
    import os as _os
    from pathlib import Path as _Path

    found: dict[str, dict[str, str]] = {}

    # ── Claude Code ──────────────────────────────────────────────────────────
    if m := _os.environ.get("CLAUDE_MODEL"):
        found["claude"] = {"model": m, "source": "CLAUDE_MODEL env"}
    else:
        settings_path = _Path.home() / ".claude" / "settings.json"
        if settings_path.exists():
            try:
                data = _json.loads(settings_path.read_text(encoding="utf-8"))
                if m := data.get("model"):
                    found["claude"] = {"model": m, "source": "~/.claude/settings.json"}
            except (OSError, ValueError):
                pass

    # ── GitHub Copilot (VS Code) ──────────────────────────────────────────────
    appdata = _os.environ.get("APPDATA", "")
    vscode_settings = _Path(appdata) / "Code" / "User" / "settings.json"
    if vscode_settings.exists():
        try:
            data = _json.loads(vscode_settings.read_text(encoding="utf-8"))
            for key in (
                "github.copilot.chat.defaultModels",
                "github.copilot.selectedModel",
                "github.copilot.advanced",
            ):
                v = data.get(key)
                if v and isinstance(v, str):
                    found["copilot"] = {"model": v, "source": f"settings.json:{key}"}
                    break
                if v and isinstance(v, dict) and "model" in v:
                    found["copilot"] = {"model": v["model"], "source": f"settings.json:{key}.model"}
                    break
        except (OSError, ValueError):
            pass

    # ── Aider ────────────────────────────────────────────────────────────────
    if m := _os.environ.get("AIDER_MODEL"):
        found["aider"] = {"model": m, "source": "AIDER_MODEL env"}

    # ── OpenAI / Codex ───────────────────────────────────────────────────────
    if m := _os.environ.get("OPENAI_MODEL") or _os.environ.get("CODEX_MODEL"):
        found["openai_codex"] = {"model": m, "source": "OPENAI_MODEL/CODEX_MODEL env"}

    # ── Google Gemini CLI ─────────────────────────────────────────────────────
    if m := _os.environ.get("GEMINI_MODEL") or _os.environ.get("GOOGLE_MODEL"):
        found["gemini_cli"] = {"model": m, "source": "GEMINI_MODEL/GOOGLE_MODEL env"}

    return found


class ProjectConfig(BaseModel):
    project_name: str = ""
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    sdks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    cloud_providers: list[str] = Field(default_factory=list)
    security_mode: SecurityMode = SecurityMode.STANDARD
    edr_safe: bool = True
    minimal_context: bool = True
    token_budget: TokenBudget = Field(default_factory=TokenBudget)
    agents: list[AgentPlatform] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    compliance: list[ComplianceFramework] = Field(default_factory=list)
    custom_policies: list[dict[str, Any]] = Field(default_factory=list)
    karpathy_guidelines: bool = True
    scanner_enabled: bool = True
    index_config: IndexConfig = Field(default_factory=IndexConfig)
    rag_config: RAGConfig = Field(default_factory=RAGConfig)
    # platform.value → model name; populated by auto-selection or --model override
    model_preferences: dict[str, str] = Field(default_factory=dict)
    # platform.value → purpose → model name; per-purpose routing in auto mode
    model_purpose_preferences: dict[str, dict[str, str]] = Field(default_factory=dict)


# ── Execution ────────────────────────────────────────────────────────────────

class ExecutionRequest(BaseModel):
    command: str
    working_dir: str = "."
    sandbox: bool = True
    dry_run: bool = True
    requires_approval: bool = True
    timeout_seconds: int = 30


class ExecutionResult(BaseModel):
    approved: bool = False
    executed: bool = False
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    sandbox_path: str | None = None
    artifacts: list[str] = Field(default_factory=list)


# ── Audit ────────────────────────────────────────────────────────────────────

class AuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action: str
    actor: str = "agentra"
    details: dict[str, Any] = Field(default_factory=dict)
    risk_level: Severity = Severity.INFO


# ── Vulnerability Scanning ───────────────────────────────────────────────────

class ScanResult(BaseModel):
    tool: str  # "bandit", "pip-audit", "npm-audit", "owasp-patterns", etc.
    severity: Severity
    file_path: str | None = None
    line: int | None = None
    finding: str = ""
    rule_id: str = ""
    cve_id: str | None = None
    fix_available: bool = False
    fix_description: str = ""
    owasp_category: str = ""  # e.g. "A01 Broken Access Control"


class VulnerabilityReport(BaseModel):
    scan_targets: list[ScanTarget] = Field(default_factory=list)
    results: list[ScanResult] = Field(default_factory=list)
    risk_score: float = 0.0
    passed: bool = True
    scan_duration_ms: int = 0
    tools_available: list[str] = Field(default_factory=list)
    tools_missing: list[str] = Field(default_factory=list)
    summary: str = ""

    @property
    def critical_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.LOW)


# ── Code Index (Knowledge Graph) ─────────────────────────────────────────────

class SymbolKind(enum.StrEnum):
    FUNCTION = "function"
    CLASS = "class"
    IMPORT = "import"
    VARIABLE = "variable"
    METHOD = "method"


class IndexedFile(BaseModel):
    path: str
    content_hash: str
    language: str
    symbols_count: int = 0
    last_indexed: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CodeSymbol(BaseModel):
    file_path: str
    name: str
    kind: SymbolKind
    line_start: int
    line_end: int
    signature: str = ""
    docstring: str = ""


class AntiPattern(BaseModel):
    pattern_id: str
    name: str
    description: str
    severity: Severity
    file_path: str
    line: int
    context: str = ""
    suggestion: str = ""


class IndexReport(BaseModel):
    files_indexed: int = 0
    files_skipped: int = 0
    symbols_extracted: int = 0
    antipatterns_found: int = 0
    duration_seconds: float = 0.0
    incremental: bool = False
    projected: bool = False  # True when no index exists and values are estimated


class RAGResult(BaseModel):
    query_text: str = ""
    similar_chunks: list[tuple[str, int, float]] = Field(default_factory=list)  # (file, line, score)
    antipatterns: list[AntiPattern] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


# ── Enterprise Config Extensions ──────────────────────────────────────────────
# (IndexConfig and RAGConfig are defined above, before ProjectConfig)

