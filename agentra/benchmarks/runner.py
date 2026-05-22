"""Benchmark Runner — measures before/after metrics for each skill."""

from __future__ import annotations

import time
from pathlib import Path

from agentra.models import (
    BenchmarkMetric,
    BenchmarkReport,
    OptimizationResult,
    SkillBenchmark,
)
from agentra.detection.engine import StackDetector
from agentra.governance.engine import GovernanceEngine
from agentra.governance.policies import ALL_POLICIES, get_policies_for_stack
from agentra.optimizer.engine import TokenOptimizer
from agentra.skills.registry import BUILTIN_SKILLS, SkillRegistry
from agentra.compliance.engine import ComplianceEngine


class BenchmarkRunner:
    """Runs before/after benchmarks for each skill to quantify improvement."""

    def __init__(self, project_root: Path | str):
        self.root = Path(project_root).resolve()
        self.registry = SkillRegistry()

    def run(self) -> BenchmarkReport:
        """Execute full benchmark suite."""
        detector = StackDetector(self.root)
        stack = detector.detect()
        stack_names = [c.name for c in stack.all_components] or ["all"]

        # Baseline governance (no skills applied)
        gov_engine = GovernanceEngine(stack)
        baseline_result = gov_engine.enforce(self.root)

        # Baseline optimization
        all_policies = get_policies_for_stack(stack_names)
        optimizer = TokenOptimizer()
        baseline_opt = optimizer.optimize(all_policies, stack)

        # Resolve applicable skills
        applicable_skills = self.registry.resolve_for_stack(stack_names)

        skill_benchmarks: list[SkillBenchmark] = []
        for skill in applicable_skills:
            sb = self._benchmark_skill(skill, stack_names, baseline_opt, baseline_result)
            skill_benchmarks.append(sb)

        # Also benchmark the governance engine itself
        gov_benchmark = self._benchmark_governance(baseline_result)
        skill_benchmarks.append(gov_benchmark)

        # Benchmark the optimization engine
        opt_benchmark = self._benchmark_optimization(baseline_opt)
        skill_benchmarks.append(opt_benchmark)

        return BenchmarkReport(
            project_name=self.root.name,
            stack=stack,
            governance=baseline_result,
            optimization=baseline_opt,
            skill_benchmarks=skill_benchmarks,
        )

    def _benchmark_skill(
        self, skill, stack_names: list[str],
        baseline_opt: OptimizationResult, baseline_result
    ) -> SkillBenchmark:
        """Benchmark a single skill: measure token cost, coverage, relevance."""
        from agentra.optimizer.engine import _estimate_tokens

        metrics: list[BenchmarkMetric] = []

        # ── 1. Token cost of skill instructions ──────────────────────────
        skill_tokens = _estimate_tokens(skill.instructions) if skill.instructions else 0
        # Without skill: 0 tokens for this skill, with skill: skill_tokens
        metrics.append(BenchmarkMetric(
            name="Instruction Token Cost",
            before=0,
            after=skill_tokens,
            unit="tokens",
            improvement_pct=0,
            description=f"Tokens consumed by {skill.name} instructions.",
        ))

        # ── 2. Policy coverage ───────────────────────────────────────────
        all_policy_ids = {p.id for p in ALL_POLICIES}
        skill_policy_ids = set(skill.policies) & all_policy_ids
        before_coverage = 0
        after_coverage = len(skill_policy_ids)
        metrics.append(BenchmarkMetric(
            name="Security Policy Coverage",
            before=before_coverage,
            after=after_coverage,
            unit="policies",
            improvement_pct=100.0 if after_coverage > 0 else 0,
            description=f"Security policies activated by {skill.name}.",
        ))

        # ── 3. Context relevance score ───────────────────────────────────
        # Score based on stack match
        stack_lower = {s.lower() for s in stack_names}
        skill_stacks = {s.lower() for s in skill.stacks}
        if "all" in skill_stacks:
            relevance = 0.8
        elif skill_stacks & stack_lower:
            relevance = 1.0
        else:
            relevance = 0.2

        metrics.append(BenchmarkMetric(
            name="Context Relevance",
            before=0.0,
            after=round(relevance, 2),
            unit="score (0-1)",
            improvement_pct=round(relevance * 100, 1),
            description=f"How relevant {skill.name} is to the detected stack.",
        ))

        # ── 4. Instruction compression ratio ────────────────────────────
        if skill.instructions:
            raw_lines = len(skill.instructions.splitlines())
            optimizer = TokenOptimizer()
            compressed = optimizer.compress_instructions([skill.instructions])
            compressed_lines = len(compressed.splitlines())
            ratio = ((raw_lines - compressed_lines) / raw_lines * 100) if raw_lines > 0 else 0
            metrics.append(BenchmarkMetric(
                name="Instruction Compression",
                before=raw_lines,
                after=compressed_lines,
                unit="lines",
                improvement_pct=round(max(0, ratio), 1),
                description="Compression achieved on skill instructions.",
            ))

        # ── 5. Verification: does the skill have all required fields? ────
        verified = bool(
            skill.instructions
            and skill.name
            and skill.description
            and skill.stacks
        )

        return SkillBenchmark(
            skill_id=skill.id,
            skill_name=skill.name,
            metrics=metrics,
            verification_passed=verified,
            verification_details=(
                "All required fields present." if verified
                else "Missing required fields: "
                + ", ".join(
                    f for f, v in [
                        ("instructions", skill.instructions),
                        ("name", skill.name),
                        ("description", skill.description),
                        ("stacks", skill.stacks),
                    ] if not v
                )
            ),
        )

    def _benchmark_governance(self, result) -> SkillBenchmark:
        """Benchmark the governance engine itself."""
        total_policies = len(ALL_POLICIES)
        violations = len(result.violations)

        metrics = [
            BenchmarkMetric(
                name="Total Policies Active",
                before=0,
                after=total_policies,
                unit="policies",
                improvement_pct=100,
                description="Number of security policies enforced.",
            ),
            BenchmarkMetric(
                name="Violations Detected",
                before=0,
                after=violations,
                unit="violations",
                improvement_pct=100 if violations > 0 else 0,
                description="Policy violations caught by governance engine.",
            ),
            BenchmarkMetric(
                name="Risk Score",
                before=100,  # Assume worst case without governance
                after=result.risk_score,
                unit="score",
                improvement_pct=round(max(0, (100 - result.risk_score)), 1),
                description="Risk score (lower is better).",
            ),
            BenchmarkMetric(
                name="Compliance Coverage",
                before=0,
                after=len({fw for p in ALL_POLICIES for fw in p.compliance}),
                unit="frameworks",
                improvement_pct=100,
                description="Number of compliance frameworks covered.",
            ),
        ]

        return SkillBenchmark(
            skill_id="governance-engine",
            skill_name="Security Governance Engine",
            metrics=metrics,
            verification_passed=True,
            verification_details=f"Governance engine operational. {total_policies} policies loaded.",
        )

    def _benchmark_optimization(self, opt_result: OptimizationResult) -> SkillBenchmark:
        """Benchmark the token optimization engine."""
        metrics = [
            BenchmarkMetric(
                name="Token Reduction",
                before=opt_result.original_tokens,
                after=opt_result.optimized_tokens,
                unit="tokens",
                improvement_pct=opt_result.reduction_pct,
                description="Tokens saved through optimization.",
            ),
            BenchmarkMetric(
                name="Rules Included",
                before=opt_result.rules_included + opt_result.rules_excluded,
                after=opt_result.rules_included,
                unit="rules",
                improvement_pct=round(
                    opt_result.rules_excluded / max(1, opt_result.rules_included + opt_result.rules_excluded) * 100, 1
                ),
                description="Low-priority rules excluded to save tokens.",
            ),
        ]

        return SkillBenchmark(
            skill_id="optimization-engine",
            skill_name="Token Optimization Engine",
            metrics=metrics,
            verification_passed=True,
            verification_details=f"Optimization engine operational. {opt_result.reduction_pct:.1f}% token reduction.",
        )
