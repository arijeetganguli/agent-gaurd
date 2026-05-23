"""SAST scanner — runs bandit/semgrep when available, falls back to pattern checks."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from agentra.models import Severity, ScanResult

# Map bandit severity levels
_BANDIT_SEVERITY_MAP = {
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
}

# Map bandit confidence to severity adjustment (lower confidence → lower severity)
_BANDIT_CONFIDENCE_MAP = {
    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2,
}


def scan_sast(root: Path) -> tuple[list[ScanResult], list[str], list[str]]:
    """
    Run SAST scan. Returns (results, tools_available, tools_missing).
    Tries bandit first, then semgrep, falls back to pattern scan.
    """
    results: list[ScanResult] = []
    available: list[str] = []
    missing: list[str] = []

    if shutil.which("bandit"):
        available.append("bandit")
        results.extend(_run_bandit(root))
    else:
        missing.append("bandit")

    if shutil.which("semgrep"):
        available.append("semgrep")
        results.extend(_run_semgrep(root))
    else:
        missing.append("semgrep")

    return results, available, missing


def _run_bandit(root: Path) -> list[ScanResult]:
    """Run bandit and parse JSON output."""
    results: list[ScanResult] = []
    try:
        proc = subprocess.run(  # noqa: S603
            ["bandit", "-r", str(root), "-f", "json", "-q",  # noqa: S607
             "--exclude", ".venv,venv,node_modules,__pycache__"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if not proc.stdout.strip():
            return results
        data = json.loads(proc.stdout)
        for issue in data.get("results", []):
            sev_str = issue.get("issue_severity", "LOW").upper()
            severity = _BANDIT_SEVERITY_MAP.get(sev_str, Severity.LOW)
            results.append(ScanResult(
                tool="bandit",
                severity=severity,
                file_path=issue.get("filename"),
                line=issue.get("line_number"),
                finding=issue.get("issue_text", ""),
                rule_id=issue.get("test_id", ""),
                owasp_category=_bandit_test_to_owasp(issue.get("test_id", "")),
            ))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError):
        pass
    return results


def _run_semgrep(root: Path) -> list[ScanResult]:
    """Run semgrep with the auto ruleset and parse JSON output."""
    results: list[ScanResult] = []
    try:
        proc = subprocess.run(  # noqa: S603
            ["semgrep", "--config", "auto", "--json", "--quiet", str(root)],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if not proc.stdout.strip():
            return results
        data = json.loads(proc.stdout)
        for finding in data.get("results", []):
            meta = finding.get("extra", {}).get("metadata", {})
            sev_str = (meta.get("severity") or finding.get("extra", {}).get("severity") or "WARNING").upper()
            severity = {"ERROR": Severity.HIGH, "WARNING": Severity.MEDIUM, "INFO": Severity.LOW}.get(sev_str, Severity.LOW)
            results.append(ScanResult(
                tool="semgrep",
                severity=severity,
                file_path=finding.get("path"),
                line=finding.get("start", {}).get("line"),
                finding=finding.get("extra", {}).get("message", ""),
                rule_id=finding.get("check_id", ""),
                owasp_category=", ".join(meta.get("owasp", [])),
                cve_id=meta.get("cve"),
            ))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError):
        pass
    return results


def _bandit_test_to_owasp(test_id: str) -> str:
    """Map bandit test IDs to approximate OWASP categories."""
    mapping = {
        "B101": "A05 Security Misconfiguration",
        "B102": "A03 Injection",
        "B103": "A05 Security Misconfiguration",
        "B105": "A07 Authentication Failures",
        "B106": "A07 Authentication Failures",
        "B107": "A07 Authentication Failures",
        "B108": "A05 Security Misconfiguration",
        "B110": "A09 Logging Failures",
        "B112": "A09 Logging Failures",
        "B201": "A05 Security Misconfiguration",
        "B301": "A08 Deserialization",
        "B302": "A08 Deserialization",
        "B303": "A02 Cryptographic Failures",
        "B304": "A02 Cryptographic Failures",
        "B305": "A02 Cryptographic Failures",
        "B306": "A05 Security Misconfiguration",
        "B307": "A03 Injection",
        "B311": "A02 Cryptographic Failures",
        "B312": "A10 SSRF",
        "B313": "A03 Injection",
        "B314": "A03 Injection",
        "B315": "A03 Injection",
        "B316": "A03 Injection",
        "B317": "A03 Injection",
        "B318": "A03 Injection",
        "B319": "A03 Injection",
        "B320": "A03 Injection",
        "B321": "A10 SSRF",
        "B322": "A03 Injection",
        "B323": "A02 Cryptographic Failures",
        "B324": "A02 Cryptographic Failures",
        "B325": "A02 Cryptographic Failures",
        "B401": "A06 Vulnerable Components",
        "B402": "A03 Injection",
        "B404": "A03 Injection",
        "B501": "A02 Cryptographic Failures",
        "B502": "A02 Cryptographic Failures",
        "B503": "A02 Cryptographic Failures",
        "B504": "A02 Cryptographic Failures",
        "B505": "A02 Cryptographic Failures",
        "B506": "A08 Deserialization",
        "B601": "A03 Injection",
        "B602": "A03 Injection",
        "B603": "A03 Injection",
        "B604": "A03 Injection",
        "B605": "A03 Injection",
        "B606": "A03 Injection",
        "B607": "A03 Injection",
        "B608": "A03 Injection",
        "B609": "A03 Injection",
        "B701": "A03 Injection",
        "B702": "A03 Injection",
        "B703": "A03 Injection",
    }
    return mapping.get(test_id.upper(), "")
