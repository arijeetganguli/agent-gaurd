"""Safe Execution Engine — sandboxed, approval-gated command execution."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

from agent_guard.models import (
    AuditEntry,
    ExecutionRequest,
    ExecutionResult,
    Severity,
)


# ── Dangerous patterns ──────────────────────────────────────────────────────

_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"rm\s+-rf\s+/", "Recursive delete from root"),
    (r"rm\s+-rf\s+\*", "Recursive delete wildcard"),
    (r"mkfs\.", "Filesystem format"),
    (r"dd\s+if=", "Raw disk write"),
    (r":(){ :\|:& };:", "Fork bomb"),
    (r">\s*/dev/sd", "Direct device write"),
    (r"curl\s+.*\|\s*(ba)?sh", "Curl pipe to shell"),
    (r"wget\s+.*\|\s*(ba)?sh", "Wget pipe to shell"),
    (r"eval\s*\(", "eval() usage"),
    (r"exec\s*\(", "exec() usage"),
    (r"base64\s+--decode\s*\|", "Decoded payload execution"),
    (r"git\s+push\s+.*--force\b", "Git force push"),
    (r"DROP\s+(TABLE|DATABASE)", "SQL DROP statement"),
    (r"TRUNCATE\s+TABLE", "SQL TRUNCATE statement"),
    (r"format\s+[a-zA-Z]:", "Windows disk format"),
    (r"del\s+/[sfq]", "Windows recursive delete"),
]


class ExecutionEngine:
    """Sandboxed execution engine with approval workflows."""

    def __init__(self, audit_log: list[AuditEntry] | None = None):
        self.audit_log = audit_log if audit_log is not None else []

    def classify_risk(self, command: str) -> tuple[Severity, list[str]]:
        """Classify a command's risk level and return matched patterns."""
        matches: list[str] = []
        for pattern, desc in _DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                matches.append(desc)

        if matches:
            return Severity.CRITICAL, matches
        if any(kw in command.lower() for kw in ["sudo", "chmod 777", "chown", "--no-verify"]):
            return Severity.HIGH, ["Elevated privilege or safety bypass"]
        if any(kw in command.lower() for kw in ["install", "pip install", "npm install", "apt-get"]):
            return Severity.MEDIUM, ["Package installation"]
        return Severity.LOW, []

    def dry_run(self, request: ExecutionRequest) -> ExecutionResult:
        """Simulate execution without actually running the command."""
        risk, reasons = self.classify_risk(request.command)
        self._audit("dry_run", request.command, risk, reasons)

        if risk == Severity.CRITICAL:
            return ExecutionResult(
                approved=False,
                executed=False,
                stderr=f"BLOCKED: {'; '.join(reasons)}",
            )

        return ExecutionResult(
            approved=risk.value not in ("critical", "high"),
            executed=False,
            stdout=f"[DRY RUN] Command: {request.command}\nRisk: {risk.value}\nReasons: {'; '.join(reasons) or 'None'}",
        )

    def execute(self, request: ExecutionRequest, force_approve: bool = False) -> ExecutionResult:
        """Execute a command with safety checks."""
        risk, reasons = self.classify_risk(request.command)

        # Block critical commands
        if risk == Severity.CRITICAL and not force_approve:
            self._audit("blocked", request.command, risk, reasons)
            return ExecutionResult(
                approved=False,
                executed=False,
                stderr=f"BLOCKED: {'; '.join(reasons)}. Use --force to override.",
            )

        # Require approval for high-risk
        if risk == Severity.HIGH and request.requires_approval and not force_approve:
            self._audit("approval_required", request.command, risk, reasons)
            return ExecutionResult(
                approved=False,
                executed=False,
                stderr=f"APPROVAL REQUIRED: {'; '.join(reasons)}",
            )

        # Execute in sandbox if requested
        if request.sandbox:
            return self._sandbox_execute(request, risk, reasons)

        return self._direct_execute(request, risk, reasons)

    def _sandbox_execute(self, request: ExecutionRequest, risk: Severity, reasons: list[str]) -> ExecutionResult:
        """Execute in a temporary sandbox directory."""
        sandbox_dir = tempfile.mkdtemp(prefix="ag_sandbox_")
        self._audit("sandbox_execute", request.command, risk, reasons)

        try:
            result = subprocess.run(
                request.command,
                shell=True,
                cwd=sandbox_dir,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                env={**os.environ, "AG_SANDBOX": "1"},
            )
            return ExecutionResult(
                approved=True,
                executed=True,
                exit_code=result.returncode,
                stdout=result.stdout[:10000],
                stderr=result.stderr[:10000],
                sandbox_path=sandbox_dir,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                approved=True,
                executed=True,
                exit_code=-1,
                stderr=f"Command timed out after {request.timeout_seconds}s",
                sandbox_path=sandbox_dir,
            )
        except Exception as e:
            return ExecutionResult(
                approved=True,
                executed=False,
                stderr=str(e),
                sandbox_path=sandbox_dir,
            )

    def _direct_execute(self, request: ExecutionRequest, risk: Severity, reasons: list[str]) -> ExecutionResult:
        """Direct execution (non-sandboxed)."""
        self._audit("direct_execute", request.command, risk, reasons)

        try:
            result = subprocess.run(
                request.command,
                shell=True,
                cwd=request.working_dir,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
            )
            return ExecutionResult(
                approved=True,
                executed=True,
                exit_code=result.returncode,
                stdout=result.stdout[:10000],
                stderr=result.stderr[:10000],
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                approved=True,
                executed=True,
                exit_code=-1,
                stderr=f"Command timed out after {request.timeout_seconds}s",
            )
        except Exception as e:
            return ExecutionResult(
                approved=True,
                executed=False,
                stderr=str(e),
            )

    def _audit(self, action: str, command: str, risk: Severity, reasons: list[str]) -> None:
        self.audit_log.append(AuditEntry(
            action=action,
            details={"command": command, "risk": risk.value, "reasons": reasons},
            risk_level=risk,
        ))
