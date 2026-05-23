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

