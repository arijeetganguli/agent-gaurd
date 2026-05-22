<div align="center">

# Agent Guard

**Enterprise AI Engineering Control Plane**

Secure, govern, and optimize AI coding agents — automatically.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-72%20passed-3fb950)](tests/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

</div>

---

Agent Guard is a DevSecOps control plane for AI coding assistants. It auto-detects your project stack, enforces 21 security policies across 7 categories, manages context token budgets, and generates tailored instruction files for every major agent platform.

<table>
<tr><td><strong>40+</strong> Technologies Detected</td><td><strong>21</strong> Security Policies</td><td><strong>14</strong> Built-in Skills</td></tr>
<tr><td><strong>7</strong> Agent Platforms</td><td><strong>5</strong> Compliance Frameworks</td><td><strong>11</strong> CLI Commands</td></tr>
</table>

## Quick Start

```bash
# Install
pip install agent-guard-ai

# Initialize — auto-detect stack, generate agent instruction files
ag init --mode quick

# Run security governance checks
ag enforce

# Check a command before running it
ag simulate "rm -rf /tmp/build"

# Run benchmarks and generate reports
ag benchmark
```

## Features

| Feature | Description |
|---------|-------------|
| 🔍 **Stack Detection** | Auto-detect languages, frameworks, databases, cloud providers, CI/CD, and agents with confidence scores |
| 🛡 **Security Governance** | 21 policies across database, execution, secret, git, infrastructure, prompt injection, and runtime categories |
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
| `ag optimize` | Show token optimization analysis: deduplication, compression, budget fitting |
| `ag simulate <cmd>` | Dry-run a command through the execution safety engine |
| `ag explain <rule>` | Display full details of a security policy (e.g., `ag explain SEC-001`) |
| `ag validate` | Full pipeline: governance + compliance + optimization in one command |
| `ag benchmark` | Run skill benchmarks, generate Markdown + HTML reports |
| `ag audit` | View local audit log of all Agent Guard actions |
| `ag doctor` | Health check: verify config, agent files, .gitignore |
| `ag version` | Display version |

### Usage Examples

```bash
# Enterprise mode with SOC2 + ISO27001 compliance
ag init --mode enterprise --agents claude,copilot

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

21 built-in policies across 7 categories:

| Category | Policies | Key Rules |
|----------|----------|-----------|
| **Database** | DB-001, DB-002, DB-003 | No auto-DROP, no unguarded mutations, require rollback plans |
| **Execution** | EX-001 – EX-004 | No inline shell, no curl\|bash, no eval/exec, no rm -rf |
| **Secrets** | SEC-001 – SEC-003 | No hardcoded secrets, no key logging, no secret persistence |
| **Git** | GIT-001 – GIT-003 | No force push, no main commits, no secret commits |
| **Infrastructure** | INF-001 – INF-003 | No public resources, no wildcard IAM, require encryption |
| **Prompt Injection** | PI-001 – PI-003 | Detect injection, hidden injections, validate external instructions |
| **Runtime** | RT-001, RT-002 | No debug in prod, require error handling |

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
agent_guard/
├── cli/             # Typer CLI with Rich output
├── detection/       # Stack detection engine (40+ technologies)
├── governance/      # Security policy engine (21 rules, 7 categories)
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

Agent Guard uses `.agent-guard.yml`:

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
ruff check agent_guard/

# Type check
mypy agent_guard/
```

## Acknowledgements

This project was inspired by [agent-policykit](https://github.com/sidrat2612/agent-policykit) by **Siddharth Rathore**. Thanks for the idea and the foundational work that sparked Agent Guard.

## License

MIT
