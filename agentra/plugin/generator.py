"""
PluginGenerator — creates a Claude Code plugin package for Agentra.

Follows the anthropics/claude-plugins-official plugin spec:
  plugin-name/
  ├── .claude-plugin/plugin.json
  ├── hooks/pre-tool-use.sh
  ├── skills/<name>/SKILL.md
  └── README.md
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

from agentra.models import ProjectConfig

# ── plugin.json ──────────────────────────────────────────────────────────────

_PLUGIN_JSON = {
    "name": "agentra",
    "description": (
        "Enterprise AI engineering control plane — security scanning, "
        "OWASP vulnerability detection, governance policy enforcement, "
        "pre-build safety gates, and Karpathy coding guidelines for every session."
    ),
    "author": {
        "name": "Agentra",
        "url": "https://github.com/stavionlabs/agentra",
    },
}

# ── PreToolUse hook ───────────────────────────────────────────────────────────

_PRE_TOOL_USE_HOOK = """\
#!/usr/bin/env bash
# Agentra PreToolUse security hook
# Intercepts Bash tool calls matching build/run patterns and gates on vulnerability scan.
# Part of the Agentra Claude Code plugin.
set -euo pipefail

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

# Only intercept Bash tool calls
if [ "$TOOL_NAME" != "Bash" ]; then
    exit 0
fi

# Patterns that indicate a build or run command
BUILD_PATTERNS="docker build|docker-compose up|docker compose up|npm run build|npm run start|yarn build|yarn start|pip install|python -m build|python setup.py|cargo build|cargo run|mvn package|gradle build|make build|make all|pytest|go build|go run"

# Check if the command matches a build/run pattern
MATCHED=false
IFS='|' read -ra PATTERNS <<< "$BUILD_PATTERNS"
for pattern in "${PATTERNS[@]}"; do
    if echo "$TOOL_INPUT" | grep -qi "$pattern"; then
        MATCHED=true
        break
    fi
done

if [ "$MATCHED" = "false" ]; then
    exit 0
fi

# Run Agentra scan if available
if command -v ag >/dev/null 2>&1; then
    echo "[agentra] Pre-build security scan triggered by: $TOOL_INPUT"
    echo "[agentra] Running OWASP + dependency vulnerability scan..."

    SCAN_OUTPUT=$(ag scan --owasp 2>&1) || SCAN_EXIT=$?
    SCAN_EXIT=${SCAN_EXIT:-0}

    echo "$SCAN_OUTPUT"

    if [ "$SCAN_EXIT" -ne 0 ]; then
        echo ""
        echo "[agentra] ✗ CRITICAL vulnerabilities detected. Build blocked."
        echo "[agentra] Fix the findings above before building."
        echo "[agentra] To skip: set AGENTRA_SKIP_SCAN=1"
        exit 1
    fi

    echo "[agentra] ✓ Security scan passed. Proceeding with build."
else
    echo "[agentra] Warning: 'ag' not found. Install agentra for pre-build security scanning."
fi
"""

# ── SKILL.md templates ────────────────────────────────────────────────────────

_SKILL_GUARDIAN = """\
---
name: agentra-guardian
description: >
  Activate when the user is writing code, editing files, running commands, or asking
  about security, vulnerabilities, dependencies, or build processes. Provides
  proactive security guidance and Karpathy engineering principles.
version: 1.0.0
allowed-tools: [Read, Glob, Grep, Bash]
---

# Agentra Guardian

You have Agentra active. Apply these principles to all code you write in this session.

## Karpathy Coding Guidelines (Universal)

### 1. Think Before Coding
- State your assumptions explicitly. If uncertain, ask — don't guess silently.
- If multiple interpretations exist, present them instead of picking one without telling the user.
- If a simpler approach exists, say so and push back when warranted.
- Stop and ask when something is genuinely unclear.

### 2. Simplicity First
- Write the minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked. No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes
- Touch only what you must. Never "improve" adjacent code that wasn't in scope.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Every changed line must trace directly to the user's request.
- Remove imports/variables/functions YOUR changes made unused — but not pre-existing dead code.

### 4. Goal-Driven Execution
- Transform tasks into verifiable goals with explicit success criteria.
- For multi-step tasks, state a brief plan with verify steps before starting.
- "Fix the bug" → "Write a test that reproduces it, then make it pass."

## Security Baseline (Always Active)

- Never hardcode secrets — use environment variables or secret managers
- Use parameterized queries — never build SQL with f-strings or .format()
- Validate and sanitize all user input before processing
- Use strong cryptography — AES-256-GCM, SHA-256+, Argon2/bcrypt for passwords
- Never bypass auth checks — deny by default, verify every request
- Never deserialize untrusted data with pickle or yaml.load() without Loader
- Pin all dependencies — always use exact version constraints

## Pre-Build Gate

Before running any build command, ask yourself:
1. Have secrets been removed from code?
2. Are all dependencies pinned to specific versions?
3. Is debug mode disabled?
4. Are there any hardcoded credentials?

If in doubt, run `ag scan` to check.
"""

_SKILL_SCAN = """\
---
name: agentra-scan
description: >
  Run when the user asks to scan for vulnerabilities, check security, audit dependencies,
  or perform a security review. Runs the Agentra vulnerability scanner.
version: 1.0.0
argument-hint: [--sast] [--deps] [--owasp] [--format table|json]
allowed-tools: [Bash]
---

# Agentra Vulnerability Scanner

Run `ag scan` to perform a multi-layer security scan:

```bash
# Full scan (OWASP patterns + SAST + dependency audit)
ag scan

# OWASP Top 10 patterns only (no external tools)
ag scan --owasp

# Dependency vulnerabilities only
ag scan --deps

# SAST analysis only (requires bandit or semgrep)
ag scan --sast

# JSON output for CI integration
ag scan --format json
```

