# Agentra — Benchmark Report

**Project:** agent-gaurd
**Generated:** 2026-05-22 05:45:02 UTC

## Detected Stack

| Category | Components |
|----------|-----------|
| Languages | python (90%) |
| Infrastructure | kubernetes (60%), docker (80%) |
| CI/CD | github_actions (80%) |

## Governance Summary

- **Status:** ❌ FAILED
- **Violations:** 35
- **Risk Score:** 286.0
- **Blast Radius:** critical

### Violations

| ID | Severity | Category | Rule | File |
|----|----------|----------|------|------|
| GIT-003 | critical | git | no-secret-commits | C:\Users\agangu\Repos\Personal\agent-gaurd\.gitignore |
| GIT-003 | critical | git | no-secret-commits | C:\Users\agangu\Repos\Personal\agent-gaurd\.gitignore |
| GIT-003 | critical | git | no-secret-commits | C:\Users\agangu\Repos\Personal\agent-gaurd\.gitignore |
| GIT-003 | critical | git | no-secret-commits | C:\Users\agangu\Repos\Personal\agent-gaurd\.gitignore |
| GIT-003 | critical | git | no-secret-commits | C:\Users\agangu\Repos\Personal\agent-gaurd\.gitignore |
| EX-004 | critical | execution | no-autonomous-destructive | C:\Users\agangu\Repos\Personal\agent-gaurd\Makefile |
| EX-004 | critical | execution | no-autonomous-destructive | C:\Users\agangu\Repos\Personal\agent-gaurd\Makefile |
| SEC-001 | critical | secret | no-hardcoded-secrets | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\models.py |
| SEC-003 | high | secret | no-secret-persistence | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\benchmarks\runner.py |
| DB-002 | critical | database | no-prod-mutations | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\execution\engine.py |
| EX-001 | high | execution | no-inline-shell | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\execution\engine.py |
| EX-001 | high | execution | no-inline-shell | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\execution\engine.py |
| EX-001 | high | execution | no-inline-shell | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\execution\engine.py |
| EX-001 | high | execution | no-inline-shell | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\execution\engine.py |
| EX-001 | high | execution | no-inline-shell | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\governance\policies.py |
| EX-001 | high | execution | no-inline-shell | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\governance\policies.py |
| SEC-003 | high | secret | no-secret-persistence | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\governance\policies.py |
| SEC-003 | high | secret | no-secret-persistence | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\governance\policies.py |
| GIT-001 | high | git | no-force-push | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\governance\policies.py |
| INF-001 | high | infrastructure | no-public-resources | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\governance\policies.py |
| PI-002 | critical | prompt_injection | detect-hidden-injections | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\governance\policies.py |
| PI-003 | high | prompt_injection | validate-external-instructions | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\governance\policies.py |
| PI-003 | high | prompt_injection | validate-external-instructions | C:\Users\agangu\Repos\Personal\agent-gaurd\agentra\governance\policies.py |
| EX-002 | critical | execution | no-curl-pipe-bash | C:\Users\agangu\Repos\Personal\agent-gaurd\tests\test_execution.py |
| EX-004 | critical | execution | no-autonomous-destructive | C:\Users\agangu\Repos\Personal\agent-gaurd\tests\test_execution.py |
| EX-004 | critical | execution | no-autonomous-destructive | C:\Users\agangu\Repos\Personal\agent-gaurd\tests\test_execution.py |
| EX-004 | critical | execution | no-autonomous-destructive | C:\Users\agangu\Repos\Personal\agent-gaurd\tests\test_execution.py |
| EX-004 | critical | execution | no-autonomous-destructive | C:\Users\agangu\Repos\Personal\agent-gaurd\tests\test_execution.py |
| GIT-001 | high | git | no-force-push | C:\Users\agangu\Repos\Personal\agent-gaurd\tests\test_execution.py |
| EX-002 | critical | execution | no-curl-pipe-bash | C:\Users\agangu\Repos\Personal\agent-gaurd\tests\test_governance.py |

## Token Optimization

