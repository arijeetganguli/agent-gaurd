"""Engineering Skill System — reusable skill packs for stack-specific guidance."""

from __future__ import annotations

from agentra.models import Skill


# ── Built-in Skill Definitions ───────────────────────────────────────────────

BUILTIN_SKILLS: dict[str, Skill] = {

    # ── FastAPI ──────────────────────────────────────────────────────────────
    "fastapi": Skill(
        id="fastapi",
        name="FastAPI Engineering",
        description="Production FastAPI patterns, security, and performance.",
        stacks=["python", "fastapi"],
        instructions="""## FastAPI Best Practices
- Use Pydantic v2 models for all request/response schemas.
- Use dependency injection for database sessions, auth, and config.
- Use async def for I/O-bound endpoints; def for CPU-bound.
- Use HTTPException with proper status codes; never return raw dicts for errors.
- Use lifespan context manager for startup/shutdown.
- Use middleware for CORS, logging, and request ID tracking.
- Structure: routers/ for endpoints, services/ for business logic, models/ for schemas.
- Always validate path/query params with Annotated types.
- Use BackgroundTasks for non-blocking work, not threads.
- Enable OpenAPI docs but disable in production.""",
        policies=["SEC-001", "EX-001"],
        optimization_rules=["Inject only when FastAPI detected", "Skip if no Python files"],
        examples=[
            "from fastapi import FastAPI, Depends, HTTPException",
            "app = FastAPI(lifespan=lifespan)",
        ],
    ),

    # ── Airflow ──────────────────────────────────────────────────────────────
    "airflow": Skill(
        id="airflow",
        name="Airflow DAG Engineering",
        description="Production Airflow DAG patterns and anti-patterns.",
        stacks=["python", "airflow"],
        instructions="""## Airflow Best Practices
- Use TaskFlow API (@task decorator) for Python tasks.
- Never do heavy computation in DAG definition files.
- Use XCom sparingly; prefer external storage for large data.
- Set explicit retries, retry_delay, and execution_timeout.
- Use Connections and Variables from Airflow UI, not hardcoded.
- Use Sensors with poke_interval and timeout.
- Prefer KubernetesPodOperator or DockerOperator for isolation.
- Use DAG tags for organization and filtering.
- Set catchup=False unless historical backfill is needed.
- Use on_failure_callback for alerting.""",
        policies=["SEC-001", "DB-002"],
        optimization_rules=["Inject only when airflow detected"],
    ),

    # ── Spark ────────────────────────────────────────────────────────────────
    "spark": Skill(
        id="spark",
        name="Apache Spark Engineering",
        description="PySpark production patterns and optimization.",
        stacks=["python", "spark"],
        instructions="""## Spark Best Practices
- Use DataFrame API over RDD API.
- Avoid collect() on large datasets; use take() or show().
- Partition data appropriately; avoid small file problem.
- Use broadcast joins for small dimension tables.
- Cache/persist only when data is reused multiple times.
- Use spark.sql.adaptive.enabled = true for adaptive query execution.
- Monitor with Spark UI; watch for data skew and spill.
- Use Delta Lake or Iceberg for ACID transactions.
- Write unit tests with small local DataFrames.
- Set proper executor memory and cores; avoid over-provisioning.""",
        policies=["DB-002"],
        optimization_rules=["Inject only when pyspark detected"],
    ),

    # ── Terraform ────────────────────────────────────────────────────────────
    "terraform": Skill(
        id="terraform",
        name="Terraform IaC Engineering",
        description="Production Terraform patterns and security.",
        stacks=["terraform"],
        instructions="""## Terraform Best Practices
- Use modules for reusable infrastructure components.
- Use remote state (S3 + DynamoDB locking).
- Never hardcode credentials in .tf files.
- Use variables with type constraints and validation blocks.
- Use terraform plan before apply; review changes.
- Use lifecycle { prevent_destroy = true } for critical resources.
- Tag all resources with owner, environment, and project.
- Use data sources to reference existing resources.
- Use workspaces or separate state files per environment.
- Pin provider versions; use required_providers block.""",
        policies=["INF-001", "INF-002", "INF-003", "SEC-001"],
        optimization_rules=["Inject only when .tf files detected"],
    ),

    # ── Kubernetes ───────────────────────────────────────────────────────────
    "kubernetes": Skill(
        id="kubernetes",
        name="Kubernetes Engineering",
        description="Production Kubernetes patterns and security.",
        stacks=["kubernetes"],
        instructions="""## Kubernetes Best Practices
- Set resource requests and limits for all containers.
- Use namespaces for isolation.
- Never run containers as root; use securityContext.
- Use NetworkPolicies to restrict pod communication.
- Use Secrets for sensitive config; never ConfigMaps for secrets.
- Use readiness and liveness probes.
- Use PodDisruptionBudgets for availability.
- Use Helm or Kustomize for templating; avoid raw kubectl apply.
- Use RBAC with least privilege.
- Use pod anti-affinity for high availability.""",
        policies=["INF-001", "SEC-001"],
        optimization_rules=["Inject only when k8s manifests detected"],
    ),

    # ── PostgreSQL ───────────────────────────────────────────────────────────
    "postgresql": Skill(
        id="postgresql",
        name="PostgreSQL Engineering",
        description="Production PostgreSQL patterns and safety.",
        stacks=["postgresql"],
        instructions="""## PostgreSQL Best Practices
- Use parameterized queries; never string-concatenate SQL.
- Use connection pooling (PgBouncer or application-level).
- Use migrations (Alembic/Flyway) for schema changes.
- Add indexes for frequently queried columns; use EXPLAIN ANALYZE.
- Use JSONB over JSON for queryable JSON data.
- Use Row-Level Security (RLS) for multi-tenant data.
- Use transactions for multi-step operations.
- Set statement_timeout for long-running queries.
- Use pg_stat_statements for query monitoring.
- Never use superuser credentials in application code.""",
        policies=["DB-001", "DB-002", "DB-003", "SEC-001"],
        optimization_rules=["Inject only when PostgreSQL detected"],
    ),

    # ── Snowflake ────────────────────────────────────────────────────────────
    "snowflake": Skill(
        id="snowflake",
        name="Snowflake Data Engineering",
        description="Production Snowflake patterns and cost optimization.",
        stacks=["snowflake"],
        instructions="""## Snowflake Best Practices
- Use appropriate warehouse sizes; auto-suspend after idle.
- Use COPY INTO for bulk loading; avoid row-by-row inserts.
- Use clustering keys for large tables with range queries.
- Use Time Travel for recovery; set DATA_RETENTION_TIME_IN_DAYS.
- Use Secure Views for data sharing.
- Use roles and grants following least privilege.
- Monitor with QUERY_HISTORY and WAREHOUSE_METERING_HISTORY.
- Use Streams and Tasks for CDC pipelines.
- Prefer Snowpark over stored procedures for complex logic.
- Use Resource Monitors to control costs.""",
        policies=["DB-001", "DB-002", "SEC-001"],
        optimization_rules=["Inject only when Snowflake SDK detected"],
    ),

    # ── Databricks ───────────────────────────────────────────────────────────
    "databricks": Skill(
        id="databricks",
        name="Databricks Engineering",
        description="Production Databricks patterns and Unity Catalog.",
        stacks=["databricks"],
        instructions="""## Databricks Best Practices
- Use Unity Catalog for governance and access control.
- Use Delta Lake for all table storage.
- Use Workflows for orchestration; avoid notebook scheduling.
- Use cluster policies to control compute costs.
- Use instance pools for faster cluster startup.
- Use secrets scope for credentials; never hardcode.
- Use MLflow for experiment tracking and model registry.
- Prefer SQL Warehouses for BI queries.
- Use Auto Loader for incremental ingestion.
- Monitor with System Tables and Overwatch.""",
        policies=["SEC-001", "DB-002"],
        optimization_rules=["Inject only when Databricks SDK detected"],
    ),

    # ── dbt ──────────────────────────────────────────────────────────────────
    "dbt": Skill(
        id="dbt",
        name="dbt Analytics Engineering",
        description="Production dbt patterns and testing.",
        stacks=["dbt"],
        instructions="""## dbt Best Practices
- Use staging models to clean raw data; marts for business logic.
- Add tests: unique, not_null, accepted_values, relationships.
- Use sources with freshness checks.
- Use incremental models for large tables; set is_incremental().
- Use tags and selectors for partial runs.
- Document all models in schema.yml.
- Use pre-hook/post-hook for grants and cleanup.
- Use packages from dbt Hub for common macros.
- Use dbt build (not run + test separately).
- Use exposures to document downstream consumers.""",
        policies=["DB-001"],
        optimization_rules=["Inject only when dbt_project.yml detected"],
    ),

    # ── Kafka ────────────────────────────────────────────────────────────────
    "kafka": Skill(
        id="kafka",
        name="Apache Kafka Engineering",
        description="Production Kafka patterns and reliability.",
        stacks=["kafka"],
        instructions="""## Kafka Best Practices
- Use Avro/Protobuf with Schema Registry for serialization.
- Set acks=all for critical producers.
- Use idempotent producers (enable.idempotence=true).
- Set appropriate retention and compaction policies.
- Use consumer groups with proper partition assignment.
- Handle rebalances gracefully with cooperative-sticky assignor.
- Monitor consumer lag with __consumer_offsets.
- Use transactions for exactly-once semantics.
- Set appropriate num.partitions based on throughput needs.
- Use Dead Letter Queues for poison pill messages.""",
        policies=["SEC-001"],
        optimization_rules=["Inject only when Kafka detected"],
    ),

    # ── OpenAI SDK ───────────────────────────────────────────────────────────
    "openai": Skill(
        id="openai",
        name="OpenAI SDK Engineering",
        description="Production OpenAI integration patterns.",
        stacks=["openai"],
        instructions="""## OpenAI SDK Best Practices
- Use structured outputs with response_format for reliable parsing.
- Implement exponential backoff with jitter for rate limits.
- Use tiktoken for accurate token counting before API calls.
- Set max_tokens to prevent runaway costs.
- Use system messages for persona; user messages for tasks.
- Cache responses for identical prompts (deterministic use cases).
- Use streaming for long responses to improve UX.
- Log prompt/completion pairs for debugging (redact PII).
- Use function calling for structured agent workflows.
- Monitor usage with OpenAI dashboard; set billing alerts.""",
        policies=["SEC-001", "PI-001", "PI-002"],
        optimization_rules=["Inject only when OpenAI SDK detected"],
    ),

    # ── LangChain ────────────────────────────────────────────────────────────
    "langchain": Skill(
        id="langchain",
        name="LangChain Engineering",
        description="Production LangChain patterns and anti-patterns.",
        stacks=["langchain"],
        instructions="""## LangChain Best Practices
- Use LCEL (LangChain Expression Language) over legacy chains.
- Use structured output parsers for reliable data extraction.
- Implement proper error handling for LLM failures.
- Use callbacks for logging, tracing, and monitoring.
- Use LangSmith for debugging and evaluation.
- Avoid over-abstraction; use raw LLM calls for simple tasks.
- Use retrieval-augmented generation (RAG) with vector stores.
- Set temperature=0 for deterministic tasks.
- Use chat message history with proper memory management.
- Test with mock LLMs to avoid API costs in CI.""",
        policies=["SEC-001", "PI-001"],
        optimization_rules=["Inject only when LangChain detected"],
    ),

    # ── MCP Servers ──────────────────────────────────────────────────────────
    "mcp": Skill(
        id="mcp",
        name="MCP Server Engineering",
        description="Model Context Protocol server patterns.",
        stacks=["mcp"],
        instructions="""## MCP Server Best Practices
- Define tools with clear descriptions and JSON Schema parameters.
- Validate all tool inputs before execution.
- Use proper error responses with error codes.
- Implement resource endpoints for data access.
- Use prompts for reusable conversation templates.
- Handle timeouts gracefully.
- Log all tool invocations for audit.
- Use stdio transport for local servers; SSE for remote.
- Never expose sensitive operations without auth checks.
- Test tools independently with mock contexts.""",
        policies=["SEC-001", "EX-001", "PI-001"],
        optimization_rules=["Inject only when MCP detected"],
    ),

    # ── Karpathy Engineering Philosophy ──────────────────────────────────────
    "karpathy": Skill(
        id="karpathy",
        name="Karpathy Engineering Philosophy",
        description="Simple, debuggable, deterministic engineering inspired by Andrej Karpathy.",
        stacks=["all"],
        instructions="""## Karpathy Engineering Principles
- Prefer simple code paths over clever abstractions.
- Write readable code first; optimize only with evidence.
- Minimize abstractions; each layer must justify its existence.
- Build debuggable systems with inspectable intermediate states.
- Prefer deterministic workflows; avoid non-deterministic defaults.
- Ensure transparent execution — no hidden side effects.
- Prioritize local reproducibility over cloud-first development.
- Build small, composable modules over monolithic systems.
- Make behavior explicit; avoid magic and implicit conventions.
- Avoid framework overengineering; prefer plain libraries.
- Minimize dependencies; each dependency is a liability.
- Prefer plain text configs over complex config frameworks.
- Prefer reproducible environments (containers, lock files).
- Write code that a new engineer can understand in 5 minutes.""",
        policies=[],
        optimization_rules=["Always available; low token cost"],
    ),
}


# ── Skill Registry ───────────────────────────────────────────────────────────

class SkillRegistry:
    """Manages available skills and resolves applicable ones for a stack."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = dict(BUILTIN_SKILLS)

    def register(self, skill: Skill) -> None:
        self._skills[skill.id] = skill

    def get(self, skill_id: str) -> Skill | None:
        return self._skills.get(skill_id)

    def list_all(self) -> list[Skill]:
        return list(self._skills.values())

    def resolve_for_stack(self, stack_names: list[str]) -> list[Skill]:
        """Return skills applicable to the given stack components."""
        lower = {s.lower() for s in stack_names}
        applicable: list[Skill] = []
        for skill in self._skills.values():
            if "all" in skill.stacks:
                applicable.append(skill)
            elif any(s.lower() in lower for s in skill.stacks):
                applicable.append(skill)
        return applicable

    def get_instructions(self, skill_ids: list[str]) -> str:
        """Concatenate instructions from selected skills."""
        parts: list[str] = []
        for sid in skill_ids:
            skill = self._skills.get(sid)
            if skill and skill.instructions:
                parts.append(skill.instructions)
        return "\n\n".join(parts)
