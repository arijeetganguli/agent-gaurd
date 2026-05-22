.PHONY: install dev test lint typecheck format clean build benchmark docker

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --tb=short --cov=agent_guard --cov-report=term-missing

lint:
	ruff check agent_guard/ tests/

format:
	ruff format agent_guard/ tests/

typecheck:
	mypy agent_guard/

benchmark:
	ag benchmark .

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build:
	python -m build

docker:
	docker build -t agent-guard:latest .
