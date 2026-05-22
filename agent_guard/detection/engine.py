"""Stack Detection Engine — automatically identifies project technologies."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agent_guard.models import DetectedComponent, StackProfile


# ── Detector registry ────────────────────────────────────────────────────────

class _DetectorRule:
    """A single detection rule for a technology component."""

    __slots__ = ("name", "category", "files", "patterns", "content_patterns")

    def __init__(
        self,
        name: str,
        category: str,
        files: list[str] | None = None,
        patterns: list[str] | None = None,
        content_patterns: dict[str, str] | None = None,
    ):
        self.name = name
        self.category = category
        self.files = files or []
        self.patterns = patterns or []
        self.content_patterns = content_patterns or {}


# fmt: off
_RULES: list[_DetectorRule] = [
    # ── Languages ──
    _DetectorRule("python",     "languages", files=["pyproject.toml","setup.py","setup.cfg","Pipfile","requirements.txt","poetry.lock"], patterns=[r"\.py$"]),
    _DetectorRule("javascript", "languages", files=["package.json"], patterns=[r"\.js$", r"\.mjs$"]),
    _DetectorRule("typescript", "languages", files=["tsconfig.json"], patterns=[r"\.ts$", r"\.tsx$"]),
    _DetectorRule("java",       "languages", files=["pom.xml","build.gradle","build.gradle.kts"], patterns=[r"\.java$"]),
    _DetectorRule("go",         "languages", files=["go.mod","go.sum"], patterns=[r"\.go$"]),
    _DetectorRule("rust",       "languages", files=["Cargo.toml","Cargo.lock"], patterns=[r"\.rs$"]),
    _DetectorRule("csharp",     "languages", files=[], patterns=[r"\.csproj$", r"\.sln$", r"\.cs$"]),
    # ── Frameworks ──
    _DetectorRule("fastapi",    "frameworks", content_patterns={"requirements.txt": r"fastapi", "pyproject.toml": r"fastapi", "Pipfile": r"fastapi"}),
    _DetectorRule("django",     "frameworks", files=["manage.py"], content_patterns={"requirements.txt": r"django", "pyproject.toml": r"django"}),
    _DetectorRule("flask",      "frameworks", content_patterns={"requirements.txt": r"flask", "pyproject.toml": r"flask"}),
    _DetectorRule("react",      "frameworks", content_patterns={"package.json": r'"react"'}),
    _DetectorRule("vue",        "frameworks", content_patterns={"package.json": r'"vue"'}),
    _DetectorRule("next.js",    "frameworks", content_patterns={"package.json": r'"next"'}),
    _DetectorRule("express",    "frameworks", content_patterns={"package.json": r'"express"'}),
    _DetectorRule("spring",     "frameworks", content_patterns={"pom.xml": r"spring-boot", "build.gradle": r"spring-boot"}),
    # ── Data / Infra ──
    _DetectorRule("spark",      "frameworks", content_patterns={"requirements.txt": r"pyspark", "pyproject.toml": r"pyspark"}),
    _DetectorRule("airflow",    "frameworks", files=["dags/"], content_patterns={"requirements.txt": r"apache-airflow", "pyproject.toml": r"apache-airflow"}),
    _DetectorRule("dbt",        "frameworks", files=["dbt_project.yml"]),
    _DetectorRule("kafka",      "infrastructure", content_patterns={"requirements.txt": r"kafka", "pyproject.toml": r"kafka", "docker-compose.yml": r"kafka"}),
    # ── Databases ──
    _DetectorRule("postgresql",  "databases", content_patterns={"requirements.txt": r"psycopg|asyncpg|sqlalchemy", "pyproject.toml": r"psycopg|asyncpg", "docker-compose.yml": r"postgres"}),
    _DetectorRule("mysql",       "databases", content_patterns={"requirements.txt": r"mysql|pymysql", "docker-compose.yml": r"mysql"}),
    _DetectorRule("mongodb",     "databases", content_patterns={"requirements.txt": r"pymongo|motor", "docker-compose.yml": r"mongo"}),
    _DetectorRule("redis",       "databases", content_patterns={"requirements.txt": r"redis", "docker-compose.yml": r"redis"}),
    _DetectorRule("snowflake",   "databases", content_patterns={"requirements.txt": r"snowflake", "pyproject.toml": r"snowflake"}),
    # ── Cloud ──
    _DetectorRule("aws",        "cloud_providers", files=["cdk.json","samconfig.toml"], content_patterns={"requirements.txt": r"boto3|aws-cdk", "pyproject.toml": r"boto3"}),
    _DetectorRule("azure",      "cloud_providers", content_patterns={"requirements.txt": r"azure", "pyproject.toml": r"azure"}),
    _DetectorRule("gcp",        "cloud_providers", content_patterns={"requirements.txt": r"google-cloud", "pyproject.toml": r"google-cloud"}),
    # ── Infrastructure ──
    _DetectorRule("terraform",   "infrastructure", files=[], patterns=[r"\.tf$"]),
    _DetectorRule("kubernetes",  "infrastructure", files=[], patterns=[r"\.ya?ml$"], content_patterns={"": r"apiVersion:\s+"}),
    _DetectorRule("docker",      "infrastructure", files=["Dockerfile","docker-compose.yml","docker-compose.yaml",".dockerignore"]),
    # ── CI/CD ──
    _DetectorRule("github_actions", "ci_cd", files=[".github/workflows/"], patterns=[r"\.github/workflows/.*\.ya?ml$"]),
    _DetectorRule("gitlab_ci",     "ci_cd", files=[".gitlab-ci.yml"]),
    _DetectorRule("jenkins",       "ci_cd", files=["Jenkinsfile"]),
    _DetectorRule("circleci",      "ci_cd", files=[".circleci/config.yml"]),
    # ── SDKs ──
    _DetectorRule("openai",     "sdks", content_patterns={"requirements.txt": r"openai", "pyproject.toml": r"openai", "package.json": r'"openai"'}),
    _DetectorRule("anthropic",  "sdks", content_patterns={"requirements.txt": r"anthropic", "pyproject.toml": r"anthropic"}),
    _DetectorRule("langchain",  "sdks", content_patterns={"requirements.txt": r"langchain", "pyproject.toml": r"langchain"}),
    _DetectorRule("databricks", "sdks", content_patterns={"requirements.txt": r"databricks", "pyproject.toml": r"databricks"}),
    # ── Agent platforms ──
    _DetectorRule("claude",    "agents", files=["CLAUDE.md",".claude/"]),
    _DetectorRule("cursor",    "agents", files=[".cursor/",".cursorrules"]),
    _DetectorRule("copilot",   "agents", files=[".github/copilot-instructions.md"]),
    _DetectorRule("aider",     "agents", files=[".aider.conf.yml",".aiderignore"]),
    _DetectorRule("continue",  "agents", files=[".continue/config.json"]),
    _DetectorRule("windsurf",  "agents", files=[".windsurf/",".windsurfrules"]),
    _DetectorRule("mcp",       "agents", files=["mcp.json",".mcp.json"], content_patterns={"pyproject.toml": r"mcp", "requirements.txt": r"mcp"}),
]
# fmt: on


# ── File cache ───────────────────────────────────────────────────────────────

def _list_files(root: Path, max_depth: int = 4) -> list[Path]:
    """Return project files up to *max_depth*, skipping common junk dirs."""
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build", ".eggs"}
    results: list[Path] = []
    for child in root.rglob("*"):
        if any(part in skip for part in child.parts):
            continue
        rel = child.relative_to(root)
        if len(rel.parts) > max_depth:
            continue
        results.append(rel)
    return results


def _read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, PermissionError):
        return ""


# ── Engine ───────────────────────────────────────────────────────────────────

class StackDetector:
    """Detects project stack by scanning files, manifests, and content."""

    def __init__(self, project_root: Path | str):
        self.root = Path(project_root).resolve()

    def detect(self) -> StackProfile:
        files = _list_files(self.root)
        file_names = {f.name for f in files}
        file_str_set = {str(f).replace("\\", "/") for f in files}
        content_cache: dict[str, str] = {}

        profile = StackProfile()

        for rule in _RULES:
            confidence = 0.0
            sources: list[str] = []

            # 1. Check for sentinel files / dirs
            for sentinel in rule.files:
                if sentinel.endswith("/"):
                    # directory check
                    dirname = sentinel.rstrip("/")
                    if any(s.startswith(dirname + "/") or s == dirname for s in file_str_set):
                        confidence = max(confidence, 0.8)
                        sources.append(sentinel)
                elif sentinel in file_names:
                    confidence = max(confidence, 0.8)
                    sources.append(sentinel)

            # 2. Check filename patterns
            for pat in rule.patterns:
                matches = [f for f in file_str_set if re.search(pat, str(f))]
                if matches:
                    # More matches → higher confidence
                    c = min(0.5 + 0.1 * len(matches), 0.9)
                    confidence = max(confidence, c)
                    sources.append(f"pattern:{pat}({len(matches)} files)")

            # 3. Check content patterns
            for filename, cpat in rule.content_patterns.items():
                if filename and filename not in file_names:
                    continue
                target_files = [filename] if filename else [str(f) for f in files]
                for tf in target_files[:5]:  # limit scanning
                    fpath = self.root / tf
                    if fpath in content_cache:
                        text = content_cache[fpath]
                    elif fpath.is_file():
                        text = _read_text_safe(fpath)
                        content_cache[fpath] = text
                    else:
                        continue
                    if re.search(cpat, text, re.IGNORECASE):
                        confidence = max(confidence, 0.85)
                        sources.append(f"{tf}:{cpat}")
                        break

            if confidence < 0.3:
                continue

            comp = DetectedComponent(
                name=rule.name,
                confidence=round(confidence, 2),
                source="; ".join(sources[:3]),
            )

            target = getattr(profile, rule.category)
            target.append(comp)

        return profile
