"""CI template generator — GitHub Actions and GitLab CI snippets for ag scan."""

from __future__ import annotations


def generate_github_actions_step() -> str:
    """Return a GitHub Actions workflow YAML with Agentra security scanning."""
    return """\
name: Agentra Security Scan

on:
  push:
    branches: ["main", "master", "develop"]
  pull_request:
    branches: ["main", "master", "develop"]

jobs:
  security-scan:
    name: Agentra Vulnerability Scan
    runs-on: ubuntu-latest
    permissions:
      contents: read

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Agentra
        run: pip install agentra

      - name: Install optional SAST tools
        run: pip install bandit pip-audit
        continue-on-error: true

      - name: Run Agentra security scan
        run: ag scan --format json
        # Exit 1 if CRITICAL vulnerabilities are found

      - name: Run governance checks
        run: ag enforce
        # Reports policy violations

      - name: Run full validation
        run: ag validate
"""


def generate_gitlab_ci_job() -> str:
    """Return a GitLab CI job YAML for Agentra security scanning."""
    return """\
# Agentra Security Scanning — add this to your .gitlab-ci.yml

agentra-security-scan:
  stage: test
  image: python:3.11-slim
  before_script:
    - pip install agentra bandit pip-audit --quiet
  script:
    - ag scan --format json
    - ag enforce
    - ag validate
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  allow_failure: false
  artifacts:
    when: always
    reports:
      # Optionally export scan results as JUnit XML
      # junit: agentra-scan-results.xml
      paths: []
    expire_in: 7 days
"""


def generate_pre_build_ci_check() -> str:
    """Return a shell script snippet for pre-build security gating in any CI."""
    return """\
#!/usr/bin/env bash
# Agentra pre-build security gate
# Add this before your build command in any CI system
set -euo pipefail

echo "=== Agentra Security Scan ==="
pip install agentra bandit pip-audit --quiet

# Run vulnerability scan — exits 1 if CRITICAL findings
ag scan

# Run governance checks
ag enforce

echo "=== Security gate passed. Proceeding with build. ==="
"""