| Metric | Value |
|--------|-------|
| Original tokens | 533 |
| Optimized tokens | 533 |
| Reduction | 0.0% |
| Rules included | 19 |
| Rules excluded | 0 |

## Skill Benchmarks

### FastAPI Engineering ✅

- **ID:** `fastapi`
- **Verified:** All required fields present.

| Metric | Before | After | Unit | Improvement |
|--------|--------|-------|------|-------------|
| Instruction Token Cost | 0 | 165 | tokens | 0.0% |
| Security Policy Coverage | 0 | 2 | policies | 100.0% |
| Context Relevance | 0 | 1 | score (0-1) | 100.0% |
| Instruction Compression | 11 | 5 | lines | 54.5% |

_Best improvement: Security Policy Coverage — 100.0% gain._

### Airflow DAG Engineering ✅

- **ID:** `airflow`
- **Verified:** All required fields present.

| Metric | Before | After | Unit | Improvement |
|--------|--------|-------|------|-------------|
| Instruction Token Cost | 0 | 143 | tokens | 0.0% |
| Security Policy Coverage | 0 | 2 | policies | 100.0% |
| Context Relevance | 0 | 1 | score (0-1) | 100.0% |
| Instruction Compression | 11 | 6 | lines | 45.5% |

_Best improvement: Security Policy Coverage — 100.0% gain._

### Apache Spark Engineering ✅

- **ID:** `spark`
- **Verified:** All required fields present.

| Metric | Before | After | Unit | Improvement |
|--------|--------|-------|------|-------------|
| Instruction Token Cost | 0 | 142 | tokens | 0.0% |
| Security Policy Coverage | 0 | 1 | policies | 100.0% |
| Context Relevance | 0 | 1 | score (0-1) | 100.0% |
| Instruction Compression | 11 | 6 | lines | 45.5% |

_Best improvement: Security Policy Coverage — 100.0% gain._

### Kubernetes Engineering ✅

- **ID:** `kubernetes`
- **Verified:** All required fields present.

| Metric | Before | After | Unit | Improvement |
|--------|--------|-------|------|-------------|
| Instruction Token Cost | 0 | 128 | tokens | 0.0% |
| Security Policy Coverage | 0 | 2 | policies | 100.0% |
| Context Relevance | 0 | 1 | score (0-1) | 100.0% |
| Instruction Compression | 11 | 6 | lines | 45.5% |

_Best improvement: Security Policy Coverage — 100.0% gain._

### Karpathy Engineering Philosophy ✅

- **ID:** `karpathy`
- **Verified:** All required fields present.

| Metric | Before | After | Unit | Improvement |
|--------|--------|-------|------|-------------|
| Instruction Token Cost | 0 | 221 | tokens | 0.0% |
| Security Policy Coverage | 0 | 0 | policies | 0.0% |
| Context Relevance | 0 | 0.8 | score (0-1) | 80.0% |
| Instruction Compression | 15 | 6 | lines | 60.0% |

_Best improvement: Context Relevance — 80.0% gain._

### Security Governance Engine ✅

- **ID:** `governance-engine`
- **Verified:** Governance engine operational. 21 policies loaded.

| Metric | Before | After | Unit | Improvement |
|--------|--------|-------|------|-------------|
| Total Policies Active | 0 | 21 | policies | 100.0% |
| Violations Detected | 0 | 35 | violations | 100.0% |
| Risk Score | 100 | 286 | score | 0.0% |
| Compliance Coverage | 0 | 5 | frameworks | 100.0% |

_Best improvement: Total Policies Active — 100.0% gain._

### Token Optimization Engine ✅

- **ID:** `optimization-engine`
- **Verified:** Optimization engine operational. 0.0% token reduction.

| Metric | Before | After | Unit | Improvement |
|--------|--------|-------|------|-------------|
| Token Reduction | 533 | 533 | tokens | 0.0% |
| Rules Included | 19 | 19 | rules | 0.0% |

_Skill active with baseline metrics._

---
*Generated by Agentra — Enterprise AI Engineering Control Plane*