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
):
    """Initialize Agentra for a project."""
    from agentra.adapters.agents import generate_for_agents, write_agent_files
    from agentra.detection.engine import StackDetector
    from agentra.governance.engine import GovernanceEngine
    from agentra.models import AgentPlatform, OnboardingMode
    from agentra.onboarding.engine import detect_and_build_config, save_config
    from agentra.optimizer.engine import TokenOptimizer

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

    engine = ScanEngine(root)

    with console.status("[bold green]Running vulnerability scan..."):
        report = engine.scan(targets=targets)

    if output_format == "json":
        console.print(json_mod.dumps(
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


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
