"""Tests for the Token Optimization Engine."""

import pytest

from agent_guard.governance.policies import ALL_POLICIES, get_policies_for_stack
from agent_guard.models import TokenBudget
from agent_guard.optimizer.engine import TokenOptimizer, _estimate_tokens


class TestTokenEstimation:
    def test_estimate_basic(self):
        assert _estimate_tokens("hello world") > 0

    def test_estimate_empty(self):
        assert _estimate_tokens("") == 1

    def test_estimate_proportional(self):
        short = _estimate_tokens("short text")
        long = _estimate_tokens("this is a much longer piece of text that should have more tokens")
        assert long > short


class TestTokenOptimizer:
    def test_deduplicate_rules(self):
        optimizer = TokenOptimizer()
        # Create rules with identical instructions
        from agent_guard.models import PolicyCategory, Severity
        from agent_guard.governance.policies import PolicyRule
        rules = [
            PolicyRule(id="A", name="a", description="a", severity=Severity.HIGH,
                       category=PolicyCategory.EXECUTION, instruction="Do not use eval"),
            PolicyRule(id="B", name="b", description="b", severity=Severity.MEDIUM,
                       category=PolicyCategory.EXECUTION, instruction="Do not use eval"),
            PolicyRule(id="C", name="c", description="c", severity=Severity.LOW,
                       category=PolicyCategory.EXECUTION, instruction="Different instruction"),
        ]
        unique = optimizer.deduplicate_rules(rules)
        assert len(unique) == 2

    def test_prioritize_rules(self):
        optimizer = TokenOptimizer()
        policies = get_policies_for_stack(["all"])
        prioritized = optimizer.prioritize_rules(policies)
        # Critical should come before low
        severities = [p.severity.value for p in prioritized]
        critical_idx = next((i for i, s in enumerate(severities) if s == "critical"), len(severities))
        low_idx = next((i for i, s in enumerate(severities) if s == "low"), -1)
        if low_idx >= 0 and critical_idx < len(severities):
            assert critical_idx < low_idx

    def test_compress_instructions(self):
        optimizer = TokenOptimizer()
        instructions = [
            "[CRITICAL] Never drop tables",
            "[CRITICAL] Never hardcode secrets",
            "[HIGH] Use parameterized queries",
            "[LOW] Add comments",
        ]
        compressed = optimizer.compress_instructions(instructions)
        assert "CRITICAL" in compressed
        assert "HIGH" in compressed

    def test_fit_to_budget(self):
        optimizer = TokenOptimizer(TokenBudget(input_limit=100, reserved_system=0))
        sections = [
            ("A", "x" * 100, 0),  # 25 tokens
            ("B", "x" * 200, 1),  # 50 tokens
            ("C", "x" * 400, 2),  # 100 tokens
        ]
        fitted = optimizer.fit_to_budget(sections, budget=80)
        names = [n for n, _ in fitted]
        assert "A" in names  # highest priority, should fit

    def test_optimize_produces_result(self):
        optimizer = TokenOptimizer()
        policies = get_policies_for_stack(["python"])
        result = optimizer.optimize(policies)
        assert result.original_tokens > 0
        assert result.optimized_tokens >= 0
        assert result.rules_included > 0
