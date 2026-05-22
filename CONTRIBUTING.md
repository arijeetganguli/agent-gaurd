# Contributing to Agentra

Thank you for your interest in contributing to Agentra!

## Getting Started

```bash
# Clone the repo
git clone git@github.com:arijeetganguli/agent-gaurd.git
cd agent-gaurd

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check agentra/
```

## Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes
4. Run tests (`pytest tests/ -v`)
5. Commit with a descriptive message
6. Push to your fork and open a Pull Request

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `test:` — adding or updating tests
- `refactor:` — code change that neither fixes a bug nor adds a feature
- `chore:` — maintenance tasks

## Adding a New Security Policy

1. Add the `PolicyRule` to `agentra/governance/policies.py`
2. Include: `id`, `name`, `severity`, `category`, `pattern` (regex), `instruction`, `stacks`, `compliance`, `token_cost`
3. Add tests in `tests/test_governance.py`
4. Run `ag explain <RULE_ID>` to verify it renders correctly

## Adding a New Skill

1. Add the skill dict to `BUILTIN_SKILLS` in `agentra/skills/registry.py`
2. Include: `id`, `name`, `description`, `stacks`, `policies`, `instructions`
3. Add tests in `tests/test_skills.py`
4. Run `ag benchmark` to verify it benchmarks correctly

## Adding a New Agent Adapter

1. Create an adapter class in `agentra/adapters/agents.py` extending the base pattern
2. Register it in `ADAPTER_REGISTRY`
3. Add the corresponding `AgentPlatform` enum value in `models.py` if needed
4. Add tests in `tests/test_adapters.py`

## Code Style

- Python 3.11+
- Use type annotations
- Follow existing patterns in the codebase
- Lint with `ruff`
- Type check with `mypy`

## Reporting Bugs

Open a [GitHub Issue](https://github.com/arijeetganguli/agent-gaurd/issues/new?template=bug_report.yml) with:

- Steps to reproduce
- Expected behavior
- Actual behavior
- Python version and OS

## Questions

Open a [Discussion](https://github.com/arijeetganguli/agent-gaurd/discussions) for general questions.
