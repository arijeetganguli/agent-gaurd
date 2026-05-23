# Changelog

All notable changes to Agentra will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2025-05-23

### Added

#### Vulnerability Scanner (`agentra/scanner/`)
- **OWASP Top 10 pattern scanner** — built-in regex-based scanner for all 10 OWASP categories (A01–A10); no external dependencies required
- **SAST integration** — optional `bandit` and `semgrep` support with graceful fallback when tools are not installed
- **Dependency CVE scanner** — optional `pip-audit`, `npm audit`, and `cargo audit` integration; falls back to unpinned-version detection
- **ScanEngine** — unified orchestrator with deduplication, risk scoring, max-results cap, and `gate()` method for build blocking

#### OWASP Vulnerability Policies (`agentra/governance/policies.py`)
- 10 new policies: VULN-001 through VULN-010, one per OWASP Top 10 category
- Total policy count: **21 → 31** across **7 → 8** categories
- All mapped to SOC2 + ISO27001 compliance frameworks

#### Git Hook Management (`agentra/hooks/`)
- `ag hooks install` — installs pre-commit (OWASP scan) and pre-push (full scan) hooks
- `ag hooks uninstall` — cleanly removes Agentra-managed hook sections
- `ag hooks status` — shows hook state table
- `ag hooks ci` — generates CI security gate templates (GitHub Actions, GitLab CI, shell)

#### Claude Code Plugin Generator (`agentra/plugin/`)
- `ag plugin` — generates a distributable Claude Code plugin package
- Includes `plugin.json`, `pre-tool-use.sh` (PreToolUse hook intercepting build commands), and 4 skills
- Skills: `agentra-guardian` (always-on with Karpathy guidelines), `agentra-scan`, `agentra-enforce`, `agentra-prebuild`

#### New CLI Commands
- `ag scan` — multi-layer vulnerability scan with table or JSON output; exits 1 on CRITICAL findings
- `ag prebuild <cmd>` — security gate that scans before running a build command; blocks on CRITICAL
- `ag hooks <action>` — git hook and CI template management
- `ag plugin` — Claude Code plugin generation
- Total CLI commands: **11 → 15**

#### Karpathy Coding Guidelines
- Andrej Karpathy's 4 behavioral coding rules embedded in all Markdown agent adapters by default
- Rules: Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution
- Controlled via `karpathy_guidelines: true` in `.agentra.yml` (opt-out)
- Updated `agentra/skills/registry.py` with full behavioral guideline content

#### Models (`agentra/models.py`)
- `ScanTarget` enum: `SAST`, `DEPS`, `OWASP`, `ALL`
- `ScanResult` model with tool, severity, file_path, line, finding, rule_id, cve_id, owasp_category, fix fields
- `VulnerabilityReport` model with computed properties (critical_count, high_count, etc.)
- `VULNERABILITY` added to `PolicyCategory` enum
- `karpathy_guidelines: bool = True` and `scanner_enabled: bool = True` on `ProjectConfig`

#### Tests
- `tests/test_scanner.py` — 47 tests covering OWASP patterns, dependency scanning, ScanEngine, and policy integration
- `tests/test_plugin.py` — 20 tests covering plugin file structure, plugin.json validation, hook scripts, and skill files
- Total tests: **72 → 124** (123 pass, 1 skipped on Windows)

### Changed
- `agentra/adapters/agents.py` — all 5 Markdown adapters (Claude, Cursor, Copilot, Windsurf, AgentsMd) now conditionally include Karpathy guidelines block
- `agentra/onboarding/engine.py` — sets `karpathy_guidelines=True` and `scanner_enabled=True` for all onboarding modes; serializes to `.agentra.yml`
- `README.md` — updated feature table, CLI table (15 commands), security policies table (31 policies, 8 categories), architecture tree, new sections for scanning/hooks/plugin/Karpathy

## [0.1.0] — 2025-05-22

### Added
- Initial release
- Stack detection engine (40+ technologies)
- Security governance engine (21 policies, 7 categories)
- Token optimization (dedup, prioritize, compress, budget-fit)
- Agent adapters (Claude, Cursor, Copilot, Aider, Windsurf, Continue.dev, AGENTS.md)
- Skills system (14 built-in domain skills)
- Execution safety engine (risk classify, sandbox, approve)
- Onboarding engine (4 modes: quick, guided, enterprise, CI)
- Compliance mapping (SOC2, ISO27001, PCI DSS, HIPAA, NIST)
- Benchmarking with HTML + Markdown reports
- CLI with 11 commands
- 72 tests
