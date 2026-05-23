"""Git hook management — install pre-commit and pre-push hooks that run ag scan."""

from __future__ import annotations

import os
import stat
from pathlib import Path

_PRE_COMMIT_SCRIPT = """\
#!/usr/bin/env bash
# Agentra pre-commit hook — security scan before commit
# Installed by: ag hooks install
set -euo pipefail

if command -v ag >/dev/null 2>&1; then
    echo "[agentra] Running pre-commit security scan..."
    ag scan --owasp 2>&1
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "[agentra] ✗ Security scan found CRITICAL vulnerabilities. Fix them before committing."
        echo "[agentra] Override with: git commit --no-verify"
        exit 1
    fi
    echo "[agentra] ✓ Security scan passed."
else
    echo "[agentra] Warning: 'ag' not found in PATH. Install agentra to enable security scanning."
fi
"""

_PRE_PUSH_SCRIPT = """\
#!/usr/bin/env bash
# Agentra pre-push hook — full vulnerability scan before push
# Installed by: ag hooks install
set -euo pipefail

if command -v ag >/dev/null 2>&1; then
    echo "[agentra] Running pre-push vulnerability scan (SAST + deps + OWASP)..."
    ag scan 2>&1
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "[agentra] ✗ Vulnerability scan found CRITICAL issues. Fix them before pushing."
        echo "[agentra] Override with: git push --no-verify"
        exit 1
    fi
    echo "[agentra] ✓ Vulnerability scan passed."
else
    echo "[agentra] Warning: 'ag' not found in PATH. Install agentra to enable security scanning."
fi
"""

_MANAGED_HOOKS = {
    "pre-commit": _PRE_COMMIT_SCRIPT,
    "pre-push": _PRE_PUSH_SCRIPT,
}

_AGENTRA_MARKER = "# Installed by: ag hooks install"


def _find_git_hooks_dir(root: Path) -> Path | None:
    """Walk up from root to find .git/hooks directory."""
    current = root.resolve()
    for _ in range(8):  # walk up at most 8 levels
        git_hooks = current / ".git" / "hooks"
        if git_hooks.is_dir():
            return git_hooks
        if current.parent == current:
            break
        current = current.parent
    return None


def install_git_hooks(root: Path) -> dict[str, str]:
    """
    Install Agentra pre-commit and pre-push hooks.
    Returns {hook_name: status} where status is "installed", "skipped", or "error".
    """
    hooks_dir = _find_git_hooks_dir(root)
    if hooks_dir is None:
        return {"error": "No .git directory found. Run 'git init' first."}

    statuses: dict[str, str] = {}
    for hook_name, script in _MANAGED_HOOKS.items():
        hook_path = hooks_dir / hook_name
        try:
            if hook_path.exists():
                existing = hook_path.read_text(encoding="utf-8")
                if _AGENTRA_MARKER in existing:
                    # Overwrite — already ours
                    hook_path.write_text(script, encoding="utf-8")
                    statuses[hook_name] = "updated"
                else:
                    # Append our hook to existing
                    combined = existing.rstrip() + "\n\n" + script
                    hook_path.write_text(combined, encoding="utf-8")
                    statuses[hook_name] = "appended"
            else:
                hook_path.write_text(script, encoding="utf-8")
                statuses[hook_name] = "installed"
            # Make executable
            hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        except OSError as e:
            statuses[hook_name] = f"error: {e}"

    return statuses


def uninstall_git_hooks(root: Path) -> dict[str, str]:
    """
    Remove Agentra-managed hooks. Leaves non-Agentra content intact.
    Returns {hook_name: status}.
    """
    hooks_dir = _find_git_hooks_dir(root)
    if hooks_dir is None:
        return {"error": "No .git directory found."}

    statuses: dict[str, str] = {}
    for hook_name in _MANAGED_HOOKS:
        hook_path = hooks_dir / hook_name
        if not hook_path.exists():
            statuses[hook_name] = "not_found"
            continue
        try:
            content = hook_path.read_text(encoding="utf-8")
            if _AGENTRA_MARKER not in content:
                statuses[hook_name] = "not_managed"
                continue
            # Strip Agentra section(s)
            lines = content.splitlines(keepends=True)
            cleaned: list[str] = []
            skip = False
            for line in lines:
                if _AGENTRA_MARKER in line:
                    skip = True
                    # Remove trailing blank lines already added
                    while cleaned and cleaned[-1].strip() == "":
                        cleaned.pop()
                    continue
                if skip:
                    # Skip until end of shebang block — stop skipping at blank line after content
                    if line.strip() == "" and cleaned:
                        skip = False
                    continue
                cleaned.append(line)

            remaining = "".join(cleaned).strip()
            if remaining and remaining != "#!/usr/bin/env bash":
                hook_path.write_text(remaining + "\n", encoding="utf-8")
                statuses[hook_name] = "removed_agentra_section"
            else:
                hook_path.unlink()
                statuses[hook_name] = "removed"
        except OSError as e:
            statuses[hook_name] = f"error: {e}"

    return statuses


def hooks_status(root: Path) -> dict[str, dict]:
    """
    Return status of Agentra hooks.
    Returns {hook_name: {exists, managed, path}}.
    """
    hooks_dir = _find_git_hooks_dir(root)
    if hooks_dir is None:
        return {"error": {"exists": False, "managed": False, "path": ""}}

    status: dict[str, dict] = {}
    for hook_name in _MANAGED_HOOKS:
        hook_path = hooks_dir / hook_name
        exists = hook_path.exists()
        managed = False
        if exists:
            try:
                managed = _AGENTRA_MARKER in hook_path.read_text(encoding="utf-8")
            except OSError:
                pass
        executable = exists and os.access(hook_path, os.X_OK)
        status[hook_name] = {
            "exists": exists,
            "managed": managed,
            "executable": executable,
            "path": str(hook_path),
        }
    return status
