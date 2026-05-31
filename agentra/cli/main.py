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
    agents: str = typer.Option(None, "--agents", "-a", help="Comma-separated agents: claude,cursor,copilot,aider,windsurf"),  # noqa: E501
    model: str = typer.Option("auto", "--model", "-M", help="Model for all agents (e.g. claude-sonnet-4-6, gpt-5.5) or 'auto'"),  # noqa: E501
):
    """Initialize Agentra for a project."""
    from agentra.adapters.agents import generate_for_agents, write_agent_files
    from agentra.detection.engine import StackDetector
    from agentra.governance.engine import GovernanceEngine
    from agentra.models import AGENT_DEFAULT_MODELS, AgentPlatform, OnboardingMode
    from agentra.onboarding.engine import detect_and_build_config, save_config
    from agentra.optimizer.engine import TokenOptimizer

    root = _resolve_root(path)
    onboarding_mode = OnboardingMode(mode)

    with console.status("[bold green]Detecting project stack..."):
        config = detect_and_build_config(root, onboarding_mode)

    if agents:
        config.agents = [AgentPlatform(a.strip()) for a in agents.split(",")]
        # Seed model preferences for any newly specified agents
        for ag in config.agents:
            if ag.value not in config.model_preferences:
                config.model_preferences[ag.value] = AGENT_DEFAULT_MODELS.get(ag.value, "")

    # Apply --model override (replaces auto-selected models for every agent)
    if model and model != "auto":
        for ag in config.agents:
            config.model_preferences[ag.value] = model

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

    # Show model preferences
    if config.model_preferences:
        source_label = f"--model {model}" if model != "auto" else "auto-selected"
        model_table = Table(title="Model Preferences", show_header=True)
        model_table.add_column("Agent", style="cyan")
        model_table.add_column("Model")
        model_table.add_column("Source", style="dim")
        for ag_val, mdl in config.model_preferences.items():
            if mdl:
                model_table.add_row(ag_val, f"[bold]{mdl}[/]", source_label)
        console.print(model_table)
        console.print("[dim]Change a model: ag model set <agent> <model>[/]\n")

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
            sev_color = {"critical": "red", "high": "yellow", "medium": "blue", "low": "dim"}.get(v.rule.severity.value, "white")  # noqa: E501
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
def audit(path: str = typer.Argument(None, help="Project root (default: cwd)"), count: int = typer.Option(20, "--count", "-n")):  # noqa: E501
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
    from agentra.onboarding.engine import CONFIG_FILE, load_config

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
    from agentra.governance.policies import get_policies_for_stack
    from agentra.optimizer.engine import TokenOptimizer

    root = _resolve_root(path)
    detector = StackDetector(root)
    stack = detector.detect()

    gov = GovernanceEngine(stack)
    result = gov.enforce(root)

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
    from agentra.renderers.html import HtmlRenderer
    from agentra.renderers.markdown import MarkdownRenderer

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


# ── ag scan ──────────────────────────────────────────────────────────────────

