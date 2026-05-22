"""Security Governance Engine — policy enforcement and risk scoring."""

from __future__ import annotations

import re
from pathlib import Path

from agentra.models import (
    GovernanceResult,
    PolicyViolation,
    Severity,
    StackProfile,
)
from agentra.governance.policies import ALL_POLICIES, PolicyRule, get_policies_for_stack


# ── Severity weights for risk scoring ────────────────────────────────────────

_SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.CRITICAL: 10.0,
    Severity.HIGH: 6.0,
    Severity.MEDIUM: 3.0,
    Severity.LOW: 1.0,
    Severity.INFO: 0.0,
}


class GovernanceEngine:
    """Evaluates files and commands against security policies."""

    def __init__(self, stack: StackProfile | None = None, extra_policies: list[PolicyRule] | None = None):
        stack_names = [c.name for c in stack.all_components] if stack else ["all"]
        self.policies = get_policies_for_stack(stack_names)
        if extra_policies:
            self.policies.extend(extra_policies)

    def scan_text(self, text: str, source: str = "<inline>") -> list[PolicyViolation]:
        """Scan arbitrary text for policy violations."""
        violations: list[PolicyViolation] = []
        for policy in self.policies:
            if not policy.pattern:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if re.search(policy.pattern, line, re.IGNORECASE):
                    violations.append(PolicyViolation(
                        rule=policy,
                        file_path=source,
                        line=i,
                        context=line.strip()[:200],
                    ))
        return violations

    def scan_file(self, file_path: Path | str) -> list[PolicyViolation]:
        """Scan a single file for policy violations."""
        fp = Path(file_path)
        if not fp.is_file():
            return []
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            return []
        return self.scan_text(text, source=str(fp))

    def scan_directory(self, directory: Path | str, max_files: int = 500) -> list[PolicyViolation]:
        """Scan all text files in a directory tree."""
        root = Path(directory)
        skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
        violations: list[PolicyViolation] = []
        count = 0
        for f in root.rglob("*"):
            if any(part in skip for part in f.parts):
                continue
            if not f.is_file() or f.stat().st_size > 1_000_000:
                continue
            if f.suffix in (".pyc", ".exe", ".dll", ".so", ".whl", ".zip", ".tar", ".gz", ".png", ".jpg"):
                continue
            violations.extend(self.scan_file(f))
            count += 1
            if count >= max_files:
                break
        return violations

    def evaluate(self, violations: list[PolicyViolation]) -> GovernanceResult:
        """Compute risk score and blast radius from violations."""
        if not violations:
            return GovernanceResult(passed=True, explanation="No policy violations detected.")

        risk = sum(_SEVERITY_WEIGHT.get(v.rule.severity, 0) for v in violations)
        critical_count = sum(1 for v in violations if v.rule.severity == Severity.CRITICAL)
        high_count = sum(1 for v in violations if v.rule.severity == Severity.HIGH)

        if critical_count > 0:
            blast = "critical"
        elif high_count > 3:
            blast = "high"
        elif risk > 20:
            blast = "medium"
        else:
            blast = "low"

        passed = critical_count == 0 and risk < 15

        categories_hit = {v.rule.category.value for v in violations}
        explanation = (
            f"Found {len(violations)} violation(s) across {len(categories_hit)} "
            f"categor{'y' if len(categories_hit) == 1 else 'ies'}: "
            f"{', '.join(sorted(categories_hit))}. "
            f"Risk score: {risk:.1f}. Blast radius: {blast}."
        )

        return GovernanceResult(
            violations=violations,
            risk_score=round(risk, 2),
            blast_radius=blast,
            passed=passed,
            explanation=explanation,
        )

    def enforce(self, directory: Path | str) -> GovernanceResult:
        """Full scan + evaluate pipeline for a project directory."""
        violations = self.scan_directory(directory)
        return self.evaluate(violations)

    def generate_instructions(self) -> list[str]:
        """Generate agent instructions from active policies (for prompt injection)."""
        instructions: list[str] = []
        for p in sorted(self.policies, key=lambda x: _SEVERITY_WEIGHT.get(x.severity, 0), reverse=True):
            if p.instruction:
                instructions.append(f"[{p.severity.value.upper()}] {p.instruction}")
        return instructions
