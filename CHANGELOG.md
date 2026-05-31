# Changelog

All notable changes to Agentra will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] — 2026-05-31

### Fixed
- `tests/test_graph.py` — pass `--include-orphans` in `test_generates_html_from_real_index` so the test works in CI where pyan3 (enterprise extra) is absent
- `tests/test_rag.py` — remove `mix_stderr=False` from `CliRunner` init; not supported by the Click version on CI's ubuntu runner

---

## [0.4.0] — 2026-05-31

### Added

#### Multi-Language Call Graph Dispatch (`agentra/index/engine.py`)
- **Language-aware edge extraction** — `_rebuild_edges()` dispatcher detects which languages are present and routes to the best available extractor per language
- **pyan3 for Python** — `_rebuild_edges_pyan3()` refactored to take pre-built lookup tables; whole-project cross-file analysis via pyan3's `CallGraphVisitor`; 1,726 edges on Agentra's own codebase
- **tree-sitter for all other languages** — `_rebuild_edges_treesitter()` uses `call_expression` AST queries for JavaScript, TypeScript, TSX, Go, Rust, Java, Ruby, C, C++, C#; `_TS_CALL_QUERIES` dict maps each language to the correct node pattern
- Both extractors degrade gracefully — if pyan3 or a tree-sitter grammar is not installed the extractor is silently skipped
- Pure-Python repos never touch tree-sitter; non-Python repos never invoke pyan3

#### Interactive Graph Improvements (`agentra/renderers/graph_html.py`)
- **`--include-orphans` flag** — import-only nodes and true orphans (no edges in or out) are filtered from the graph by default; `ag graph --include-orphans` restores them
- **vis.js physics tuning** — forceAtlas2Based with stronger repulsion (`gravitationalConstant: -120`), weak gravity (`centralGravity: 0.001`), longer springs (`springLength: 220`), and node mass scaling by in-degree; eliminates center clustering on large graphs
- **Node mass scaling** — high-degree nodes are heavier and settle to the center naturally; leaf nodes spread to the periphery
- **Hotspot dedup** — top-10 hotspot list deduplicates by label and filters dunder (`__init__`, `__call__`, etc.) names; list now reflects real user-defined hotspots
- **Edge opacity** — edge color opacity reduced to 0.35 for readability on dense graphs

#### New Files
- `agentra/renderers/graph_html.py` — dedicated HTML graph renderer (extracted from CLI + new physics/hotspot logic)
- `tests/test_graph.py` — 13 tests covering orphan filtering, hotspot dedup, edge counts, physics options
- `tests/test_rag.py` — RAG engine coverage

### Changed
- `agentra/cli/main.py` — `graph_cmd` computes `out_degree`, applies orphan filter, passes deduped hotspot count to renderer
- `pyproject.toml` — `enterprise` extras: `pyan3>=2.6,<3` added for whole-project Python call graph analysis
- `README.md` — updated test badge (211), `ag graph` examples (add `--include-orphans`), Code Knowledge Graph section (multi-language dispatch explanation)
- Total tests: **198 → 211** (211 passed, 1 skipped)

---

## [0.3.2] — 2026-05-30

### Added

#### Smart Model Routing (`agentra/models.py`)
- **Capability-class system** — four capability classes (`deep_reasoning`, `coding`, `balanced`, `fast`) map agent purposes to the best-fit model tier
- **`CAPABILITY_MODELS`** — best model per capability class for 8 platforms (claude, copilot, cursor, windsurf, aider, continue, roo_code, openai_codex) using current 2026 model names
- **`PURPOSE_CAPABILITY_MAP`** — 9 agent purposes (planning, reasoning, review, coding, testing, refactoring, documentation, general, formatting) each mapped to a capability class
- **`PURPOSE_MODELS`** — derived per-platform, per-purpose model routing table (not hardcoded)
- **`CAPABILITY_FALLBACK_CHAINS`** — ordered fallback chains per platform/capability for enterprise environments where primary models may be restricted
- **`resolve_model_with_fallback(platform, capability_class, restricted)`** — returns next best available model from the fallback chain, skipping any in the `restricted` set; gracefully handles unknown platforms
- **`detect_active_models()`** — probes `CLAUDE_MODEL`, `AIDER_MODEL`, `OPENAI_MODEL`, `CODEX_MODEL`, `GEMINI_MODEL` env vars and `~/.claude/settings.json` / VS Code settings to identify the currently active model per platform; returns `{platform: {model, source}}`
- Updated `KNOWN_MODELS` with 2026 model names across all platforms
- Expanded `AGENT_PURPOSES` from 5 to 9 purposes

#### New CLI Commands / Flags (`agentra/cli/main.py`)
- **`ag model list`** — table of active model + 9-purpose routing per agent; hints for changing models
- **`ag model set <agent> <model>`** — change active model for one agent and regenerate all instruction files
- **`ag model set <agent> <model> --purpose <p>`** — override model for a single purpose only
- **`ag model set <agent> --interactive`** — numbered menu of known models with capability class hints; accepts number or model name; useful in enterprise/restricted environments
- **`ag model set <agent> <model> --auto-fallback`** — if model is not in the known list, automatically selects the next best from the fallback chain for the inferred capability class
- **`ag model detect`** — probe env vars and settings files; show `Platform | Model | Source` table with explanations for IDE-controlled platforms (Copilot, Cursor, Windsurf); tips for making platforms detectable

#### Agent Adapter Changes (`agentra/adapters/agents.py`)
- **Self-identification hint** — for IDE-controlled platforms (copilot, cursor, windsurf) the generated model block now includes: *"If uncertain which model version is active, state it at the start of your response."*
- `_build_model_block` now renders a 9-purpose routing table in all Markdown agent files

#### Tests
- `TestModelFallback` (8 tests) — `resolve_model_with_fallback` primary/skip/exhausted/unknown-platform, fallback chains completeness, `detect_active_models` dict contract, env var detection for claude and aider
- `TestModelDetectCLI` (2 tests) — `ag model detect` exits 0 without config; output contains expected header
- `TestModelSetFallbackCLI` (4 tests) — unknown model warns+proceeds, `--auto-fallback` picks fallback, `--interactive` with input `"1\n"` selects first model, missing agent name errors
- Total tests: **183 → 198** (197 pass, 1 pre-existing skip)

### Changed
- `agentra/cli/main.py` — `model_cmd` refactored: `_require_config()` helper allows `detect` to run without a config; `set` action uses `cfg` variable throughout; `else` branch now lists `detect` as a valid action
- `README.md` — updated test badge (198), feature table (Smart Model Routing row), CLI table (6 new model commands), Usage Examples (model routing + detect section), stats (18 commands, 8 platforms)
- `docs/whats-new-0.3.2.html` — added `ag model detect` terminal showcase, `--auto-fallback` / `--interactive` examples, 3 new rows in command reference table, updated Smart Models description

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