## What Gets Scanned

| Layer | Tool | Fallback |
|-------|------|---------|
| OWASP Top 10 | Built-in patterns | Always runs |
| SAST | bandit, semgrep | Pattern-based checks |
| Dependencies | pip-audit, npm audit, cargo audit | Unpinned version detection |

## Exit Codes

- `0` — No CRITICAL findings (build/run may proceed)
- `1` — CRITICAL vulnerabilities found (block build)
"""

_SKILL_ENFORCE = """\
---
name: agentra-enforce
description: >
  Run when the user asks to enforce security policies, check governance rules,
  or validate the codebase against security standards.
version: 1.0.0
argument-hint: [path]
allowed-tools: [Bash]
---

# Agentra Policy Enforcement

Run `ag enforce` to check 31 security policies (21 governance + 10 OWASP):

```bash
# Run governance scan
ag enforce

# Full validation pipeline (governance + compliance + optimization + scan)
ag validate

# Explain a specific rule
ag explain VULN-003
ag explain DB-001
```

## Policy Categories

| Category | Count | Coverage |
|----------|-------|---------|
| Database | 3 | DROP protection, mutations, rollbacks |
| Execution | 4 | Shell safety, eval/exec, destructive ops |
| Secrets | 3 | Hardcoded creds, logging, persistence |
| Git | 3 | Force push, history rewrite, secret commits |
| Infrastructure | 3 | Public resources, IAM, encryption |
| Prompt Injection | 3 | Injection detection, hidden injections |
| Runtime | 2 | Sandbox, approval workflows |
| **Vulnerability** | **10** | **OWASP A01–A10** |
"""

_SKILL_PREBUILD = """\
---
name: agentra-prebuild
description: >
  Run before any build or deployment command to gate on security scan results.
  Blocks builds if CRITICAL vulnerabilities are found.
version: 1.0.0
argument-hint: <build-command>
allowed-tools: [Bash]
---

# Agentra Pre-Build Security Gate

Use `ag prebuild` to run a security scan before executing any build command:

```bash
# Gate before docker build
ag prebuild "docker build -t myapp ."

# Gate before npm build
ag prebuild "npm run build"

# Gate before Python build
ag prebuild "python -m build"

# Gate before running tests
ag prebuild "pytest tests/"
```

## How It Works

1. Runs `ag scan` (OWASP + deps + SAST)
2. If CRITICAL findings → **blocks** the build command and shows findings
3. If HIGH findings → **warns** but allows build to proceed
4. If MEDIUM/LOW only → **proceeds** with the build command

## Git Hooks

Install permanent pre-commit and pre-push hooks:

```bash
ag hooks install
ag hooks status
ag hooks uninstall
```
"""

_README = """\
# Agentra Plugin for Claude Code

Enterprise AI engineering control plane — security scanning, OWASP vulnerability
detection, governance policy enforcement, and Karpathy coding guidelines.

## Installation

```bash
/plugin install agentra@claude-plugins
```

Or from source:

```bash
/plugin add /path/to/agentra-plugin
```

## Skills

| Skill | Trigger | Description |
|-------|---------|-------------|
| `agentra-guardian` | Automatic | Karpathy guidelines + security baseline on all code |
| `/agentra-scan` | Manual | Run vulnerability scan (OWASP + SAST + deps) |
| `/agentra-enforce` | Manual | Run governance policy checks |
| `/agentra-prebuild <cmd>` | Manual | Security gate before build commands |

## Pre-Tool-Use Hook

The plugin includes a `hooks/pre-tool-use.sh` hook that automatically intercepts
Bash tool calls matching build patterns (`docker build`, `npm run build`, `pytest`, etc.)
and runs `ag scan` before allowing them to proceed.

CRITICAL vulnerabilities block the build. The hook can be disabled per-session with:
```bash
export AGENTRA_SKIP_SCAN=1
```

## Standalone CLI

```bash
pip install agentra

ag init          # Initialize project
ag scan          # Vulnerability scan
ag enforce       # Policy checks
ag validate      # Full pipeline
ag prebuild <cmd>  # Pre-build gate
ag hooks install # Install git hooks
```

## License

MIT
"""


class PluginGenerator:
    """Generates a Claude Code plugin package directory for Agentra."""

    def generate(self, output_dir: Path, config: ProjectConfig | None = None) -> list[Path]:
        """
        Write the plugin package to output_dir.
        Returns list of created file paths.
        """
        written: list[Path] = []
        plugin_root = output_dir

        # .claude-plugin/plugin.json
        claude_plugin_dir = plugin_root / ".claude-plugin"
        claude_plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_json = claude_plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps(_PLUGIN_JSON, indent=2), encoding="utf-8")
        written.append(plugin_json)

        # hooks/pre-tool-use.sh
        hooks_dir = plugin_root / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_path = hooks_dir / "pre-tool-use.sh"
        hook_path.write_text(_PRE_TOOL_USE_HOOK, encoding="utf-8")
        # Make executable
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        written.append(hook_path)

        # skills/
        skills = {
            "agentra-guardian": _SKILL_GUARDIAN,
            "agentra-scan": _SKILL_SCAN,
            "agentra-enforce": _SKILL_ENFORCE,
            "agentra-prebuild": _SKILL_PREBUILD,
        }
        for skill_name, content in skills.items():
            skill_dir = plugin_root / "skills" / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(content, encoding="utf-8")
            written.append(skill_md)

        # README.md
        readme_path = plugin_root / "README.md"
        readme_path.write_text(_README, encoding="utf-8")
        written.append(readme_path)

        return written
