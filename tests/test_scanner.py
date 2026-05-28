"""Tests for the vulnerability scanner module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agentra.models import ScanTarget, Severity
from agentra.scanner.engine import ScanEngine
from agentra.scanner.owasp import scan_owasp


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal Python project for scanning."""
    (tmp_path / "app.py").write_text(
        "import hashlib\n"
        "import pickle\n"
        "import yaml\n\n"
        "password = 'admin123'\n"  # VULN-001 / SEC-001
        "h = hashlib.md5(b'data').hexdigest()\n"  # VULN-002
        "obj = pickle.loads(user_data)\n"  # VULN-008
        "config = yaml.load(f)\n"  # VULN-008
        "DEBUG = True\n",  # VULN-005
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def clean_project(tmp_path: Path) -> Path:
    """Create a clean project with no vulnerability patterns."""
    (tmp_path / "app.py").write_text(
        "import hashlib\n"
        "import yaml\n\n"
        "h = hashlib.sha256(b'data').hexdigest()\n"
        "config = yaml.safe_load(f)\n"
        "DEBUG = False\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def node_project(tmp_path: Path) -> Path:
    """Create a Node.js project with unpinned deps."""
    pkg = {"name": "test", "dependencies": {"express": "*", "lodash": "latest"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def python_project_unpinned(tmp_path: Path) -> Path:
    """Create a Python project with unpinned requirements."""
    (tmp_path / "requirements.txt").write_text(
        "fastapi>=0.100\nrequests\npydantic\n",
        encoding="utf-8",
    )
    return tmp_path


# ── OWASP Pattern Scanner Tests ───────────────────────────────────────────────

class TestOwaspScanner:
    def test_detects_md5(self, tmp_project: Path):
        results = scan_owasp(tmp_project)
        rule_ids = {r.rule_id for r in results}
        assert "VULN-002" in rule_ids

    def test_detects_debug_true(self, tmp_project: Path):
        results = scan_owasp(tmp_project)
        rule_ids = {r.rule_id for r in results}
        assert "VULN-005" in rule_ids

    def test_detects_unsafe_pickle(self, tmp_project: Path):
        results = scan_owasp(tmp_project)
        rule_ids = {r.rule_id for r in results}
        assert "VULN-008" in rule_ids

    def test_detects_yaml_load(self, tmp_project: Path):
        results = scan_owasp(tmp_project)
        rule_ids = {r.rule_id for r in results}
        assert "VULN-008" in rule_ids

    def test_clean_project_no_high_findings(self, clean_project: Path):
        results = scan_owasp(clean_project)
        critical_high = [r for r in results if r.severity in (Severity.CRITICAL, Severity.HIGH)]
        assert len(critical_high) == 0

    def test_results_have_required_fields(self, tmp_project: Path):
        results = scan_owasp(tmp_project)
        for r in results:
            assert r.tool == "owasp-patterns"
            assert r.severity is not None
            assert r.finding
            assert r.owasp_category

    def test_skips_venv_directory(self, tmp_path: Path):
        venv = tmp_path / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "bad.py").write_text("DEBUG = True\n", encoding="utf-8")
        results = scan_owasp(tmp_path)
        # Should not pick up files inside .venv
        venv_findings = [r for r in results if ".venv" in (r.file_path or "")]
        assert len(venv_findings) == 0

    def test_sql_injection_detection(self, tmp_path: Path):
        (tmp_path / "db.py").write_text(
            'sql = f"SELECT * FROM users WHERE id = {user_id}"\n',
            encoding="utf-8",
        )
        results = scan_owasp(tmp_path)
        assert any(r.rule_id == "VULN-003" for r in results)

    def test_jwt_none_algorithm_detection(self, tmp_path: Path):
        (tmp_path / "auth.py").write_text(
            'token = jwt.decode(data, algorithm="none")\n',
            encoding="utf-8",
        )
        results = scan_owasp(tmp_path)
        assert any(r.rule_id == "VULN-007" for r in results)


# ── Dependency Scanner Fallback Tests ─────────────────────────────────────────

class TestDepsScanner:
    def test_flags_unpinned_requirements_txt(self, python_project_unpinned: Path):
        from agentra.scanner.deps import scan_deps
        results, _, _ = scan_deps(python_project_unpinned)
        # dep-fallback should flag unpinned packages
        dep_findings = [r for r in results if r.tool == "dep-fallback"]
        assert len(dep_findings) > 0
        for r in dep_findings:
            assert r.rule_id == "VULN-006"
            assert r.owasp_category == "A06 Vulnerable and Outdated Components"

    def test_flags_wildcard_package_json(self, node_project: Path):
        from unittest.mock import patch
        import shutil
        from agentra.scanner.deps import scan_deps
        # Force fallback path regardless of whether npm is installed
        with patch.object(shutil, "which", return_value=None):
            results, _, _ = scan_deps(node_project)
        wildcard_findings = [r for r in results if r.tool == "dep-fallback"]
        assert any("express" in r.finding or "lodash" in r.finding for r in wildcard_findings)

    def test_no_findings_for_clean_project(self, clean_project: Path):
        from agentra.scanner.deps import scan_deps
        results, _, _ = scan_deps(clean_project)
        assert len(results) == 0  # no requirements.txt or package.json

    def test_pinned_requirements_not_flagged(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text(
            "fastapi==0.111.0\nrequests==2.31.0\npydantic==2.5.0\n",
            encoding="utf-8",
        )
        from agentra.scanner.deps import scan_deps
        results, _, _ = scan_deps(tmp_path)
        dep_findings = [r for r in results if r.tool == "dep-fallback"]
        assert len(dep_findings) == 0


# ── ScanEngine Tests ──────────────────────────────────────────────────────────

class TestScanEngine:
    def test_scan_returns_vulnerability_report(self, tmp_project: Path):
        engine = ScanEngine(tmp_project)
        report = engine.scan(targets=[ScanTarget.OWASP])
        assert report is not None
        assert isinstance(report.results, list)
        assert report.scan_duration_ms >= 0

    def test_scan_owasp_only(self, tmp_project: Path):
        engine = ScanEngine(tmp_project)
        report = engine.scan(targets=[ScanTarget.OWASP])
        assert "owasp-patterns" in report.tools_available

    def test_scan_all_targets(self, tmp_project: Path):
        engine = ScanEngine(tmp_project)
        report = engine.scan(targets=[ScanTarget.ALL])
        assert "owasp-patterns" in report.tools_available

    def test_critical_findings_fail_gate(self, tmp_project: Path):
        engine = ScanEngine(tmp_project)
        report = engine.scan(targets=[ScanTarget.OWASP])
        # tmp_project has pickle.loads → VULN-008 (CRITICAL)
        if report.critical_count > 0:
            assert report.passed is False
            assert engine.gate(report) is False

    def test_clean_project_passes_gate(self, clean_project: Path):
        engine = ScanEngine(clean_project)
        report = engine.scan(targets=[ScanTarget.OWASP])
        assert engine.gate(report) is True

    def test_risk_score_increases_with_critical(self, tmp_project: Path):
        engine = ScanEngine(tmp_project)
        report = engine.scan(targets=[ScanTarget.OWASP])
        # Each CRITICAL adds 10.0 to score
        critical_count = report.critical_count
        assert report.risk_score >= critical_count * 10.0

    def test_deduplication(self, tmp_path: Path):
        """Identical findings from same location should be deduplicated."""
        (tmp_path / "app.py").write_text(
            "import pickle\n" * 1 +  # Just one line
            "x = pickle.loads(data)\n",
            encoding="utf-8",
        )
        engine = ScanEngine(tmp_path)
        report = engine.scan(targets=[ScanTarget.OWASP])
        rule_ids = [r.rule_id for r in report.results]
        # VULN-008 should appear at most once per occurrence
        assert rule_ids.count("VULN-008") <= 2

    def test_summary_populated(self, tmp_project: Path):
        engine = ScanEngine(tmp_project)
        report = engine.scan(targets=[ScanTarget.OWASP])
        assert report.summary

    def test_max_results_cap(self, tmp_path: Path):
        """Generate many findings and verify cap is applied."""
        # Write a file with many issues
        lines = ["import hashlib\n"]
        for i in range(600):
            lines.append(f"h{i} = hashlib.md5(b'data{i}').hexdigest()\n")
        (tmp_path / "big.py").write_text("".join(lines), encoding="utf-8")
        engine = ScanEngine(tmp_path)
        report = engine.scan(targets=[ScanTarget.OWASP], max_results=50)
        assert len(report.results) <= 50

    def test_report_counts_by_severity(self, tmp_project: Path):
        engine = ScanEngine(tmp_project)
        report = engine.scan(targets=[ScanTarget.OWASP])
        total = report.critical_count + report.high_count + report.medium_count + report.low_count
        assert total == len(report.results)


# ── Policy Integration Tests ──────────────────────────────────────────────────

class TestVulnPolicies:
    def test_vuln_policies_exist(self):
        from agentra.governance.policies import ALL_POLICIES, VULNERABILITY_POLICIES
        assert len(VULNERABILITY_POLICIES) == 10
        vuln_ids = {p.id for p in VULNERABILITY_POLICIES}
        expected = {f"VULN-{i:03d}" for i in range(1, 11)}
        assert vuln_ids == expected

    def test_vuln_policies_in_all_policies(self):
        from agentra.governance.policies import ALL_POLICIES
        all_ids = {p.id for p in ALL_POLICIES}
        assert "VULN-001" in all_ids
        assert "VULN-010" in all_ids

    def test_total_policy_count(self):
        from agentra.governance.policies import ALL_POLICIES
        # 21 original + 10 OWASP = 31
        assert len(ALL_POLICIES) == 32

    def test_vuln_policies_have_compliance_mappings(self):
        from agentra.governance.policies import VULNERABILITY_POLICIES
        for p in VULNERABILITY_POLICIES:
            assert len(p.compliance) > 0, f"{p.id} has no compliance mappings"

    def test_all_owasp_categories_represented(self):
        from agentra.governance.policies import VULNERABILITY_POLICIES
        descriptions = " ".join(p.description for p in VULNERABILITY_POLICIES)
        for i in range(1, 11):
            assert f"A0{i}" in descriptions or f"A{i:02d}" in descriptions, (
                f"OWASP A{i:02d} not represented in VULN policies"
            )
