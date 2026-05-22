"""Tests for the Stack Detection Engine."""

from pathlib import Path

import pytest

from agent_guard.detection.engine import StackDetector


@pytest.fixture
def python_project(tmp_path: Path) -> Path:
    """Create a minimal Python/FastAPI project structure."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test"\ndependencies = ["fastapi", "sqlalchemy", "boto3", "openai"]\n'
    )
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\npsycopg2-binary\nboto3\nopenai\n")
    (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim\n")
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: CI\non: push\n")
    return tmp_path


@pytest.fixture
def node_project(tmp_path: Path) -> Path:
    """Create a minimal Node.js/React project."""
    (tmp_path / "package.json").write_text('{"name": "test", "dependencies": {"react": "^18", "next": "^14"}}')
    (tmp_path / "tsconfig.json").write_text("{}")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.tsx").write_text("export default function App() {}")
    return tmp_path


@pytest.fixture
def terraform_project(tmp_path: Path) -> Path:
    """Create a minimal Terraform project."""
    (tmp_path / "main.tf").write_text('resource "aws_s3_bucket" "b" { bucket = "my-bucket" }')
    (tmp_path / "variables.tf").write_text('variable "region" { default = "us-east-1" }')
    return tmp_path


class TestStackDetection:
    def test_detects_python(self, python_project: Path):
        detector = StackDetector(python_project)
        stack = detector.detect()
        names = [c.name for c in stack.languages]
        assert "python" in names

    def test_detects_fastapi(self, python_project: Path):
        detector = StackDetector(python_project)
        stack = detector.detect()
        names = [c.name for c in stack.frameworks]
        assert "fastapi" in names

    def test_detects_postgresql(self, python_project: Path):
        detector = StackDetector(python_project)
        stack = detector.detect()
        names = [c.name for c in stack.databases]
        assert "postgresql" in names

    def test_detects_aws(self, python_project: Path):
        detector = StackDetector(python_project)
        stack = detector.detect()
        names = [c.name for c in stack.cloud_providers]
        assert "aws" in names

    def test_detects_openai(self, python_project: Path):
        detector = StackDetector(python_project)
        stack = detector.detect()
        names = [c.name for c in stack.sdks]
        assert "openai" in names

    def test_detects_docker(self, python_project: Path):
        detector = StackDetector(python_project)
        stack = detector.detect()
        names = [c.name for c in stack.infrastructure]
        assert "docker" in names

    def test_detects_github_actions(self, python_project: Path):
        detector = StackDetector(python_project)
        stack = detector.detect()
        names = [c.name for c in stack.ci_cd]
        assert "github_actions" in names

    def test_detects_typescript(self, node_project: Path):
        detector = StackDetector(node_project)
        stack = detector.detect()
        names = [c.name for c in stack.languages]
        assert "typescript" in names

    def test_detects_react(self, node_project: Path):
        detector = StackDetector(node_project)
        stack = detector.detect()
        names = [c.name for c in stack.frameworks]
        assert "react" in names

    def test_detects_terraform(self, terraform_project: Path):
        detector = StackDetector(terraform_project)
        stack = detector.detect()
        names = [c.name for c in stack.infrastructure]
        assert "terraform" in names

    def test_confidence_scoring(self, python_project: Path):
        detector = StackDetector(python_project)
        stack = detector.detect()
        for c in stack.all_components:
            assert 0.0 <= c.confidence <= 1.0

    def test_empty_project(self, tmp_path: Path):
        detector = StackDetector(tmp_path)
        stack = detector.detect()
        assert len(stack.all_components) == 0
