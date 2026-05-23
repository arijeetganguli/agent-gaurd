"""OWASP Top 10 pattern-based scanner — no external tools required."""

from __future__ import annotations

import re
from pathlib import Path

from agentra.models import Severity, ScanResult

# OWASP pattern library — each entry: (rule_id, owasp_category, severity, pattern, finding_template)
OWASP_PATTERNS: list[tuple[str, str, Severity, str, str]] = [
    (
        "VULN-001",
        "A01 Broken Access Control",
        Severity.CRITICAL,
        r"(allow_all\s*=\s*True|bypass_auth|skip_auth|@no_auth|is_admin\s*=\s*True\s*#\s*TODO|permission_required\s*=\s*\[\])",
        "Access control bypass detected — never disable or skip permission checks",
    ),
    (
        "VULN-002",
        "A02 Cryptographic Failures",
        Severity.HIGH,
        r"(hashlib\.md5|hashlib\.sha1|Crypto\.Cipher\.DES|AES\.MODE_ECB|MD5\(|SHA1\(|DES\.new\(|RC4|Blowfish)",
        "Weak cryptographic algorithm detected — use AES-256-GCM or SHA-256+",
    ),
    (
        "VULN-003",
        "A03 Injection",
        Severity.CRITICAL,
        r'(f".*SELECT|f".*INSERT|f".*UPDATE|f".*DELETE|"SELECT.*"\s*%|"SELECT.*"\.format\(|execute\(\s*f"|os\.popen\(f")',
        "Injection vulnerability detected — use parameterized queries instead of string formatting",
    ),
    (
        "VULN-004",
        "A04 Insecure Design",
        Severity.MEDIUM,
        r"(file\.read\(\s*\)(?!\s*\[)|open\([^)]+\)\.read\(\s*\)(?!\s*\[))",
        "Unbounded file read detected — set explicit size limits to prevent DoS",
    ),
    (
        "VULN-005",
        "A05 Security Misconfiguration",
        Severity.HIGH,
        r"(DEBUG\s*=\s*True|debug\s*=\s*true|FLASK_DEBUG\s*=\s*1|password\s*[=:]\s*['\"]?(admin|password|123456|root|default)['\"]?|autoindex\s+on)",
        "Security misconfiguration detected — disable debug mode and change default credentials",
    ),
    (
        "VULN-006",
        "A06 Vulnerable and Outdated Components",
        Severity.MEDIUM,
        r"(pip install\s+[\w-]+\s*$|\"[\w-]+\":\s*\"\*\")",
        "Unpinned dependency detected — pin all versions to prevent supply-chain attacks",
    ),
    (
        "VULN-007",
        "A07 Identification and Authentication Failures",
        Severity.CRITICAL,
        r"(algorithm\s*=\s*['\"]none['\"]|algorithms\s*=\s*\[['\"]none['\"]|jwt\.decode\([^)]*verify\s*=\s*False|SECRET_KEY\s*=\s*['\"]['\"])",
        "Authentication failure risk — never disable JWT verification or use empty secret keys",
    ),
    (
        "VULN-008",
        "A08 Software and Data Integrity Failures",
        Severity.CRITICAL,
        r"(pickle\.loads?\s*\(|yaml\.load\s*\([^)]*\)(?!.*Loader\s*=)|marshal\.loads?\s*\(|jsonpickle\.decode\s*\()",
        "Unsafe deserialization detected — use yaml.safe_load() and avoid pickle on untrusted data",
    ),
    (
        "VULN-009",
        "A09 Security Logging and Monitoring Failures",
        Severity.MEDIUM,
        r"except\s*(?:Exception|BaseException|[\w\.]+)?\s*:\s*\n\s*pass",
        "Silent exception handler detected — log all errors; never swallow exceptions with bare pass",
    ),
    (
        "VULN-010",
        "A10 Server-Side Request Forgery",
        Severity.HIGH,
        r"(requests\.(get|post|put|delete|head)\s*\(\s*(?:request\.|params\[|args\[|data\[|body)|urllib\.request\.urlopen\s*\(\s*(?:request\.|params\[|args\[))",
        "SSRF vector detected — validate URLs against an allowlist before making outbound requests",
    ),
]

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb",
    ".php", ".cs", ".rs", ".swift", ".kt", ".scala", ".sh",
}

# Directories to skip
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".tox", ".eggs", "*.egg-info",
}


def scan_owasp(root: Path) -> list[ScanResult]:
    """Scan source files for OWASP Top 10 patterns. No external tools needed."""
    results: list[ScanResult] = []
    compiled = [(rid, cat, sev, re.compile(pat, re.IGNORECASE | re.MULTILINE), msg)
                for rid, cat, sev, pat, msg in OWASP_PATTERNS]

    for path in _iter_source_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = text.splitlines()
        for line_no, line in enumerate(lines, start=1):
            for rule_id, owasp_cat, severity, pattern, finding in compiled:
                if pattern.search(line):
                    results.append(ScanResult(
                        tool="owasp-patterns",
                        severity=severity,
                        file_path=str(path),
                        line=line_no,
                        finding=finding,
                        rule_id=rule_id,
                        owasp_category=owasp_cat,
                    ))

    return results


def _iter_source_files(root: Path):
    """Yield all source files, skipping ignored directories."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in path.parts):
            continue
        if path.suffix in SCANNABLE_EXTENSIONS:
            yield path
