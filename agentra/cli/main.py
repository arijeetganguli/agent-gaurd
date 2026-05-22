"""Agentra CLI — Enterprise AI Engineering Control Plane."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from agentra import __version__

app = typer.Typer(
    name="ag",
    help="Agentra — Secure, token-optimized AI engineering control plane.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _resolve_root(path: str | None) -> Path:
    return Path(path).resolve() if path else Path.cwd().resolve()


# ── ag init ──────────────────────────────────────────────────────────────────

@app.command()
def init(
    path: str = typer.Argument(None, help="Project root (default: cwd)"),
    mode: str = typer.Option("quick", "--mode", "-m", help="Onboarding mode: quick, guided, enterprise, ci"),
    agents: str = typer.Option(None, "--agents", "-a", help="Comma-separated agents: claude,cursor,copilot,aider,windsurf"),
):
    """Initialize Agentra for a project."""
    from agentra.models import AgentPlatform, OnboardingMode
    from agentra.onboarding.engine import detect_and_build_config, save_config
    from agentra.detection.engine import StackDetector
    from agentra.governance.engine import GovernanceEngine
    from agentra.optimizer.engine import TokenOptimizer
    from agentra.adapters.agents import generate_for_agents, write_agent_files

    root = _resolve_root(path)
    onboarding_mode = OnboardingMode(mode)

    with console.status("[bold green]Detecting project stack..."):
        config = detect_and_build_config(root, onboarding_mode)

    if agents:
        config.agents = [AgentPlatform(a.strip()) for a in agents.split(",")]

    # Save config
    cfg_path = save_config(config, root)
    console.print(f"[green]✓[/] Config saved to {cfg_path}")

    # Detect stack for display
    detector = StackDetector(root)
    stack = detector.detect()

    # Display detected stack
    tree = Tree("[bold]Detected Stack")
    for cat, label in [("languages", "Languages"), ("frameworks", "Frameworks"),
                       ("databases", "Databases"), ("sdks", "SDKs"), ("infrastructure", "Infra")]:
        components = getattr(stack, cat)
        if components:
            branch = tree.add(f"[cyan]{label}[/]")
            for c in components:
                conf_color = "green" if c.confidence >= 0.8 else "yellow" if c.confidence >= 0.6 else "red"
                branch.add(f"{c.name} [{conf_color}]{c.confidence:.0%}[/]")
    console.print(tree)

    # Generate agent files
    governance = GovernanceEngine(stack)
    optimizer = TokenOptimizer(config.token_budget)
    agent_files = generate_for_agents(config.agents, config, stack, governance, optimizer)
    written = write_agent_files(root, agent_files)

    console.print(f"\n[green]✓[/] Generated {len(written)} agent file(s):")
    for f in written:
        console.print(f"  • {f.relative_to(root)}")

    console.print(Panel(
        f"[bold green]Agentra initialized for {config.project_name}[/]\n"
        f"Mode: {mode} | Security: {config.security_mode.value} | Agents: {len(config.agents)}",
        title="✓ Setup Complete",
    ))


# ── ag detect ────────────────────────────────────────────────────────────────

@app.command()
def detect(path: str = typer.Argument(None, help="Project root (default: cwd)")):
    """Detect project stack and technologies."""
    from agentra.detection.engine import StackDetector

    root = _resolve_root(path)
    detector = StackDetector(root)

    with console.status("[bold green]Scanning project..."):
        stack = detector.detect()

    table = Table(title="Detected Stack", show_header=True)
    table.add_column("Category", style="cyan")
    table.add_column("Component", style="white")
    table.add_column("Confidence", justify="right")
    table.add_column("Source", style="dim")

    for cat, label in [("languages", "Language"), ("frameworks", "Framework"),
                       ("databases", "Database"), ("sdks", "SDK"),
                       ("cloud_providers", "Cloud"), ("infrastructure", "Infra"),
                       ("ci_cd", "CI/CD"), ("agents", "Agent")]:
        for c in getattr(stack, cat):
            conf_color = "green" if c.confidence >= 0.8 else "yellow" if c.confidence >= 0.6 else "red"
            table.add_row(label, c.name, f"[{conf_color}]{c.confidence:.0%}[/]", c.source[:60])

    console.print(table)

    low = stack.low_confidence
    if low:
        console.print(f"\n[yellow]⚠[/] {len(low)} component(s) with low confidence. Consider manual verification.")


# ── ag enforce ───────────────────────────────────────────────────────────────

@app.command()
def enforce(path: str = typer.Argument(None, help="Project root (default: cwd)")):
    """Run security governance checks on the project."""
    from agentra.detection.engine import StackDetector
    from agentra.governance.engine import GovernanceEngine

    root = _resolve_root(path)
    detector = StackDetector(root)
    stack = detector.detect()
    engine = GovernanceEngine(stack)

    with console.status("[bold green]Scanning for policy violations..."):
        result = engine.enforce(root)

    if result.passed:
        console.print(Panel("[bold green]All checks passed![/]", title="✓ Governance"))
    else:
        console.print(Panel(f"[bold red]Violations found![/]\n{result.explanation}", title="✗ Governance"))

    if result.violations:
        table = Table(title=f"Policy Violations ({len(result.violations)})", show_header=True)
        table.add_column("ID", style="cyan", width=8)
        table.add_column("Severity", width=10)
        table.add_column("Category", width=14)
        table.add_column("Rule", width=20)
        table.add_column("File", style="dim", width=30)
        table.add_column("Line", justify="right", width=5)

        for v in result.violations[:50]:
            sev_color = {"critical": "red", "high": "yellow", "medium": "blue", "low": "dim"}.get(v.rule.severity.value, "white")
            table.add_row(
                v.rule.id,
                f"[{sev_color}]{v.rule.severity.value}[/]",
                v.rule.category.value,
                v.rule.name,
                str(v.file_path or "")[-30:],
                str(v.line or ""),
            )

        console.print(table)
        console.print(f"\nRisk Score: [bold]{result.risk_score:.1f}[/] | Blast Radius: [bold]{result.blast_radius}[/]")


# ── ag optimize ──────────────────────────────────────────────────────────────

@app.command()
def optimize(path: str = typer.Argument(None, help="Project root (default: cwd)")):
    """Show token optimization analysis."""
    from agentra.detection.engine import StackDetector
    from agentra.governance.policies import get_policies_for_stack
    from agentra.optimizer.engine import TokenOptimizer

    root = _resolve_root(path)
    detector = StackDetector(root)
    stack = detector.detect()

    stack_names = [c.name for c in stack.all_components] or ["all"]
    policies = get_policies_for_stack(stack_names)
    optimizer = TokenOptimizer()
    result = optimizer.optimize(policies, stack)

    table = Table(title="Token Optimization", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Original tokens", str(result.original_tokens))
    table.add_row("Optimized tokens", str(result.optimized_tokens))
    table.add_row("Reduction", f"[green]{result.reduction_pct:.1f}%[/]")
    table.add_row("Rules included", str(result.rules_included))
    table.add_row("Rules excluded", str(result.rules_excluded))

    console.print(table)


# ── ag audit ─────────────────────────────────────────────────────────────────

@app.command()
def audit(path: str = typer.Argument(None, help="Project root (default: cwd)"), count: int = typer.Option(20, "--count", "-n")):
    """View recent audit log entries."""
    from agentra.telemetry.audit import AuditLog

    root = _resolve_root(path)
    log = AuditLog(root / ".agentra" / "audit")
    entries = log.load_recent(count)

    if not entries:
        console.print("[dim]No audit entries found.[/]")
        return

    table = Table(title=f"Audit Log (last {count})", show_header=True)
    table.add_column("Timestamp", width=20)
    table.add_column("Action", style="cyan", width=20)
    table.add_column("Risk", width=10)
    table.add_column("Details", width=50)

    for e in entries:
        table.add_row(
            str(e.get("timestamp", ""))[:19],
            e.get("action", ""),
            e.get("risk_level", ""),
            str(e.get("details", ""))[:50],
        )

    console.print(table)


# ── ag doctor ────────────────────────────────────────────────────────────────

@app.command()
def doctor(path: str = typer.Argument(None, help="Project root (default: cwd)")):
    """Diagnose Agentra setup health."""
    from agentra.onboarding.engine import load_config, CONFIG_FILE

    root = _resolve_root(path)

    checks: list[tuple[str, bool, str]] = []

    # Config file
    cfg_exists = (root / CONFIG_FILE).exists()
    checks.append(("Config file", cfg_exists, CONFIG_FILE))

    # Agent files
    for f in ["AGENTS.md", "CLAUDE.md", ".cursorrules", ".github/copilot-instructions.md"]:
        checks.append((f"Agent file: {f}", (root / f).exists(), f))

    # .gitignore
    gitignore = root / ".gitignore"
    checks.append((".gitignore exists", gitignore.exists(), ".gitignore"))

    # Config validity
    if cfg_exists:
        config = load_config(root)
        checks.append(("Config parseable", config is not None, "Config loaded"))
    else:
        checks.append(("Config parseable", False, "No config file"))

    table = Table(title="Agentra Health Check", show_header=True)
    table.add_column("Check", style="cyan")
    table.add_column("Status", width=8)
    table.add_column("Details", style="dim")

    for name, ok, detail in checks:
        status = "[green]✓[/]" if ok else "[red]✗[/]"
        table.add_row(name, status, detail)

    console.print(table)

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    console.print(f"\n{passed}/{total} checks passed")


# ── ag explain ───────────────────────────────────────────────────────────────

@app.command()
def explain(rule_id: str = typer.Argument(..., help="Policy rule ID (e.g. DB-001)")):
    """Explain a specific policy rule."""
    from agentra.governance.policies import ALL_POLICIES

    rule = next((p for p in ALL_POLICIES if p.id == rule_id), None)
    if not rule:
        console.print(f"[red]Rule {rule_id} not found.[/]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold]{rule.name}[/] ({rule.id})\n\n"
        f"[cyan]Severity:[/] {rule.severity.value}\n"
        f"[cyan]Category:[/] {rule.category.value}\n"
        f"[cyan]Description:[/] {rule.description}\n\n"
        f"[cyan]Instruction:[/]\n{rule.instruction}\n\n"
        f"[cyan]Pattern:[/] {rule.pattern or 'N/A'}\n"
        f"[cyan]Stacks:[/] {', '.join(rule.stacks)}\n"
        f"[cyan]Compliance:[/] {', '.join(c.value for c in rule.compliance) or 'None'}\n"
        f"[cyan]Token cost:[/] {rule.token_cost}",
        title=f"Policy Rule: {rule_id}",
    ))


# ── ag simulate ──────────────────────────────────────────────────────────────

@app.command()
def simulate(command: str = typer.Argument(..., help="Command to simulate")):
    """Dry-run a command through the execution safety engine."""
    from agentra.execution.engine import ExecutionEngine
    from agentra.models import ExecutionRequest

    engine = ExecutionEngine()
    request = ExecutionRequest(command=command, dry_run=True)
    result = engine.dry_run(request)

    if result.approved:
        console.print(Panel(f"[green]SAFE[/]\n{result.stdout}", title="Simulation Result"))
    else:
        console.print(Panel(f"[red]BLOCKED[/]\n{result.stderr}", title="Simulation Result"))


# ── ag validate ──────────────────────────────────────────────────────────────

@app.command()
def validate(path: str = typer.Argument(None, help="Project root (default: cwd)")):
    """Validate project against all governance, compliance, and optimization checks."""
    from agentra.detection.engine import StackDetector
    from agentra.governance.engine import GovernanceEngine
    from agentra.compliance.engine import ComplianceEngine
    from agentra.optimizer.engine import TokenOptimizer
    from agentra.governance.policies import get_policies_for_stack

    root = _resolve_root(path)
    detector = StackDetector(root)
    stack = detector.detect()

    gov = GovernanceEngine(stack)
    result = gov.enforce(root)

    comp = ComplianceEngine()
    compliance_report = comp.generate_compliance_report(result)

    stack_names = [c.name for c in stack.all_components] or ["all"]
    policies = get_policies_for_stack(stack_names)
    opt = TokenOptimizer()
    opt_result = opt.optimize(policies, stack)

    console.print(Panel(
        f"Governance: {'[green]PASS[/]' if result.passed else '[red]FAIL[/]'}\n"
        f"Violations: {len(result.violations)}\n"
        f"Risk Score: {result.risk_score:.1f}\n"
        f"Token Optimization: {opt_result.reduction_pct:.1f}% reduction\n"
        f"Rules Active: {opt_result.rules_included}",
        title="Validation Summary",
    ))


# ── ag benchmark ─────────────────────────────────────────────────────────────

@app.command()
def benchmark(
    path: str = typer.Argument(None, help="Project root (default: cwd)"),
    output: str = typer.Option(".agentra/reports", "--output", "-o", help="Output directory for reports"),
):
    """Run skill benchmarks and generate metric reports."""
    from agentra.benchmarks.runner import BenchmarkRunner
    from agentra.renderers.markdown import MarkdownRenderer
    from agentra.renderers.html import HtmlRenderer

    root = _resolve_root(path)
    output_dir = root / output
    output_dir.mkdir(parents=True, exist_ok=True)

    runner = BenchmarkRunner(root)

    with console.status("[bold green]Running benchmarks..."):
        report = runner.run()

    # Generate reports
    md_renderer = MarkdownRenderer()
    html_renderer = HtmlRenderer()

    md_path = output_dir / "benchmark-report.md"
    html_path = output_dir / "benchmark-report.html"

    md_renderer.render(report, md_path)
    html_renderer.render(report, html_path)

    console.print(f"[green]✓[/] Benchmark report (MD):   {md_path}")
    console.print(f"[green]✓[/] Benchmark report (HTML): {html_path}")

    # Summary table
    table = Table(title="Skill Benchmarks Summary", show_header=True)
    table.add_column("Skill", style="cyan")
    table.add_column("Verified", width=10)
    table.add_column("Metrics", justify="right")
    table.add_column("Best Improvement", justify="right")

    for sb in report.skill_benchmarks:
        verified = "[green]✓[/]" if sb.verification_passed else "[red]✗[/]"
        best = max((m.improvement_pct for m in sb.metrics), default=0)
        table.add_row(sb.skill_name, verified, str(len(sb.metrics)), f"{best:.1f}%")

    console.print(table)


# ── ag version ───────────────────────────────────────────────────────────────

@app.command()
def version():
    """Show Agentra version."""
    console.print(f"Agentra v{__version__}")


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
