"""Compliance Engine — map policies to compliance frameworks."""

from __future__ import annotations

from agent_guard.models import ComplianceFramework, GovernanceResult, PolicyViolation
from agent_guard.governance.policies import ALL_POLICIES, PolicyRule


# ── Framework descriptions ───────────────────────────────────────────────────

FRAMEWORK_INFO: dict[ComplianceFramework, dict[str, str]] = {
    ComplianceFramework.SOC2: {
        "name": "SOC 2 Type II",
        "description": "Service Organization Control — security, availability, processing integrity, confidentiality, privacy.",
        "focus": "Access control, change management, risk assessment, monitoring.",
    },
    ComplianceFramework.ISO27001: {
        "name": "ISO/IEC 27001",
        "description": "Information Security Management System standard.",
        "focus": "Risk management, access control, cryptography, operations security.",
    },
    ComplianceFramework.PCI_DSS: {
        "name": "PCI DSS v4.0",
        "description": "Payment Card Industry Data Security Standard.",
        "focus": "Network security, data protection, access control, monitoring, testing.",
    },
    ComplianceFramework.HIPAA: {
        "name": "HIPAA",
        "description": "Health Insurance Portability and Accountability Act.",
        "focus": "PHI protection, encryption, access controls, audit trails.",
    },
    ComplianceFramework.NIST: {
        "name": "NIST Cybersecurity Framework",
        "description": "National Institute of Standards and Technology framework.",
        "focus": "Identify, Protect, Detect, Respond, Recover.",
    },
}


class ComplianceEngine:
    """Maps policies and violations to compliance frameworks."""

    def get_policies_for_framework(self, framework: ComplianceFramework) -> list[PolicyRule]:
        return [p for p in ALL_POLICIES if framework in p.compliance and p.enabled]

    def get_compliance_coverage(self) -> dict[ComplianceFramework, int]:
        """Return count of policies per compliance framework."""
        coverage: dict[ComplianceFramework, int] = {}
        for fw in ComplianceFramework:
            coverage[fw] = len(self.get_policies_for_framework(fw))
        return coverage

    def map_violations_to_frameworks(
        self, violations: list[PolicyViolation]
    ) -> dict[ComplianceFramework, list[PolicyViolation]]:
        """Group violations by compliance framework."""
        mapping: dict[ComplianceFramework, list[PolicyViolation]] = {fw: [] for fw in ComplianceFramework}
        for v in violations:
            for fw in v.rule.compliance:
                mapping[fw].append(v)
        return {k: v for k, v in mapping.items() if v}

    def generate_compliance_report(self, result: GovernanceResult) -> str:
        """Generate a human-readable compliance report."""
        lines = ["# Compliance Report\n"]
        mapped = self.map_violations_to_frameworks(result.violations)

        for fw in ComplianceFramework:
            info = FRAMEWORK_INFO.get(fw, {})
            vcount = len(mapped.get(fw, []))
            status = "PASS" if vcount == 0 else "FAIL"
            lines.append(f"## {info.get('name', fw.value)} — {status}")
            lines.append(f"_{info.get('description', '')}_\n")

            if vcount == 0:
                lines.append("No violations detected.\n")
            else:
                for v in mapped[fw]:
                    lines.append(f"- **{v.rule.id}** [{v.rule.severity.value}] {v.rule.name}: {v.context[:100]}")
                lines.append("")

        return "\n".join(lines)