@app.command()
def scan(
    path: str = typer.Argument(None, help="Project root (default: cwd)"),
    sast: bool = typer.Option(False, "--sast", help="Run SAST scan (bandit/semgrep)"),
    deps: bool = typer.Option(False, "--deps", help="Run dependency vulnerability scan"),
    owasp: bool = typer.Option(False, "--owasp", help="Run OWASP Top 10 pattern scan"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json"),
    incremental: bool = typer.Option(True, "--incremental/--no-incremental", help="Only scan files changed since last index (requires ag index)"),
):
    """Scan for security vulnerabilities (OWASP Top 10, SAST, dependency CVEs)."""
    import json as json_mod
    from agentra.models import ScanTarget
    from agentra.scanner.engine import ScanEngine

    root = _resolve_root(path)

    # Determine targets
    targets: list[ScanTarget] = []
    if sast:
        targets.append(ScanTarget.SAST)
    if deps:
        targets.append(ScanTarget.DEPS)
    if owasp:
        targets.append(ScanTarget.OWASP)
    if not targets:
        targets = [ScanTarget.ALL]

    # Resolve incremental file list if requested
    file_list = None
    if incremental:
        index_dir = root / ".agentra"
        db_path = index_dir / "code_index.db"
        if db_path.exists():
            try:
                from agentra.index.engine import CodeIndexEngine
                with CodeIndexEngine(index_dir) as idx:
                    changed = idx.get_changed_files(root)
                if changed:
                    file_list = changed
                    console.print(f"[dim]Incremental scan: {len(changed)} changed file(s)[/]")
                else:
                    console.print("[dim]Incremental scan: no changed files detected — skipping scan[/]")
                    return
            except Exception:  # noqa: BLE001
                pass  # fall back to full scan silently

    engine = ScanEngine(root)

    with console.status("[bold green]Running vulnerability scan..."):
        report = engine.scan(targets=targets, file_list=file_list)

    if output_format == "json":
        print(json_mod.dumps(
            {
                "passed": report.passed,
                "risk_score": report.risk_score,
                "summary": report.summary,
                "findings": [
                    {
                        "tool": r.tool,
                        "severity": r.severity.value,
                        "file": r.file_path,
                        "line": r.line,
                        "rule_id": r.rule_id,
                        "owasp": r.owasp_category,
                        "finding": r.finding,
                        "cve": r.cve_id,
                        "fix_available": r.fix_available,
                        "fix": r.fix_description,
                    }
                    for r in report.results
                ],
                "tools_available": report.tools_available,
                "tools_missing": report.tools_missing,
            },
            indent=2,
        ))
    else:
        # Table output
        status_str = "[green]PASSED[/]" if report.passed else "[red]FAILED — CRITICAL FINDINGS[/]"
        console.print(Panel(
            f"{status_str}\n"
            f"Risk Score: [bold]{report.risk_score:.1f}[/] | "
            f"Findings: [bold]{len(report.results)}[/] | "
            f"Duration: {report.scan_duration_ms}ms\n"
            f"{report.summary}",
            title="Vulnerability Scan",
        ))

        if report.results:
            table = Table(title=f"Findings ({len(report.results)})", show_header=True)
            table.add_column("Severity", width=10)
            table.add_column("Rule", width=10)
            table.add_column("OWASP", width=30)
            table.add_column("File", style="dim", width=35)
            table.add_column("Line", justify="right", width=5)
            table.add_column("Finding", width=50)

            sev_colors = {
                "critical": "red", "high": "yellow",
                "medium": "blue", "low": "dim", "info": "dim",
            }
            for r in report.results[:100]:
                color = sev_colors.get(r.severity.value, "white")
                table.add_row(
                    f"[{color}]{r.severity.value}[/]",
                    r.rule_id or r.tool,
                    r.owasp_category[:28],
                    str(r.file_path or "")[-33:],
                    str(r.line or ""),
                    r.finding[:48],
                )

            console.print(table)

        if report.tools_missing:
            console.print(
                f"\n[yellow]Tip:[/] Install [bold]{', '.join(report.tools_missing)}[/] for deeper scanning:\n"
                f"  pip install {' '.join(report.tools_missing)}"
            )

    if not report.passed:
        raise typer.Exit(1)


# ── ag prebuild ──────────────────────────────────────────────────────────────

@app.command()
def prebuild(
    command: str = typer.Argument(..., help="Build command to run after security gate"),
    path: str = typer.Option(None, "--path", "-p", help="Project root (default: cwd)"),
    block_on_high: bool = typer.Option(False, "--block-high", help="Also block on HIGH findings (default: only CRITICAL)"),
):
    """Security gate: scan for vulnerabilities then run the build command if clean."""
    import subprocess
    from agentra.models import ScanTarget, Severity
    from agentra.scanner.engine import ScanEngine

    root = _resolve_root(path)
    engine = ScanEngine(root)

    console.print(f"[bold]Pre-build security gate[/] for: [cyan]{command}[/]")

    with console.status("[bold green]Running pre-build vulnerability scan..."):
        report = engine.scan(targets=[ScanTarget.ALL])

    block_severities = [Severity.CRITICAL]
    if block_on_high:
        block_severities.append(Severity.HIGH)

    gate_passed = engine.gate(report, block_on=block_severities)

    # Show critical/high findings
    critical_high = [r for r in report.results if r.severity in block_severities]
    if critical_high:
        table = Table(title="Blocking Findings", show_header=True)
        table.add_column("Severity", width=10)
        table.add_column("Rule", width=10)
        table.add_column("File", style="dim", width=40)
        table.add_column("Finding", width=60)
        for r in critical_high[:20]:
            color = "red" if r.severity.value == "critical" else "yellow"
            table.add_row(
                f"[{color}]{r.severity.value}[/]",
                r.rule_id or r.tool,
                str(r.file_path or "")[-38:],
                r.finding[:58],
            )
        console.print(table)

    if not gate_passed:
        console.print(Panel(
            f"[bold red]Build blocked.[/] {len(critical_high)} blocking finding(s) detected.\n"
            "Fix vulnerabilities and re-run, or use [bold]ag enforce[/] for details.",
            title="✗ Security Gate FAILED",
        ))
        raise typer.Exit(1)

    warn_count = sum(1 for r in report.results if r.severity.value == "high") if not block_on_high else 0
    if warn_count:
        console.print(f"[yellow]⚠[/] {warn_count} HIGH finding(s) — review recommended but build proceeds.")

    console.print(f"[green]✓ Security gate passed.[/] Running: [cyan]{command}[/]\n")

    try:
        result = subprocess.run(  # noqa: S603
            command,
            shell=True,  # noqa: S602
            cwd=root,
            check=False,
        )
        raise typer.Exit(result.returncode)
    except KeyboardInterrupt:
        raise typer.Exit(130)


# ── ag hooks ─────────────────────────────────────────────────────────────────

@app.command()
def hooks(
    action: str = typer.Argument("status", help="Action: install, uninstall, status, ci"),
    path: str = typer.Option(None, "--path", "-p", help="Project root (default: cwd)"),
    ci_type: str = typer.Option("github", "--ci", help="CI type for 'ci' action: github, gitlab, shell"),
    output: str = typer.Option(None, "--output", "-o", help="Output file for CI template"),
):
    """Manage git security hooks and generate CI security templates."""
    from agentra.hooks.ci import generate_github_actions_step, generate_gitlab_ci_job, generate_pre_build_ci_check
    from agentra.hooks.git import hooks_status, install_git_hooks, uninstall_git_hooks

    root = _resolve_root(path)

    if action == "install":
        statuses = install_git_hooks(root)
        if "error" in statuses:
            console.print(f"[red]✗[/] {statuses['error']}")
            raise typer.Exit(1)
        table = Table(title="Hook Installation", show_header=True)
        table.add_column("Hook", style="cyan")
        table.add_column("Status", width=20)
        for hook_name, status in statuses.items():
            color = "green" if status in ("installed", "updated", "appended") else "red"
            table.add_row(hook_name, f"[{color}]{status}[/]")
        console.print(table)
        console.print("\n[green]✓[/] Hooks installed. Security scan runs automatically on commit/push.")
        console.print("[dim]Override with: git commit --no-verify[/]")

    elif action == "uninstall":
        statuses = uninstall_git_hooks(root)
        if "error" in statuses:
            console.print(f"[red]✗[/] {statuses['error']}")
            raise typer.Exit(1)
        for hook_name, status in statuses.items():
            color = "green" if "removed" in status else "yellow"
            console.print(f"[{color}]{hook_name}[/]: {status}")

    elif action == "status":
        statuses = hooks_status(root)
        if "error" in statuses:
            console.print(f"[yellow]⚠[/] {statuses['error']['path'] or 'No git repo found'}")
            raise typer.Exit(1)
        table = Table(title="Git Hook Status", show_header=True)
        table.add_column("Hook", style="cyan")
        table.add_column("Exists", width=8)
        table.add_column("Managed by Agentra", width=20)
        table.add_column("Executable", width=12)
        table.add_column("Path", style="dim")
        for hook_name, info in statuses.items():
            table.add_row(
                hook_name,
                "[green]✓[/]" if info["exists"] else "[red]✗[/]",
                "[green]✓[/]" if info["managed"] else "[dim]no[/]",
                "[green]✓[/]" if info.get("executable") else "[yellow]no[/]",
                info["path"],
            )
        console.print(table)

    elif action == "ci":
        if ci_type == "github":
            content = generate_github_actions_step()
            title = "GitHub Actions Workflow"
        elif ci_type == "gitlab":
            content = generate_gitlab_ci_job()
            title = "GitLab CI Job"
        else:
            content = generate_pre_build_ci_check()
            title = "Pre-Build Shell Script"

        if output:
            out_path = root / output
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            console.print(f"[green]✓[/] {title} written to {out_path}")
        else:
            console.print(Panel(content, title=title))

    else:
        console.print(f"[red]Unknown action: {action}[/]. Use: install, uninstall, status, ci")
        raise typer.Exit(1)


# ── ag plugin ────────────────────────────────────────────────────────────────

@app.command()
def plugin(
    path: str = typer.Argument(None, help="Project root (default: cwd)"),
    output: str = typer.Option(".agentra-plugin", "--output", "-o", help="Output directory for plugin package"),
):
    """Generate a Claude Code plugin package for Agentra."""
    from agentra.adapters.agents import generate_claude_plugin
    from agentra.onboarding.engine import load_config

    root = _resolve_root(path)
    output_dir = root / output

    config = load_config(root)

    with console.status("[bold green]Generating Claude Code plugin..."):
        written = generate_claude_plugin(output_dir, config)

    console.print(Panel(
        f"[bold green]Claude Code plugin generated![/]\n"
        f"Location: {output_dir}\n\n"
        f"[cyan]To install in Claude Code:[/]\n"
        f"  /plugin add {output_dir}\n\n"
        f"[cyan]Files created:[/]\n" +
        "\n".join(f"  • {p.relative_to(root)}" for p in written),
        title="✓ Plugin Generated",
    ))

    console.print(
        f"\n[dim]The plugin includes a PreToolUse hook that intercepts build commands "
        f"and runs [bold]ag scan[/] automatically.[/]"
    )


# ── ag version ───────────────────────────────────────────────────────────────

@app.command()
def version():
    """Show Agentra version."""
    console.print(f"Agentra v{__version__}")


# ── ag index ─────────────────────────────────────────────────────────────────

@app.command(name="index")
def index_cmd(
    path: str = typer.Argument(None, help="Project root (default: cwd)"),
    index_path: str = typer.Option(".agentra", "--index-path", help="Directory for the knowledge graph DB and RAG store"),
    force: bool = typer.Option(False, "--force", help="Rebuild index from scratch even for unchanged files"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json"),
):
    """Build (or update) the persistent code knowledge graph and TF-IDF RAG index."""
    import json as json_mod

    root = _resolve_root(path)
    idx_dir = (root / index_path).resolve()

    try:
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine
    except ImportError:
        console.print(
            "[red]Enterprise dependencies not installed.[/]\n"
            "Run: [bold]pip install agentra[enterprise][/]"
        )
        raise typer.Exit(code=1) from None

    with console.status("[bold green]Building code knowledge graph..."):
        idx_dir.mkdir(parents=True, exist_ok=True)
        with CodeIndexEngine(idx_dir) as idx:
            import time as _time
            t0 = _time.monotonic()
            report = idx.build(root, force=force)
            idx_duration = round(_time.monotonic() - t0, 2)

            rag = CodeRAGEngine(idx_dir, idx)
            t1 = _time.monotonic()
            rag.build(force=force)
            rag_duration = round(_time.monotonic() - t1, 2)

    if output_format == "json":
        print(json_mod.dumps({
            "files_indexed": report.files_indexed,
            "files_skipped": report.files_skipped,
            "symbols_extracted": report.symbols_extracted,
            "antipatterns_found": report.antipatterns_found,
            "incremental": report.incremental,
            "index_duration_s": idx_duration,
            "rag_duration_s": rag_duration,
        }, indent=2))
    else:
        mode_label = "Incremental" if report.incremental else "Full"
        console.print(Panel(
            f"[green]Knowledge graph built successfully ({mode_label})[/]\n"
            f"Files indexed: [bold]{report.files_indexed}[/] | "
            f"Skipped: [bold]{report.files_skipped}[/] | "
            f"Symbols: [bold]{report.symbols_extracted}[/]\n"
            f"Anti-patterns found: [bold]{report.antipatterns_found}[/] | "
            f"Index: {idx_duration}s | RAG: {rag_duration}s",
            title="ag index",
        ))
        table = Table(title="Index Summary", show_header=True)
        table.add_column("Metric")
        table.add_column("Value", justify="right")
        table.add_row("Files indexed", str(report.files_indexed))
        table.add_row("Files skipped", str(report.files_skipped))
        table.add_row("Symbols extracted", str(report.symbols_extracted))
        table.add_row("Anti-patterns", str(report.antipatterns_found))
        table.add_row("Mode", mode_label)
        table.add_row("Index build time", f"{idx_duration}s")
        table.add_row("RAG build time", f"{rag_duration}s")
        table.add_row("Index location", str(idx_dir))
        console.print(table)


# ── ag patterns ───────────────────────────────────────────────────────────────

@app.command(name="patterns")
def patterns_cmd(
    path: str = typer.Argument(None, help="Project root (default: cwd)"),
    file: str = typer.Option(None, "--file", help="Scan a specific file instead of the whole project"),
    severity: str = typer.Option(None, "--severity", help="Filter by severity: critical, high, medium, low"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json"),
):
    """Detect code smells and anti-patterns using the knowledge graph index."""
    import json as json_mod

    root = _resolve_root(path)
    idx_dir = root / ".agentra"

    try:
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine
        from agentra.rag.patterns import AntiPatternLibrary
    except ImportError:
        console.print(
            "[red]Enterprise dependencies not installed.[/]\n"
            "Run: [bold]pip install agentra[enterprise][/]"
        )
        raise typer.Exit(code=1) from None

    if file:
        # Scan a single file directly
        target = Path(file).resolve()
        lib = AntiPatternLibrary()
        antipatterns = lib.scan_file(target)
    else:
        db_path = idx_dir / "code_index.db"
        if not db_path.exists():
            console.print(
                "[yellow]No knowledge graph index found.[/] "
                "Run [bold]ag index[/] first to build the index."
            )
            raise typer.Exit(code=1)
        with CodeIndexEngine(idx_dir) as idx:
            rag = CodeRAGEngine(idx_dir, idx)
            antipatterns = rag.project_antipatterns()

    if severity:
        antipatterns = [ap for ap in antipatterns if ap.severity.value.lower() == severity.lower()]

    if output_format == "json":
        print(json_mod.dumps([
            {
                "pattern_id": ap.pattern_id,
                "name": ap.name,
                "severity": ap.severity.value,
                "file": ap.file_path,
                "line": ap.line,
                "description": ap.description,
                "suggestion": ap.suggestion,
                "context": ap.context,
            }
            for ap in antipatterns
        ], indent=2))
    else:
        if not antipatterns:
            console.print("[green]No anti-patterns detected![/]")
            return

        sev_color = {"critical": "red", "high": "red", "medium": "yellow", "low": "cyan", "info": "dim"}

        table = Table(title=f"Anti-patterns ({len(antipatterns)} found)", show_header=True)
        table.add_column("ID")
        table.add_column("Severity")
        table.add_column("Name")
        table.add_column("File")
        table.add_column("Line", justify="right")
        table.add_column("Suggestion")

        for ap in antipatterns:
            color = sev_color.get(ap.severity.value.lower(), "white")
            short_path = ap.file_path.split("/")[-1] if "/" in ap.file_path else ap.file_path.split("\\")[-1]
            table.add_row(
                ap.pattern_id,
                f"[{color}]{ap.severity.value.upper()}[/]",
                ap.name,
                short_path,
                str(ap.line),
                ap.suggestion[:60] + "…" if len(ap.suggestion) > 60 else ap.suggestion,
            )

        console.print(table)



# ── ag rag ───────────────────────────────────────────────────────────────────

@app.command(name="rag")
def rag_cmd(
    query: str = typer.Argument(..., help="Natural language description of what you want to find"),
    path: str = typer.Option(None, "--path", "-p", help="Project root (default: cwd)"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to return"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json"),
):
    """Semantic code search — find similar code in the knowledge graph before writing new code.

    Example: ag rag "JWT token validation middleware"
    """
    import json as json_mod

    root = _resolve_root(path)
    idx_dir = root / ".agentra"

    try:
        from agentra.index.engine import CodeIndexEngine
        from agentra.rag.engine import CodeRAGEngine
    except ImportError:
        console.print(
            "[red]Enterprise dependencies not installed.[/]\n"
            "Run: [bold]pip install agentra[enterprise][/]"
        )
        raise typer.Exit(code=1) from None

    db_path = idx_dir / "code_index.db"
    if not db_path.exists():
        console.print(
            "[yellow]No knowledge graph index found.[/] "
            "Run [bold]ag index[/] first to build the index."
        )
        raise typer.Exit(code=1)

    with console.status(f"[bold green]Searching for: {query!r}..."):
        with CodeIndexEngine(idx_dir) as idx:
            rag = CodeRAGEngine(idx_dir, idx)
            matches = rag.find_similar(query, top_k=top_k)
            # Build (file_path, start_line) → (symbol_name, snippet) lookup from the index
            chunk_lookup: dict[tuple[str, int], tuple[str, str]] = {
                (fp, sl): (sym, txt[:200])
                for _cid, fp, sl, sym, txt in idx.all_chunks()
            }

    if output_format == "json":
        print(json_mod.dumps([
            {
                "file": fp,
                "line": sl,
                "score": score,
                "symbol": chunk_lookup.get((fp, sl), ("", ""))[0],
                "snippet": chunk_lookup.get((fp, sl), ("", ""))[1],
            }
            for fp, sl, score in matches
        ], indent=2))
    else:
        if not matches:
            console.print("[dim]No similar code found. Try a broader query or run [bold]ag index[/] to rebuild.[/]")
            return

        table = Table(title=f"RAG Results for: {query!r}", show_header=True)
        table.add_column("Score", justify="right", width=7)
        table.add_column("Symbol", style="cyan", width=30)
        table.add_column("File", style="dim", width=35)
        table.add_column("Line", justify="right", width=5)
        table.add_column("Snippet", width=60)

        for fp, sl, score in matches:
            symbol, snippet = chunk_lookup.get((fp, sl), ("(chunk)", ""))
            score_color = "green" if score >= 0.7 else "yellow" if score >= 0.4 else "dim"
            short_path = fp.split("/")[-1] if "/" in fp else fp.split("\\")[-1]
            snippet_clean = snippet.replace("\n", " ").strip()[:58]
            table.add_row(
                f"[{score_color}]{score:.3f}[/]",
                symbol or "(chunk)",
                short_path,
                str(sl),
                snippet_clean,
            )
        console.print(table)
        console.print(
            "\n[dim]High score (≥0.7) → strong match. Reuse or extend that code instead of rewriting.[/]"
        )


# ── ag graph ──────────────────────────────────────────────────────────────────

@app.command(name="graph")
def graph_cmd(
    path: str = typer.Argument(None, help="Project root (default: cwd)"),
    output: str = typer.Option("code-graph.html", "--output", "-o", help="Output HTML file path"),
    max_nodes: int = typer.Option(300, "--max-nodes", help="Cap node count for large codebases"),
    no_open: bool = typer.Option(False, "--no-open", help="Do not open the HTML file in the browser after generating"),
    index_path: str = typer.Option(".agentra", "--index-path", help="Directory for the knowledge graph DB"),
    include_orphans: bool = typer.Option(False, "--include-orphans", help="Include isolated nodes (no edges). By default, import nodes and true orphans are hidden."),
):
    """Generate an interactive HTML call-graph visualization from the code knowledge graph.

    Requires ag index to have been run first.  Opens in the default browser automatically.
    By default, import nodes and isolated symbols with no edges are hidden — use --include-orphans to show them.
    """
    import webbrowser

    root = _resolve_root(path)
    idx_dir = (root / index_path).resolve()
    db_path = idx_dir / "code_index.db"

    if not db_path.exists():
        console.print(
            "[yellow]No knowledge graph index found.[/] "
            "Run [bold]ag index[/] first to build the index."
        )
        raise typer.Exit(code=1)

    try:
        from agentra.index.engine import CodeIndexEngine
    except ImportError:
        console.print(
            "[red]Enterprise dependencies not installed.[/]\n"
            "Run: [bold]pip install agentra[enterprise][/]"
        )
        raise typer.Exit(code=1) from None

    with console.status("[bold green]Loading code graph…"):
        with CodeIndexEngine(idx_dir) as idx:
            # Load all symbols
            sym_rows = idx._conn.execute(
                "SELECT s.id, s.name, s.kind, f.path, s.line_start "
                "FROM symbols s JOIN files f ON s.file_id = f.id"
            ).fetchall()

            # Load all edges
            edge_rows = idx._conn.execute(
                "SELECT src_symbol_id, dst_name, edge_type FROM edges"
            ).fetchall()

            file_count = idx.total_files()

    # Build name→ids lookup for resolving edge targets
    name_to_ids: dict[str, list[int]] = {}
    id_to_sym: dict[int, dict] = {}
    for sym_id, name, kind, path, line in sym_rows:
        name_to_ids.setdefault(name, []).append(sym_id)
        id_to_sym[sym_id] = {"id": sym_id, "name": name, "kind": kind, "path": path, "line": line or 0}

    # Resolve edges and compute in-degrees
    in_degree: dict[int, int] = {s["id"]: 0 for s in id_to_sym.values()}
    resolved_edges: list[dict] = []
    seen_pairs: set[tuple[int, int]] = set()
    for src_id, dst_name, edge_type in edge_rows:
        if src_id not in id_to_sym:
            continue
        for dst_id in name_to_ids.get(dst_name, []):
            if dst_id == src_id:
                continue
            pair = (src_id, dst_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            resolved_edges.append({"from": src_id, "to": dst_id, "kind": edge_type or "call"})
            in_degree[dst_id] = in_degree.get(dst_id, 0) + 1

    # Compute out-degree (symbols that call others)
    out_degree: dict[int, int] = {s["id"]: 0 for s in id_to_sym.values()}
    for e in resolved_edges:
        out_degree[e["from"]] = out_degree.get(e["from"], 0) + 1

    # Attach in-degree to each symbol
    for sym in id_to_sym.values():
        sym["in_degree"] = in_degree.get(sym["id"], 0)
        sym["out_degree"] = out_degree.get(sym["id"], 0)

    # Filter: by default drop import nodes and true orphans (no edges at all)
    if not include_orphans:
        id_to_sym = {
            k: v for k, v in id_to_sym.items()
            if v["kind"] != "import" and (v["in_degree"] > 0 or v["out_degree"] > 0)
        }

    # Cap nodes: prioritise by in-degree desc, then by kind (class > function > method > rest)
    kind_priority = {"class": 0, "function": 1, "method": 2, "variable": 3, "import": 4}
    all_syms = sorted(
        id_to_sym.values(),
        key=lambda s: (kind_priority.get(s["kind"], 9), -s["in_degree"]),
    )
    total_nodes = len(all_syms)
    truncated = total_nodes > max_nodes
    if truncated:
        all_syms = all_syms[:max_nodes]

    kept_ids = {s["id"] for s in all_syms}
    kept_edges = [e for e in resolved_edges if e["from"] in kept_ids and e["to"] in kept_ids]

    meta = {
        "total_nodes": total_nodes,
        "total_edges": len(resolved_edges),
        "displayed_nodes": len(all_syms),
        "displayed_edges": len(kept_edges),
        "files": file_count,
        "hotspot_count": len({s["name"] for s in all_syms if s["in_degree"] >= 3 and not s["name"].startswith("__")}),
        "truncated": truncated,
        "max_nodes": max_nodes,
    }

    from agentra.renderers.graph_html import write_graph_html
    out_path = Path(output).resolve()
    write_graph_html(all_syms, kept_edges, meta, out_path)

    console.print(Panel(
        f"[green]Call graph generated[/]\n"
        f"Nodes: [bold]{len(all_syms)}[/] | Edges: [bold]{len(kept_edges)}[/] | Files: [bold]{file_count}[/]"
        + (f"\n[yellow]Truncated to {max_nodes} nodes (total: {total_nodes}) — use --max-nodes to show more[/]" if truncated else ""),
        title="ag graph",
    ))
    console.print(f"[dim]Output:[/] {out_path}")

    if not no_open:
        webbrowser.open(out_path.as_uri())
        console.print("[dim]Opened in browser. Requires internet to load vis.js.[/]")


# ── ag model ─────────────────────────────────────────────────────────────────

@app.command(name="model")
def model_cmd(
    action: str = typer.Argument("list", help="Action: list, set, detect"),
    agent_name: str = typer.Argument(None, help="Agent platform (for 'set'): claude, copilot, cursor, …"),
    model_name: str = typer.Argument(None, help="Model name (for 'set'): e.g. claude-opus-4-7, gpt-5.5"),
    path: str = typer.Option(None, "--path", "-p", help="Project root (default: cwd)"),
    purpose: str = typer.Option(
        None, "--purpose",
        help="Purpose to set model for: coding, reasoning, planning, documentation, general",
    ),
    auto_fallback: bool = typer.Option(
        False, "--auto-fallback",
        help="If model is not in the known list, automatically pick the next best from the fallback chain.",
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i",
        help="Prompt to choose a model interactively from the available list.",
    ),
):
    """View or change model preferences per agent platform.

    Examples:

      ag model list

      ag model detect

      ag model set claude claude-opus-4-7

      ag model set copilot --interactive

      ag model set claude gpt-unknown --auto-fallback

      ag model set copilot gpt-5.5 --purpose reasoning
    """
    from agentra.adapters.agents import generate_for_agents, write_agent_files
    from agentra.detection.engine import StackDetector
    from agentra.governance.engine import GovernanceEngine
    from agentra.models import (
        AGENT_DEFAULT_MODELS, AGENT_PURPOSES, CAPABILITY_FALLBACK_CHAINS,
        KNOWN_MODELS, PURPOSE_MODELS, AgentPlatform,
        detect_active_models, resolve_model_with_fallback,
    )
    from agentra.onboarding.engine import load_config, save_config
    from agentra.optimizer.engine import TokenOptimizer

    root = _resolve_root(path)
    config = load_config(root)

    def _require_config():
        if config is None:
            console.print("[red]No Agentra config found.[/] Run [bold]ag init[/] first.")
            raise typer.Exit(1)
        return config

    if action == "detect":
        # ── ag model detect ───────────────────────────────────────────────────
        active = detect_active_models()

        dtable = Table(title="Detected Active Models", show_header=True)
        dtable.add_column("Platform", style="cyan")
        dtable.add_column("Model", style="bold green")
        dtable.add_column("Source", style="dim")

        platforms = [ag.value for ag in config.agents] if config else list(KNOWN_MODELS.keys())

        any_detected = False
        for platform in platforms:
            if platform in active:
                dtable.add_row(platform, active[platform]["model"], active[platform]["source"])
                any_detected = True
            else:
                dtable.add_row(platform, "[dim]unknown[/]", "not found in env or settings")

        console.print(dtable)

        if not any_detected:
            console.print(
                "\n[yellow]No active models detected from environment.[/]\n"
                "[dim]For Copilot/Cursor: model is selected in the IDE UI — not exposed via env.\n"
                "For Claude Code: set CLAUDE_MODEL env var or check ~/.claude/settings.json.\n"
                "For Aider: set AIDER_MODEL env var.[/]"
            )
        else:
            console.print(
                "\n[dim]Note: Copilot/Cursor model selection is IDE-controlled.\n"
                "Set CLAUDE_MODEL, AIDER_MODEL, or OPENAI_MODEL to make them detectable.[/]"
            )

        # Hint: tell users they can ask the AI to self-identify
        console.print(
            "\n[bold]Tip:[/] To know which model is generating a response, add this to "
            "your prompt:\n"
            '[dim]"State which model version you are at the start of your response."[/]'
        )
        return

    elif action == "list":
        cfg = _require_config()
        # Main model table
        table = Table(title="Model Preferences", show_header=True)
        table.add_column("Agent", style="cyan")
        table.add_column("Active Model")
        table.add_column("Available Models", style="dim")

        for ag in cfg.agents:
            active = cfg.model_preferences.get(ag.value) or AGENT_DEFAULT_MODELS.get(ag.value, "—")
            choices = ", ".join(KNOWN_MODELS.get(ag.value, []))
            table.add_row(ag.value, f"[bold]{active}[/]", choices)

        console.print(table)

        # Per-purpose routing table (only if any agent has purpose preferences set)
        any_purposes = any(cfg.model_purpose_preferences.get(ag.value) for ag in cfg.agents)
        if any_purposes:
            console.print("")
            ptable = Table(title="Per-Purpose Model Routing", show_header=True)
            ptable.add_column("Agent", style="cyan")
            ptable.add_column("Purpose")
            ptable.add_column("Model", style="bold")

            purpose_labels = {
                "planning":      "🗺️  Planning",
                "reasoning":     "🧠 Reasoning",
                "review":        "🔍 Review",
                "coding":        "💻 Coding",
                "testing":       "🧪 Testing",
                "refactoring":   "🔧 Refactoring",
                "documentation": "📝 Documentation",
                "general":       "⚡ General",
                "formatting":    "✨ Formatting",
            }
            for ag in cfg.agents:
                pm = cfg.model_purpose_preferences.get(ag.value, {})
                if not pm:
                    pm = PURPOSE_MODELS.get(ag.value, {})
                first = True
                for p in AGENT_PURPOSES:
                    m = pm.get(p, "—")
                    ptable.add_row(ag.value if first else "", purpose_labels.get(p, p), m)
                    first = False

            console.print(ptable)

        console.print(
            "\n[dim]Change general model: ag model set <agent> <model>[/]\n"
            "[dim]Change purpose model: ag model set <agent> <model> --purpose <purpose>[/]\n"
            "[dim]Interactive pick:      ag model set <agent> --interactive[/]\n"
            "[dim]Detect active models:  ag model detect[/]"
        )

    elif action == "set":
        cfg = _require_config()

        if not agent_name:
            console.print("[red]Usage: ag model set <agent> [<model>] [--purpose <purpose>][/]")
            raise typer.Exit(1)

        try:
            ag = AgentPlatform(agent_name)
        except ValueError:
            valid = ", ".join(p.value for p in AgentPlatform)
            console.print(f"[red]Unknown agent '{agent_name}'.[/] Valid: {valid}")
            raise typer.Exit(1)

        if ag not in cfg.agents:
            console.print(
                f"[yellow]Agent '{ag.value}' is not in your config. "
                "Add it with [bold]ag init --agents {ag.value}[/]."
            )

        known = KNOWN_MODELS.get(ag.value, [])

        # ── Interactive mode: prompt user to pick ─────────────────────────────
        if interactive or (not model_name and not auto_fallback):
            if not model_name:
                if not known:
                    console.print(f"[red]No known models for {ag.value}.[/]")
                    raise typer.Exit(1)
                console.print(f"\n[bold]Available models for [cyan]{ag.value}[/]:[/]")
                for i, m in enumerate(known, 1):
                    # Mark capability class for context
                    cap_hints = {
                        v: k for k, v in {
                            "deep_reasoning": CAPABILITY_FALLBACK_CHAINS.get(ag.value, {}).get("deep_reasoning", [""])[0],
                            "coding": CAPABILITY_FALLBACK_CHAINS.get(ag.value, {}).get("coding", [""])[0],
                            "balanced": CAPABILITY_FALLBACK_CHAINS.get(ag.value, {}).get("balanced", [""])[0],
                            "fast": CAPABILITY_FALLBACK_CHAINS.get(ag.value, {}).get("fast", [""])[0],
                        }.items()
                    }
                    hint = f" [dim]({cap_hints[m]} class)[/]" if m in cap_hints else ""
                    console.print(f"  [cyan]{i}[/]. {m}{hint}")
                raw = typer.prompt(f"\nEnter number or model name")
                if raw.isdigit():
                    idx = int(raw) - 1
                    if 0 <= idx < len(known):
                        model_name = known[idx]
                    else:
                        console.print("[red]Invalid selection.[/]")
                        raise typer.Exit(1)
                else:
                    model_name = raw.strip()

        # ── Validate / auto-fallback ──────────────────────────────────────────
        if model_name and known and model_name not in known:
            if auto_fallback:
                # Determine the capability class for the requested model,
                # then pick the next available model from the fallback chain.
                # Use "balanced" as the default capability if we can't infer.
                cap = "balanced"
                for cap_class, chain in CAPABILITY_FALLBACK_CHAINS.get(ag.value, {}).items():
                    if model_name in chain:
                        cap = cap_class
                        break
                fallback = resolve_model_with_fallback(ag.value, cap, restricted={model_name})
                console.print(
                    f"[yellow]'{model_name}' is not in the known list for {ag.value}.[/]\n"
                    f"[green]Auto-fallback:[/] using [bold]{fallback}[/] "
                    f"(next best for '{cap}' capability)"
                )
                model_name = fallback
            else:
                choices_str = ", ".join(known)
                fallback_chain = CAPABILITY_FALLBACK_CHAINS.get(ag.value, {}).get("balanced", [])
                console.print(
                    f"[yellow]Warning:[/] '{model_name}' is not in the known list for {ag.value}.\n"
                    f"Known models: {choices_str}\n"
                    f"[dim]Tip: use --auto-fallback to automatically pick the next best, "
                    f"or --interactive to choose.[/]\n"
                    "Proceeding anyway."
                )

        if not model_name:
            console.print("[red]No model specified. Use --interactive to pick, or provide a model name.[/]")
            raise typer.Exit(1)

        if purpose:
            # Set model for a specific purpose only
            if purpose not in AGENT_PURPOSES:
                console.print(
                    f"[red]Unknown purpose '{purpose}'.[/] "
                    f"Valid purposes: {', '.join(AGENT_PURPOSES)}"
                )
                raise typer.Exit(1)
            if ag.value not in cfg.model_purpose_preferences:
                cfg.model_purpose_preferences[ag.value] = dict(PURPOSE_MODELS.get(ag.value, {}))
            cfg.model_purpose_preferences[ag.value][purpose] = model_name
            save_config(cfg, root)
            console.print(
                f"[green]✓[/] Set {ag.value} [bold]{purpose}[/] model to [bold]{model_name}[/]"
            )
        else:
            # Set the general (active) model for this agent
            cfg.model_preferences[ag.value] = model_name
            save_config(cfg, root)
            console.print(f"[green]✓[/] Set {ag.value} model to [bold]{model_name}[/]")

        # Regenerate agent files to reflect the change
        detector = StackDetector(root)
        stack = detector.detect()
        governance = GovernanceEngine(stack)
        optimizer = TokenOptimizer(cfg.token_budget)
        agent_files = generate_for_agents(cfg.agents, cfg, stack, governance, optimizer)
        written = write_agent_files(root, agent_files)
        console.print(f"[green]✓[/] Regenerated {len(written)} agent file(s) with updated model preference.")

    else:
        console.print(f"[red]Unknown action '{action}'.[/] Use: list, set, detect")
        raise typer.Exit(1)


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
