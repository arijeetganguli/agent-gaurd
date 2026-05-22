"""Token Optimization Engine — minimize context, maximize relevance."""

from __future__ import annotations

import re
from collections import defaultdict

from agentra.governance.policies import PolicyRule
from agentra.models import OptimizationResult, StackProfile, TokenBudget


def _estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


class TokenOptimizer:
    """Optimizes prompt context for token budget compliance."""

    def __init__(self, budget: TokenBudget | None = None):
        self.budget = budget or TokenBudget()

    def deduplicate_rules(self, rules: list[PolicyRule]) -> list[PolicyRule]:
        """Remove rules with identical instructions."""
        seen: set[str] = set()
        unique: list[PolicyRule] = []
        for r in rules:
            key = r.instruction.strip().lower()
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def prioritize_rules(self, rules: list[PolicyRule], stack: StackProfile | None = None) -> list[PolicyRule]:
        """Sort rules by severity (critical first), then by stack relevance."""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        stack_names = {c.name.lower() for c in stack.all_components} if stack else set()

        def sort_key(r: PolicyRule) -> tuple[int, int]:
            sev = severity_order.get(r.severity.value, 5)
            # Boost stack-specific rules
            relevance = 0 if any(s.lower() in stack_names for s in r.stacks) else 1
            return (sev, relevance)

        return sorted(rules, key=sort_key)

    def compress_instructions(self, instructions: list[str]) -> str:
        """Compress a list of instructions into a single block, removing redundancy."""
        if not instructions:
            return ""

        # Group by prefix pattern
        groups: dict[str, list[str]] = defaultdict(list)
        for inst in instructions:
            # Extract severity tag if present
            match = re.match(r"\[(\w+)\]\s*(.*)", inst)
            if match:
                groups[match.group(1)].append(match.group(2))
            else:
                groups["GENERAL"].append(inst)

        lines: list[str] = []
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "GENERAL"]:
            if severity not in groups:
                continue
            lines.append(f"\n## {severity} Rules")
            for item in groups[severity]:
                # Shorten long instructions
                if len(item) > 150:
                    item = item[:147] + "..."
                lines.append(f"- {item}")

        return "\n".join(lines)

    def fit_to_budget(self, sections: list[tuple[str, str, int]], budget: int | None = None) -> list[tuple[str, str]]:
        """
        Given sections as (name, content, priority), return those that fit in budget.
        Lower priority number = higher importance.
        """
        limit = budget or (self.budget.input_limit - self.budget.reserved_system)
        sorted_sections = sorted(sections, key=lambda x: x[2])

        included: list[tuple[str, str]] = []
        used = 0
        for name, content, _ in sorted_sections:
            tokens = _estimate_tokens(content)
            if used + tokens <= limit:
                included.append((name, content))
                used += tokens

        return included

    def optimize(
        self,
        rules: list[PolicyRule],
        stack: StackProfile | None = None,
        extra_context: dict[str, str] | None = None,
    ) -> OptimizationResult:
        """Full optimization pipeline: dedupe, prioritize, compress, budget-fit."""
        original_tokens = sum(_estimate_tokens(r.instruction) for r in rules)

        # Step 1: Deduplicate
        unique_rules = self.deduplicate_rules(rules)

        # Step 2: Prioritize
        prioritized = self.prioritize_rules(unique_rules, stack)

        # Step 3: Build sections
        sections: list[tuple[str, str, int]] = []
        severity_priority = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

        for r in prioritized:
            if r.instruction:
                pri = severity_priority.get(r.severity.value, 5)
                sections.append((r.id, r.instruction, pri))

        if extra_context:
            for name, content in extra_context.items():
                sections.append((name, content, 3))

        # Step 4: Fit to budget
        fitted = self.fit_to_budget(sections)

        optimized_tokens = sum(_estimate_tokens(content) for _, content in fitted)

        reduction = ((original_tokens - optimized_tokens) / original_tokens * 100) if original_tokens > 0 else 0

        return OptimizationResult(
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            reduction_pct=round(max(0, reduction), 1),
            rules_included=len(fitted),
            rules_excluded=max(0, len(sections) - len(fitted)),
            context_sections=[name for name, _ in fitted],
        )
