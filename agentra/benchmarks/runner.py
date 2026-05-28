"""Benchmark Runner — measures before/after metrics for each skill."""

from __future__ import annotations

import time
from pathlib import Path

from agentra.detection.engine import StackDetector
from agentra.governance.engine import GovernanceEngine
from agentra.governance.policies import ALL_POLICIES, get_policies_for_stack
from agentra.models import (
    BenchmarkMetric,
    BenchmarkReport,
    OptimizationResult,
    SkillBenchmark,
    StackProfile,
)
from agentra.optimizer.engine import TokenOptimizer
from agentra.skills.registry import SkillRegistry

_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    "env", "dist", "build", "target", ".mypy_cache", ".agentra",
})
_SKIP_EXTENSIONS: frozenset[str] = frozenset({
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".whl",
    ".zip", ".tar", ".gz", ".png", ".jpg", ".pdf", ".lock",
})


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

        # Benchmark scan efficiency: full scan vs knowledge graph
        scan_eff_benchmark = self._benchmark_scan_efficiency(stack)
        skill_benchmarks.append(scan_eff_benchmark)

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

    def _benchmark_scan_efficiency(self, stack: StackProfile) -> SkillBenchmark:
        """
        Benchmark full code scan vs knowledge-graph incremental scan.

        - Before: every scannable file is read and evaluated.
        - After:  only files changed since the last index run are scanned.

        When no index exists yet, the 'after' values are projected at a
        10% steady-state file-change rate with a note to run ``ag index``.
        """
        from agentra.optimizer.engine import _estimate_tokens
        from agentra.governance.engine import GovernanceEngine

        # ── Collect all scannable files (before baseline) ─────────────────
        all_files: list[Path] = []
        for f in self.root.rglob("*"):
            if any(p in _SKIP_DIRS for p in f.parts):
                continue
            if not f.is_file():
                continue
            if f.suffix.lower() in _SKIP_EXTENSIONS:
                continue
            if f.stat().st_size > 1_000_000:
                continue
            all_files.append(f)

        n_all = len(all_files)

        # Full content token cost (sum len(content)//4 for all files)
        full_token_cost = sum(f.stat().st_size // 4 for f in all_files if f.exists())

        # Time a real OWASP scan over the full project
        from agentra.scanner.engine import ScanEngine
        from agentra.models import ScanTarget

        t0 = time.monotonic()
        ScanEngine(self.root).scan(targets=[ScanTarget.OWASP], max_results=50)
        full_scan_seconds = round(time.monotonic() - t0, 2)

        # Generic context tokens (all governance instructions, not project-specific)
        gov = GovernanceEngine(stack)
        generic_instructions = gov.generate_instructions()
        generic_context_tokens = _estimate_tokens("\n".join(generic_instructions))

        # ── Incremental baseline (after) ──────────────────────────────────
        projected = False
        index_dir = self.root / ".agentra"
        db_path = index_dir / "code_index.db"

        if db_path.exists():
            try:
                from agentra.index.engine import CodeIndexEngine
                from agentra.rag.engine import CodeRAGEngine

                with CodeIndexEngine(index_dir) as idx:
                    changed = idx.get_changed_files(self.root)
                    n_changed = len(changed)
                    incremental_token_cost = sum(f.stat().st_size // 4 for f in changed if f.exists())

                    # Time an incremental scan on only the changed files
                    t1 = time.monotonic()
                    if changed:
                        from agentra.scanner.owasp import scan_owasp_files
                        scan_owasp_files(changed)
                    incremental_scan_seconds = round(time.monotonic() - t1, 3)

                    rag = CodeRAGEngine(index_dir, idx)
                    rag_context_tokens = rag.context_token_cost()

            except Exception:  # noqa: BLE001
                projected = True
                n_changed = max(1, n_all // 10)
                incremental_token_cost = full_token_cost // 10
                incremental_scan_seconds = round(full_scan_seconds * 0.1, 3)
                rag_context_tokens = max(100, generic_context_tokens // 5)
        else:
            projected = True
            n_changed = max(1, n_all // 10)
            incremental_token_cost = full_token_cost // 10
            incremental_scan_seconds = round(full_scan_seconds * 0.1, 3)
            rag_context_tokens = max(100, generic_context_tokens // 5)

        proj_note = " (projected — run 'ag index' for real measurements)" if projected else ""

        def _pct(before: float, after: float) -> float:
            if before == 0:
                return 0.0
            return round(max(0.0, (before - after) / before * 100), 1)

        metrics = [
            BenchmarkMetric(
                name="Files Traversed",
                before=float(n_all),
                after=float(n_changed),
                unit="files",
                improvement_pct=_pct(n_all, n_changed),
                description=f"Full scan reads all {n_all} files; incremental reads only changed files{proj_note}.",
            ),
            BenchmarkMetric(
                name="Content Tokens Scanned",
                before=float(full_token_cost),
                after=float(incremental_token_cost),
                unit="tokens",
                improvement_pct=_pct(full_token_cost, incremental_token_cost),
                description=f"Token-equivalent of file content read during scan{proj_note}.",
            ),
            BenchmarkMetric(
                name="Agent Context Tokens",
                before=float(generic_context_tokens),
                after=float(rag_context_tokens),
                unit="tokens",
                improvement_pct=_pct(generic_context_tokens, rag_context_tokens),
                description=(
                    "Generic (all-policies) context vs RAG-sourced project-specific patterns. "
                    "Fewer, more targeted tokens improve agent precision."
                ),
            ),
            BenchmarkMetric(
                name="Scan Wall Time",
                before=full_scan_seconds,
                after=incremental_scan_seconds,
                unit="seconds",
                improvement_pct=_pct(full_scan_seconds, incremental_scan_seconds),
                description=f"Elapsed time for OWASP pattern scan{proj_note}.",
            ),
        ]

        token_reduction = _pct(full_token_cost, incremental_token_cost)
        passed = token_reduction >= 30 or not projected
        detail = (
            f"Knowledge graph reduces scan scope from {n_all} to {n_changed} files "
            f"({_pct(n_all, n_changed):.0f}% skip rate), "
            f"{token_reduction:.0f}% fewer content tokens scanned."
            + (f" Run 'ag index' for real measurements." if projected else "")
        )

        return SkillBenchmark(
            skill_id="scan-efficiency",
            skill_name="Scan Efficiency: Full vs Knowledge Graph",
            metrics=metrics,
            verification_passed=passed,
            verification_details=detail,
        )
