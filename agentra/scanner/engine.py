"""ScanEngine — orchestrates SAST, dependency, and OWASP vulnerability scanning."""

from __future__ import annotations

import time
from pathlib import Path

from agentra.models import Severity, ScanTarget, VulnerabilityReport


class ScanEngine:
    """
    Multi-layer vulnerability scanner.

    Targets:
      - SAST: bandit + semgrep (subprocess), pattern fallback when unavailable
      - DEPS: pip-audit, npm audit, cargo audit, unpinned-dep fallback
      - OWASP: OWASP Top 10 pattern checks (always runs, no external tools)
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.cwd()

    def scan(
        self,
        targets: list[ScanTarget] | None = None,
        max_results: int = 500,
    ) -> VulnerabilityReport:
        """
        Run selected scan targets and return a VulnerabilityReport.

        Args:
            targets: Which scan types to run. Defaults to ALL.
            max_results: Cap total findings to prevent overwhelming output.
        """
        if targets is None:
            targets = [ScanTarget.ALL]

        run_sast = ScanTarget.ALL in targets or ScanTarget.SAST in targets
        run_deps = ScanTarget.ALL in targets or ScanTarget.DEPS in targets
        run_owasp = ScanTarget.ALL in targets or ScanTarget.OWASP in targets

        from agentra.models import ScanResult

        all_results: list[ScanResult] = []
        all_available: list[str] = []
        all_missing: list[str] = []

        start = time.monotonic()

        if run_owasp:
            from agentra.scanner.owasp import scan_owasp
            owasp_results = scan_owasp(self.root)
            all_results.extend(owasp_results)
            all_available.append("owasp-patterns")

        if run_sast:
            from agentra.scanner.sast import scan_sast
            sast_results, avail, miss = scan_sast(self.root)
            all_results.extend(sast_results)
            all_available.extend(avail)
            all_missing.extend(miss)

        if run_deps:
            from agentra.scanner.deps import scan_deps
            dep_results, avail, miss = scan_deps(self.root)
            all_results.extend(dep_results)
            all_available.extend(avail)
            all_missing.extend(miss)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Deduplicate by (file, line, rule_id)
        seen: set[tuple] = set()
        deduped: list[ScanResult] = []
        for r in all_results:
            key = (r.file_path, r.line, r.rule_id, r.finding[:80])
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        # Cap results
        deduped = deduped[:max_results]

        risk_score = self._compute_risk_score(deduped)
        passed = not any(r.severity == Severity.CRITICAL for r in deduped)

        summary_parts = []
        critical = sum(1 for r in deduped if r.severity == Severity.CRITICAL)
        high = sum(1 for r in deduped if r.severity == Severity.HIGH)
        medium = sum(1 for r in deduped if r.severity == Severity.MEDIUM)
        low = sum(1 for r in deduped if r.severity == Severity.LOW)
        if deduped:
            summary_parts.append(
                f"{len(deduped)} findings: {critical} critical, {high} high, "
                f"{medium} medium, {low} low"
            )
        else:
            summary_parts.append("No vulnerabilities detected")

        if all_missing:
            summary_parts.append(
                f"Install {', '.join(all_missing)} for deeper scanning "
                f"(pip install {' '.join(all_missing)})"
            )

        return VulnerabilityReport(
            scan_targets=targets,
            results=deduped,
            risk_score=risk_score,
            passed=passed,
            scan_duration_ms=elapsed_ms,
            tools_available=all_available,
            tools_missing=all_missing,
            summary=". ".join(summary_parts),
        )

    def _compute_risk_score(self, results) -> float:
        weights = {
            Severity.CRITICAL: 10.0,
            Severity.HIGH: 6.0,
            Severity.MEDIUM: 3.0,
            Severity.LOW: 1.0,
            Severity.INFO: 0.0,
        }
        return sum(weights.get(r.severity, 0) for r in results)

    def gate(self, report: VulnerabilityReport, block_on: list[Severity] | None = None) -> bool:
        """
        Return True if the gate passes (build/run can proceed).
        By default blocks on CRITICAL findings.
        """
        if block_on is None:
            block_on = [Severity.CRITICAL]
        return not any(r.severity in block_on for r in report.results)
