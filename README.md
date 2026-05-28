<div align="center">

# Agentra

**Enterprise AI Engineering Control Plane**

Secure, govern, and optimize AI coding agents — automatically.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-72%20passed-3fb950)](tests/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

</div>

---

Agentra is a DevSecOps control plane for AI coding assistants. It auto-detects your project stack, enforces 32 security policies across 8 categories (including the OWASP Top 10), manages context token budgets, generates tailored instruction files for every major agent platform, and gates builds against real vulnerability scans.

<table>
<tr><td><strong>40+</strong> Technologies Detected</td><td><strong>32</strong> Security Policies</td><td><strong>14</strong> Built-in Skills</td></tr>
<tr><td><strong>7</strong> Agent Platforms</td><td><strong>5</strong> Compliance Frameworks</td><td><strong>15</strong> CLI Commands</td></tr>
</table>

## Quick Start

```bash
# Install
pip install agentra

# Initialize — auto-detect stack, generate agent instruction files
ag init --mode quick

# Run security vulnerability scan (OWASP Top 10 + SAST + CVE)
ag scan

# Security gate: scan then build only if clean
ag prebuild "docker build ."

# Run security governance checks
ag enforce

# Check a command before running it
ag simulate "rm -rf /tmp/build"

# Install git hooks (pre-commit + pre-push security gates)
ag hooks install

# Generate a Claude Code plugin package
ag plugin

# Run benchmarks and generate reports
ag benchmark
```

## Features

| Feature | Description |
|---------|-------------|
| 🔍 **Stack Detection** | Auto-detect languages, frameworks, databases, cloud providers, CI/CD, and agents with confidence scores |
| 🛡 **Security Governance** | 32 policies across 8 categories including OWASP Top 10 (A01–A10) |
| 🔬 **Vulnerability Scanning** | Pre-build OWASP pattern scan, SAST (bandit/semgrep), and dependency CVE scan (pip-audit/npm audit/cargo audit) |
| 🚦 **Pre-Build Security Gates** | Block builds on CRITICAL findings; CI templates for GitHub Actions, GitLab CI, and generic shell |
| 🪝 **Git Hooks** | Auto-install pre-commit (OWASP scan) and pre-push (full scan) hooks with clean install/uninstall |
| 🔌 **Claude Code Plugin** | Distributable plugin package with PreToolUse hook, 4 skills, and Karpathy coding guidelines |
| 🧩 **Skills System** | 14 domain skills (FastAPI, Terraform, K8s, Spark, Airflow, PostgreSQL, Snowflake, dbt, Kafka, OpenAI, LangChain, MCP, Databricks, Karpathy) |
| 📦 **Token Optimization** | Deduplicate, prioritize, compress, and budget-fit instructions — 30-60% token savings |
| 🔌 **Agent Adapters** | Native instruction files for Claude, Cursor, Copilot, Aider, Windsurf, Continue.dev, and universal AGENTS.md |
| ⚙ **Execution Safety** | Risk-classify commands, block destructive patterns, sandbox with approval gates, dry-run mode |
| ✓ **Compliance** | Map violations to SOC2, ISO27001, PCI DSS, HIPAA, NIST frameworks |
| 📊 **Benchmarking** | Before/after metrics for every skill with HTML + Markdown report generation |

## CLI Commands

| Command | Description |
|---------|-------------|
| `ag init` | Initialize project — detect stack, save config, generate agent files |
| `ag detect` | Scan and display detected technologies with confidence scores |
| `ag enforce` | Run security policies against codebase, report violations with risk scoring |
| `ag scan` | Vulnerability scan: OWASP Top 10 patterns, SAST (bandit/semgrep), dependency CVEs |
| `ag scan --incremental` | Incremental scan — only files changed since last `ag index` run |
| `ag index` | Build/update the persistent code knowledge graph and TF-IDF RAG index |
| `ag patterns` | Detect code smells and anti-patterns using the knowledge graph |
| `ag prebuild <cmd>` | Security gate — scan then run build command only if no CRITICAL findings |
| `ag hooks <action>` | Manage git hooks (install/uninstall/status) and generate CI templates |
| `ag plugin` | Generate a Claude Code plugin package with skills and PreToolUse hook |
| `ag optimize` | Show token optimization analysis: deduplication, compression, budget fitting |
| `ag simulate <cmd>` | Dry-run a command through the execution safety engine |
| `ag explain <rule>` | Display full details of a security policy (e.g., `ag explain SEC-001`) |
| `ag validate` | Full pipeline: governance + compliance + optimization in one command |
| `ag benchmark` | Run skill benchmarks including scan-efficiency comparison (full vs knowledge graph) |
| `ag audit` | View local audit log of all Agentra actions |
| `ag doctor` | Health check: verify config, agent files, .gitignore |
| `ag version` | Display version |

### Usage Examples

```bash
# Enterprise mode with SOC2 + ISO27001 compliance
ag init --mode enterprise --agents claude,copilot

# Build the code knowledge graph index (run once, then keep updated)
ag index                            # Full index build
ag index --force                    # Force rebuild from scratch
ag index --format json              # Machine-readable output

# Detect code smells and anti-patterns
ag patterns                         # Whole project (requires ag index)
ag patterns --file src/api.py       # Single file (no index needed)
ag patterns --severity high         # Filter by severity

# Full vulnerability scan — OWASP + SAST + deps
ag scan

# Incremental scan (only changed files since last ag index)
ag scan --incremental               # Default when index exists
ag scan --no-incremental            # Force full scan

# Scan with specific targets
ag scan --owasp --deps              # OWASP patterns + dependency CVEs
ag scan --sast                     # SAST only (requires bandit or semgrep)
ag scan --format json > report.json  # Machine-readable output

# Security gate before any build
ag prebuild "docker build ."
ag prebuild "python -m pytest" --block-high

# Git hooks
ag hooks install
ag hooks status
ag hooks ci --ci github --output .github/workflows/security.yml

# Generate Claude Code plugin
ag plugin --output my-plugin/
# Then in Claude Code: /plugin add my-plugin/

# Explain a specific policy rule
ag explain DB-001
#   DB-001 — no-auto-drop
#   Severity: CRITICAL │ Category: database
#   Never auto-execute DROP TABLE/DATABASE without explicit approval

# Full validation pipeline
ag validate
#   Governance:  4 violations │ Risk: 29.0 │ Blast Radius: high
#   Compliance:  SOC2: 3 findings │ PCI_DSS: 2 findings
#   Optimization: 3,840 → 2,112 tokens (45.0% reduction)
```

## Security Policies

32 built-in policies across 8 categories:

| Category | Policies | Key Rules |
|----------|----------|-----------|
| **Database** | DB-001, DB-002, DB-003 | No auto-DROP, no unguarded mutations, require rollback plans |
| **Execution** | EX-001 – EX-005 | No inline shell, no curl\|bash, no eval/exec, no rm -rf, no inline code args (python -c, node -e, bash -c) |
| **Secrets** | SEC-001 – SEC-003 | No hardcoded secrets, no key logging, no secret persistence |
| **Git** | GIT-001 – GIT-003 | No force push, no main commits, no secret commits |
| **Infrastructure** | INF-001 – INF-003 | No public resources, no wildcard IAM, require encryption |
| **Prompt Injection** | PI-001 – PI-003 | Detect injection, hidden injections, validate external instructions |
| **Runtime** | RT-001, RT-002 | No debug in prod, require error handling |
| **Vulnerability (OWASP)** | VULN-001 – VULN-010 | A01 Broken Access Control, A02 Crypto, A03 Injection, A04 Design, A05 Misconfiguration, A06 Components, A07 Auth Failures, A08 Deserialization, A09 Logging, A10 SSRF |

## Agent Adapters

Generates native instruction files for each platform:

| Platform | Output File | Format |
|----------|-------------|--------|
| **Claude** | `CLAUDE.md` | Markdown |
| **Cursor** | `.cursorrules` | Markdown |
| **GitHub Copilot** | `.github/copilot-instructions.md` | Markdown |
| **Aider** | `.aider.conf.yml` | YAML |
| **Windsurf** | `.windsurfrules` | Markdown |
| **Continue.dev** | `.continue/config.json` | JSON |
| **Universal** | `AGENTS.md` | Markdown |

## Architecture

```
agentra/
├── cli/             # Typer CLI with Rich output
├── detection/       # Stack detection engine (40+ technologies)
├── governance/      # Security policy engine (32 rules, 8 categories)
├── scanner/         # Vulnerability scanning: OWASP patterns, SAST, deps CVE
├── index/           # Persistent code knowledge graph (SQLite + tree-sitter)
├── rag/             # TF-IDF RAG engine + anti-pattern library (12 patterns)
├── hooks/           # Git hook management + CI template generation
├── plugin/          # Claude Code plugin generator
├── optimizer/       # Token optimization (dedup, prioritize, compress, budget-fit)
├── adapters/        # Agent platform adapters (7 platforms)
├── skills/          # Domain skill packs (14 built-in)
├── execution/       # Execution safety engine (risk classify, sandbox, approve)
├── onboarding/      # Project initialization (4 modes)
├── compliance/      # Compliance mapping (SOC2, ISO27001, PCI DSS, HIPAA, NIST)
├── benchmarks/      # Skill benchmarking with before/after metrics
├── renderers/       # HTML + Markdown report generation
├── risk/            # Risk scoring and blast radius estimation
├── telemetry/       # Local-only JSON audit logging
└── models.py        # Pydantic data models
```

## Onboarding Modes

| Mode | Security | Compliance | Token Budget | Best For |
|------|----------|------------|-------------|----------|
| `quick` | Standard | — | 12k / 4k / 2k | Fast dev setup |
| `guided` | Strict | All 5 frameworks | 12k / 4k / 2k | Interactive comprehensive |
| `enterprise` | Enterprise | SOC2 + ISO27001 | 16k / 6k / 3k | Production deployments |
| `ci` | Standard | — | 8k / 3k / 1.5k | CI/CD pipelines |

## Benchmarking & Reports

Every skill is benchmarked with before/after metrics:

- **Instruction Token Cost** — tokens consumed by skill instructions
- **Security Policy Coverage** — policies activated by the skill
- **Context Relevance** — stack-match relevance score (0–1)
- **Instruction Compression** — compression ratio achieved

```bash
ag benchmark --output reports/
# ✓ Benchmark report (MD):   reports/benchmark-report.md
# ✓ Benchmark report (HTML): reports/benchmark-report.html
```

The HTML report is a self-contained dark-themed dashboard with stat cards, metric bars, and tables. Open it directly in a browser.

## Configuration

Agentra uses `.agentra.yml`:

```yaml
project:
  name: my-project
  languages: [python]
  frameworks: [fastapi]
  sdks: [openai]

security:
  mode: enterprise
  edr_safe: true
  compliance: [SOC2, ISO27001]

optimization:
  minimal_context: true
  token_budget:
    input: 12000
    output: 4000

agents: [claude, copilot, cursor]
skills: [fastapi, postgresql, karpathy]
karpathy_guidelines: true   # Embed behavioral coding guidelines in all agent files
scanner_enabled: true       # Enable pre-build vulnerability scanning
```

## Pre-Build Security Gates

Agentra intercepts builds before they run and gates on vulnerability findings:

```bash
# Manual gate
ag prebuild "docker build ."
# → Runs OWASP + SAST + deps scan
# → Blocks if CRITICAL findings (exit 1)
# → Warns on HIGH findings (continues)

# Git hook gate (auto-runs on every commit/push)
ag hooks install
# → pre-commit: OWASP scan (fast, <5s)
# → pre-push:   full scan (OWASP + SAST + deps)

# CI pipeline gate
ag hooks ci --ci github --output .github/workflows/security.yml
ag hooks ci --ci gitlab --output .gitlab-ci.yml
```

Scanner degrades gracefully — `bandit`, `semgrep`, `pip-audit`, `npm audit`, and `cargo audit` are all optional. The built-in OWASP regex scanner works with no extra dependencies.

## Claude Code Plugin

Agentra ships as a distributable Claude Code plugin:

```bash
# Generate plugin package
ag plugin --output .agentra-plugin/

# Install in Claude Code
/plugin add .agentra-plugin/
```

The plugin includes:
- **PreToolUse hook** — intercepts `bash`, `make`, `npm run`, `cargo`, `docker` commands and runs `ag scan --owasp` automatically
- **`/agentra-scan`** — run a full vulnerability scan
- **`/agentra-enforce`** — run governance policy checks
- **`/agentra-prebuild`** — security gate before a build
- **`agentra-guardian`** — always-on skill with Karpathy coding guidelines + security baseline

## Karpathy Coding Guidelines

All generated agent instruction files include Andrej Karpathy's 4 behavioral coding rules:

1. **Think Before Coding** — Read the full task before writing any code
2. **Simplicity First** — Prefer the simplest solution that works; complexity is a liability
3. **Surgical Changes** — Change only what is necessary; don't refactor opportunistically
4. **Goal-Driven Execution** — Every line must serve the stated task; delete code that doesn't

These are embedded in `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`, `.windsurfrules`, and `AGENTS.md` by default (`karpathy_guidelines: true`).

## Enterprise Features

Install the optional enterprise extras to unlock persistent code intelligence, incremental scanning, and project-specific RAG context:

```bash
pip install "agentra[enterprise]"
```

### Code Knowledge Graph

Agentra builds and maintains a **persistent SQLite knowledge graph** (`code_index.db`) of your codebase using tree-sitter multi-language AST parsing. Once indexed, scans and agent context generation are incremental — only files changed since the last index run are reprocessed.

```bash
ag index                    # Build or update the knowledge graph
ag index --force            # Full rebuild from scratch
```

The index stores:
- All functions, classes, methods, and imports with line ranges and docstrings
- Call edges between symbols for dependency and hotspot analysis
- SHA-256 content hashes per file for change detection
- Code chunks for TF-IDF retrieval

**Languages supported:** Python, JavaScript, TypeScript, Rust, Go, Java, Ruby, C, C++, C# (via tree-sitter), with regex-based fallback for all other file types.

### TF-IDF Code RAG

The RAG engine builds a TF-IDF matrix (scikit-learn, 50,000 features, sublinear TF) over all indexed code chunks. When generating agent instruction files (`CLAUDE.md`, `.cursorrules`, etc.), Agentra injects a **Codebase Patterns** section with:

- **Established patterns** — the top-3 most prevalent idioms in the codebase
- **Known code smells** — the 5 highest-severity anti-patterns to avoid repeating

This gives coding agents targeted, project-specific context instead of generic boilerplate, reducing agent context tokens by ~60–80% in steady state.

### Anti-Pattern Detection

12 built-in anti-pattern rules run on every file:

| ID | Name | Description |
|----|------|-------------|
| AP-001 | god-class | Classes > 300 lines |
| AP-002 | long-method | Functions > 50 lines |
| AP-003 | deep-nesting | Indentation > 4 levels |
| AP-004 | magic-number | Bare integer literals ≥ 2 digits |
| AP-005 | mutable-default-arg | `def f(x=[])` pattern |
| AP-006 | bare-except | `except:` with no exception type |
| AP-007 | wildcard-import | `from x import *` |
| AP-008 | commented-code | 5+ consecutive comment lines |
| AP-009 | todo-density | > 5 TODO/FIXME per file |
| AP-010 | missing-type-hints | Public functions without annotations |
| AP-011 | duplicate-chunk | TF-IDF cosine similarity > 0.92 |
| AP-012 | global-mutation | `global x` inside functions |

```bash
ag patterns                         # Scan whole project
ag patterns --file src/api.py       # Single file scan
ag patterns --severity high         # Filter by severity
ag patterns --format json           # Machine-readable output
```

### Incremental Scanning

Once the knowledge graph is built, `ag scan` automatically uses incremental mode:

```bash
ag scan --incremental               # Default: only changed files
ag scan --no-incremental            # Force full scan
```

In steady state (10% of files change per run), this reduces scan token cost by ~90% and wall time proportionally.

### Scan Efficiency Benchmark

`ag benchmark` now includes a **Scan Efficiency** benchmark that compares full scan vs knowledge-graph-incremental scan across four metrics: files traversed, content tokens scanned, agent context tokens, and scan wall time. Run without an index for projected values; run after `ag index` for real measurements.

### Configuration

```yaml
# .agentra.yml (enterprise sections)
index:
  path: .agentra          # Where to store code_index.db and RAG store
  enabled: true
  exclude:                # Patterns to exclude from indexing
    - "*.generated.*"
    - "migrations/"

rag:
  enabled: true
  top_k: 5               # Similar chunks to retrieve
  antipatterns: true     # Run anti-pattern detection during indexing
  include_in_agent_files: true  # Inject patterns block into CLAUDE.md etc.
```

## Documentation

Full interactive documentation is available at [`docs/index.html`](docs/index.html) — a storybook-style guide covering every feature, command, policy, skill, and adapter with usage examples. A Markdown version is at [`docs/index.md`](docs/index.md).

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (72 tests)
pytest tests/ -v

# Lint
ruff check agentra/

# Type check
mypy agentra/
```

## Acknowledgements

This project was inspired by [agent-policykit](https://github.com/sidrat2612/agent-policykit) by **Siddharth Rathore**. Thanks for the idea and the foundational work that sparked Agentra.

## License

MIT
