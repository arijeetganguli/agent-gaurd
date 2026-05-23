"""Dependency vulnerability scanner — pip-audit, npm audit, cargo audit with graceful fallback."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from agentra.models import Severity, ScanResult


def scan_deps(root: Path) -> tuple[list[ScanResult], list[str], list[str]]:
    """
    Scan dependencies for known vulnerabilities.
    Returns (results, tools_available, tools_missing).
    Runs available audit tools; falls back to version-constraint checks.
    """
    results: list[ScanResult] = []
    available: list[str] = []
    missing: list[str] = []

    # Python — pip-audit
    has_python_deps = (root / "requirements.txt").exists() or (root / "pyproject.toml").exists()
    if has_python_deps:
        if shutil.which("pip-audit"):
            available.append("pip-audit")
            results.extend(_run_pip_audit(root))
        else:
            missing.append("pip-audit")
            results.extend(_scan_requirements_txt(root))

    # JavaScript / Node — npm audit
    has_node_deps = (root / "package.json").exists()
    if has_node_deps:
        if shutil.which("npm"):
            available.append("npm-audit")
            results.extend(_run_npm_audit(root))
        else:
            missing.append("npm-audit")
            results.extend(_scan_package_json(root))

    # Rust — cargo audit
    has_cargo = (root / "Cargo.toml").exists()
    if has_cargo:
        if shutil.which("cargo-audit") or shutil.which("cargo"):
            available.append("cargo-audit")
            results.extend(_run_cargo_audit(root))
        else:
            missing.append("cargo-audit")

    return results, available, missing


# ── pip-audit ─────────────────────────────────────────────────────────────────

def _run_pip_audit(root: Path) -> list[ScanResult]:
    results: list[ScanResult] = []
    try:
        cmd = ["pip-audit", "--format", "json", "--progress-spinner", "off"]
        req = root / "requirements.txt"
        if req.exists():
            cmd += ["-r", str(req)]
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            cwd=root,
        )
        raw = proc.stdout.strip() or proc.stderr.strip()
        if not raw:
            return results
        data = json.loads(raw)
        for dep in data.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                fix_versions = vuln.get("fix_versions", [])
                results.append(ScanResult(
                    tool="pip-audit",
                    severity=_cvss_to_severity(vuln.get("fix_versions", [])),
                    file_path="requirements.txt",
                    finding=f"{dep.get('name')} {dep.get('version')}: {vuln.get('description', vuln.get('id', ''))}",
                    rule_id=vuln.get("id", ""),
                    cve_id=vuln.get("aliases", [None])[0],
                    fix_available=bool(fix_versions),
                    fix_description=f"Upgrade to {', '.join(fix_versions)}" if fix_versions else "",
                    owasp_category="A06 Vulnerable and Outdated Components",
                ))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError, KeyError):
        pass
    return results


def _scan_requirements_txt(root: Path) -> list[ScanResult]:
    """Fallback: flag requirements without pinned versions."""
    results: list[ScanResult] = []
    req = root / "requirements.txt"
    if not req.exists():
        return results
    unpinned_pattern = re.compile(r"^([\w\-\[\]]+)\s*(?:>=|>|<=|<|!=|~=|$)")
    pinned_pattern = re.compile(r"^[\w\-\[\]]+\s*==\s*\S+")
    for line_no, line in enumerate(req.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if unpinned_pattern.match(line) and not pinned_pattern.match(line):
            results.append(ScanResult(
                tool="dep-fallback",
                severity=Severity.MEDIUM,
                file_path="requirements.txt",
                line=line_no,
                finding=f"Unpinned dependency '{line.split()[0]}' — cannot guarantee vulnerability-free version",
                rule_id="VULN-006",
                owasp_category="A06 Vulnerable and Outdated Components",
            ))
    return results


# ── npm audit ─────────────────────────────────────────────────────────────────

def _run_npm_audit(root: Path) -> list[ScanResult]:
    results: list[ScanResult] = []
    try:
        proc = subprocess.run(  # noqa: S603
            ["npm", "audit", "--json"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            cwd=root,
        )
        if not proc.stdout.strip():
            return results
        data = json.loads(proc.stdout)
        # npm audit v2 format
        for name, vuln in data.get("vulnerabilities", {}).items():
            sev_str = vuln.get("severity", "moderate").upper()
            severity = {"CRITICAL": Severity.CRITICAL, "HIGH": Severity.HIGH,
                        "MODERATE": Severity.MEDIUM, "LOW": Severity.LOW}.get(sev_str, Severity.MEDIUM)
            via = vuln.get("via", [])
            description = next((v.get("title", "") for v in via if isinstance(v, dict)), f"Vulnerability in {name}")
            cve = next((v.get("cve", [None])[0] if v.get("cve") else None for v in via if isinstance(v, dict)), None)
            results.append(ScanResult(
                tool="npm-audit",
                severity=severity,
                file_path="package.json",
                finding=f"{name}: {description}",
                rule_id=str(vuln.get("cwe", [""])[0]) if vuln.get("cwe") else "",
                cve_id=cve,
                fix_available=vuln.get("fixAvailable", False) is not False,
                owasp_category="A06 Vulnerable and Outdated Components",
            ))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError):
        pass
    return results


def _scan_package_json(root: Path) -> list[ScanResult]:
    """Fallback: flag wildcard or latest versions in package.json."""
    results: list[ScanResult] = []
    pkg = root / "package.json"
    if not pkg.exists():
        return results
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        for section in ("dependencies", "devDependencies"):
            for name, version in data.get(section, {}).items():
                if version in ("*", "latest", ""):
                    results.append(ScanResult(
                        tool="dep-fallback",
                        severity=Severity.MEDIUM,
                        file_path="package.json",
                        finding=f"Unpinned dependency '{name}': '{version}' — pin to a specific version",
                        rule_id="VULN-006",
                        owasp_category="A06 Vulnerable and Outdated Components",
                    ))
    except (json.JSONDecodeError, OSError):
        pass
    return results


# ── cargo audit ──────────────────────────────────────────────────────────────

def _run_cargo_audit(root: Path) -> list[ScanResult]:
    results: list[ScanResult] = []
    try:
        proc = subprocess.run(  # noqa: S603
            ["cargo", "audit", "--json"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            cwd=root,
        )
        if not proc.stdout.strip():
            return results
        data = json.loads(proc.stdout)
        for vuln in data.get("vulnerabilities", {}).get("list", []):
            adv = vuln.get("advisory", {})
            results.append(ScanResult(
                tool="cargo-audit",
                severity=Severity.HIGH,
                file_path="Cargo.toml",
                finding=f"{adv.get('package')}: {adv.get('title', adv.get('id', ''))}",
                rule_id=adv.get("id", ""),
                cve_id=adv.get("aliases", [None])[0],
                fix_available=bool(vuln.get("versions", {}).get("patched")),
                fix_description=f"Patched in {vuln.get('versions', {}).get('patched', [])}",
                owasp_category="A06 Vulnerable and Outdated Components",
            ))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError):
        pass
    return results


def _cvss_to_severity(fix_versions: list) -> Severity:
    """Simple heuristic: if no fix available → higher urgency."""
    return Severity.HIGH if not fix_versions else Severity.MEDIUM
