"""Risk scoring engine — blast radius estimation and risk classification."""

from __future__ import annotations

from agentra.models import GovernanceResult, PolicyViolation, Severity


_SEVERITY_IMPACT: dict[Severity, float] = {
    Severity.CRITICAL: 10.0,
    Severity.HIGH: 6.0,
    Severity.MEDIUM: 3.0,
    Severity.LOW: 1.0,
    Severity.INFO: 0.0,
}


def compute_risk_score(violations: list[PolicyViolation]) -> float:
    return sum(_SEVERITY_IMPACT.get(v.rule.severity, 0) for v in violations)


def estimate_blast_radius(violations: list[PolicyViolation]) -> str:
    categories = {v.rule.category.value for v in violations}
    critical = sum(1 for v in violations if v.rule.severity == Severity.CRITICAL)
    if critical > 0 or len(categories) >= 4:
        return "critical"
    if len(categories) >= 3 or sum(1 for v in violations if v.rule.severity == Severity.HIGH) > 3:
        return "high"
    if len(categories) >= 2:
        return "medium"
    return "low"


def generate_rollback_suggestions(violations: list[PolicyViolation]) -> list[str]:
    """Generate rollback suggestions based on violation categories."""
    suggestions: list[str] = []
    categories = {v.rule.category.value for v in violations}

    if "database" in categories:
        suggestions.append("Generate database rollback migration before applying changes.")
    if "infrastructure" in categories:
        suggestions.append("Run terraform plan to preview changes; keep previous state backup.")
    if "git" in categories:
        suggestions.append("Create git stash or backup branch before proceeding.")
    if "execution" in categories:
        suggestions.append("Review execution artifacts in sandbox directory before promoting.")

    return suggestions
