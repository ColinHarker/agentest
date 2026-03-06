"""CLI interface for Agentest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from agentest.core import AgentTrace
from agentest.evaluators.base import CompositeEvaluator
from agentest.evaluators.builtin import (
    CostEvaluator,
    LatencyEvaluator,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
)
from agentest.recorder.recorder import Recorder
from agentest.recorder.replayer import Replayer
from agentest.reporters.console import ConsoleReporter
from agentest.reporters.json_reporter import JSONReporter

console = Console()
err_console = Console(stderr=True)
reporter = ConsoleReporter(console)


@click.group()
@click.version_option(version="0.2.0", prog_name="agentest")
def main() -> None:
    """Agentest - Universal agent testing and evaluation toolkit."""
    pass


@main.command()
@click.argument("trace_path", type=click.Path(exists=True))
@click.option("--max-cost", type=float, default=None, help="Max cost budget in USD.")
@click.option("--max-tokens", type=int, default=None, help="Max token budget.")
@click.option("--max-time-ms", type=float, default=None, help="Max total time in ms.")
@click.option("--check-safety/--no-check-safety", default=True, help="Run safety checks.")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save JSON report to file.")
def evaluate(
    trace_path: str,
    max_cost: float | None,
    max_tokens: int | None,
    max_time_ms: float | None,
    check_safety: bool,
    output: str | None,
) -> None:
    """Evaluate a recorded agent trace."""
    trace = Recorder.load(trace_path)

    evaluators = [TaskCompletionEvaluator(), ToolUsageEvaluator()]

    if check_safety:
        evaluators.append(SafetyEvaluator())
    if max_cost is not None or max_tokens is not None:
        evaluators.append(CostEvaluator(max_cost=max_cost, max_tokens=max_tokens))
    if max_time_ms is not None:
        evaluators.append(LatencyEvaluator(max_total_ms=max_time_ms))

    composite = CompositeEvaluator(evaluators)
    results = composite.evaluate_all(trace)

    reporter.print_eval_results(results, title=f"Evaluation: {trace_path}")

    all_passed = all(r.passed for r in results)

    if output:
        json_reporter = JSONReporter()
        json_reporter.save(JSONReporter.eval_results_to_dict(results), output)
        console.print(f"\nReport saved to: {output}")

    if not all_passed:
        sys.exit(1)


@main.command()
@click.argument("trace_path", type=click.Path(exists=True))
@click.option("--strict/--no-strict", default=True, help="Fail on mismatches.")
def replay(trace_path: str, strict: bool) -> None:
    """Replay a recorded agent trace and verify consistency."""
    trace = Recorder.load(trace_path)
    replayer = Replayer(trace, strict=strict)

    console.print(f"[bold]Replaying trace:[/bold] {trace_path}")
    console.print(f"  Task: {trace.task}")
    console.print(f"  LLM responses: {len(trace.llm_responses)}")
    console.print(f"  Tool calls: {len(trace.tool_calls)}")
    console.print()

    # Replay all interactions
    for i, response in enumerate(trace.llm_responses):
        console.print(f"  [{i + 1}] LLM: {response.model} - {response.content[:80]}...")

    for i, tc in enumerate(trace.tool_calls):
        status = "[green]OK[/green]" if tc.succeeded else f"[red]ERR: {tc.error}[/red]"
        console.print(f"  [{i + 1}] Tool: {tc.name}({tc.arguments}) -> {status}")

    # Generate mock functions
    mocks = replayer.create_tool_mock()
    console.print(f"\n  Generated {len(mocks)} tool mocks for replay testing")

    if trace.success:
        console.print("\n[bold green]Trace replayed successfully.[/bold green]")
    else:
        console.print(f"\n[bold red]Trace ended with error: {trace.error}[/bold red]")
        sys.exit(1)


@main.command()
@click.argument("trace_dir", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def summary(trace_dir: str, fmt: str) -> None:
    """Summarize all traces in a directory."""
    trace_path = Path(trace_dir)
    traces: list[AgentTrace] = []

    for f in sorted(trace_path.iterdir()):
        if f.suffix in (".yaml", ".yml", ".json"):
            try:
                traces.append(Recorder.load(f))
            except Exception as e:
                err_console.print(f"[yellow]Warning: Could not load {f}: {e}[/yellow]")

    if not traces:
        console.print("[yellow]No traces found.[/yellow]")
        return

    if fmt == "json":
        data = []
        for t in traces:
            data.append(
                {
                    "id": t.id,
                    "task": t.task,
                    "success": t.success,
                    "duration_ms": t.duration_ms,
                    "total_cost": t.total_cost,
                    "total_tokens": t.total_tokens,
                    "tool_calls": t.total_tool_calls,
                }
            )
        console.print(json.dumps(data, indent=2))
    else:
        from rich.table import Table

        table = Table(title=f"Traces in {trace_dir}", show_lines=True)
        table.add_column("Task", style="cyan", max_width=40)
        table.add_column("Status", justify="center")
        table.add_column("Cost", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Tools", justify="right")
        table.add_column("Time (ms)", justify="right")

        for t in traces:
            from rich.text import Text

            status = Text("OK", style="green") if t.success else Text("FAIL", style="red")
            table.add_row(
                t.task[:40],
                status,
                f"${t.total_cost:.4f}",
                str(t.total_tokens),
                str(t.total_tool_calls),
                f"{t.duration_ms:.0f}" if t.duration_ms else "N/A",
            )

        console.print(table)
        console.print(
            f"\nTotal: {len(traces)} traces, "
            f"{sum(1 for t in traces if t.success):d} passed, "
            f"${sum(t.total_cost for t in traces):.4f} total cost"
        )


@main.command()
def init() -> None:
    """Initialize Agentest in the current project."""
    # Create directories
    dirs = ["traces", "tests/agent_tests"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        console.print(f"  Created {d}/")

    # Create sample test file
    sample_test = Path("tests/agent_tests/test_agent_example.py")
    if not sample_test.exists():
        sample_test.write_text('''"""Example agent evaluation tests."""

from agentest import Recorder, Replayer, ToolMock, MockToolkit
from agentest.evaluators.builtin import (
    TaskCompletionEvaluator,
    SafetyEvaluator,
    CostEvaluator,
)


def test_agent_completes_task(agent_recorder, agent_eval_suite):
    """Test that an agent completes its task successfully."""
    agent_recorder.trace.task = "Summarize a document"

    agent_recorder.record_message("user", "Please summarize README.md")
    agent_recorder.record_tool_call(
        name="read_file",
        arguments={"path": "README.md"},
        result="# My Project\\nThis is a sample project.",
    )
    agent_recorder.record_llm_response(
        model="claude-sonnet-4-6",
        content="This project is a sample project.",
        input_tokens=100,
        output_tokens=20,
    )
    trace = agent_recorder.finalize(success=True)

    results = agent_eval_suite.evaluate_all(trace)
    assert all(r.passed for r in results)


def test_tool_mocking(agent_toolkit):
    """Test mocked tools return expected results."""
    agent_toolkit.mock("read_file").returns("file contents")
    agent_toolkit.mock("search").when(query="python").returns(["result1"])
    agent_toolkit.mock("search").otherwise().returns([])

    assert agent_toolkit.execute("read_file", path="test.txt") == "file contents"
    assert agent_toolkit.execute("search", query="python") == ["result1"]


def test_safety_check():
    """Test that unsafe commands are flagged."""
    recorder = Recorder(task="Run a command")
    recorder.record_tool_call(
        name="bash",
        arguments={"command": "rm -rf /"},
        result="",
    )
    trace = recorder.finalize(success=True)

    evaluator = SafetyEvaluator()
    result = evaluator.evaluate(trace)
    assert not result.passed, "Should flag unsafe commands"


def test_cost_budget():
    """Test that cost limits are enforced."""
    recorder = Recorder(task="Expensive task")
    recorder.record_llm_response(
        model="claude-opus-4-6",
        content="response",
        input_tokens=100000,
        output_tokens=50000,
    )
    trace = recorder.finalize(success=True)

    evaluator = CostEvaluator(max_cost=0.50)
    result = evaluator.evaluate(trace)
    assert not result.passed, "Should flag over-budget tasks"
''')
        console.print(f"  Created {sample_test}")

    # Create sample conftest
    conftest = Path("tests/agent_tests/conftest.py")
    if not conftest.exists():
        conftest.write_text('''"""Agentest pytest configuration.

The agentest pytest plugin auto-registers fixtures:
  - agent_recorder: Fresh Recorder for each test
  - agent_toolkit: Fresh MockToolkit for each test
  - agent_eval_suite: Standard evaluation suite
"""
''')
        console.print(f"  Created {conftest}")

    console.print("\n[bold green]Agentest initialized![/bold green]")
    console.print("Run tests with: [cyan]pytest tests/agent_tests/[/cyan]")


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", "-p", default=8000, type=int, help="Port to bind to.")
@click.option("--traces-dir", default="traces", help="Directory containing traces.")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload for development.")
def serve(host: str, port: int, traces_dir: str, reload: bool) -> None:
    """Start the Agentest web UI."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error:[/red] Web UI requires extra dependencies.")
        console.print("Install with: [cyan]pip install agentest[web][/cyan]")
        sys.exit(1)

    from agentest.server.app import create_app

    Path(traces_dir).mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Agentest UI[/bold] starting at [cyan]http://{host}:{port}[/cyan]")
    console.print(f"  Traces directory: [cyan]{traces_dir}[/cyan]")
    console.print()

    # Create app with traces dir
    app = create_app(traces_dir=traces_dir)

    uvicorn.run(app, host=host, port=port, log_level="info")


@main.command()
@click.argument("trace_dir", type=click.Path(exists=True))
@click.option("--port", "-p", default=8000, type=int, help="Port for the UI server.")
def ui(trace_dir: str, port: int) -> None:
    """Open the web UI for a traces directory (alias for serve)."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error:[/red] Web UI requires extra dependencies.")
        console.print("Install with: [cyan]pip install agentest[web][/cyan]")
        sys.exit(1)
    import webbrowser

    from agentest.server.app import create_app

    app = create_app(traces_dir=trace_dir)

    console.print(f"[bold]Opening Agentest UI[/bold] at [cyan]http://127.0.0.1:{port}[/cyan]")
    webbrowser.open(f"http://127.0.0.1:{port}")

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


@main.command()
@click.argument("trace_a", type=click.Path(exists=True))
@click.argument("trace_b", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def diff(trace_a: str, trace_b: str, fmt: str) -> None:
    """Compare two traces side by side."""
    from agentest.core import diff_traces

    a = Recorder.load(trace_a)
    b = Recorder.load(trace_b)
    result = diff_traces(a, b)

    if fmt == "json":
        console.print(json.dumps(result, indent=2, default=str))
        return

    from rich.table import Table
    from rich.text import Text

    # Summary table
    title = f"Trace Diff: {Path(trace_a).name} vs {Path(trace_b).name}"
    table = Table(title=title, show_lines=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Trace A", justify="right")
    table.add_column("Trace B", justify="right")
    table.add_column("Delta", justify="right")

    summary = result["summary"]
    for key in ["total_tokens", "total_cost", "tool_call_count", "llm_call_count"]:
        if key in summary:
            val_a = summary[key]["a"]
            val_b = summary[key]["b"]
            delta = summary[key]["delta"]

            if key == "total_cost":
                a_str = f"${val_a:.4f}"
                b_str = f"${val_b:.4f}"
                d_str = f"${delta:+.4f}"
            else:
                a_str = str(val_a)
                b_str = str(val_b)
                d_str = f"{delta:+d}" if isinstance(delta, int) else f"{delta:+.0f}"

            if delta > 0 and key in ("total_cost", "total_tokens"):
                delta_style = "red"
            elif delta < 0:
                delta_style = "green"
            else:
                delta_style = ""
            table.add_row(
                key.replace("_", " ").title(),
                a_str,
                b_str,
                Text(d_str, style=delta_style),
            )

    if "duration_ms" in summary:
        d = summary["duration_ms"]
        table.add_row(
            "Duration (ms)",
            f"{d['a']:.0f}",
            f"{d['b']:.0f}",
            Text(f"{d['delta']:+.0f}", style="red" if d["delta"] > 0 else "green"),
        )

    console.print(table)

    # Success comparison
    s = summary["success"]
    if s["a"] != s["b"]:
        a_txt = "[green]OK[/green]" if s["a"] else "[red]FAIL[/red]"
        b_txt = "[green]OK[/green]" if s["b"] else "[red]FAIL[/red]"
        console.print(f"\n  Status changed: {a_txt} -> {b_txt}")

    # Tool call sequence
    tc = result["tool_calls"]
    if not tc["same_sequence"]:
        console.print("\n  [yellow]Tool call sequence differs[/yellow]")
        if tc["added"]:
            console.print(f"    Added: {', '.join(tc['added'])}")
        if tc["removed"]:
            console.print(f"    Removed: {', '.join(tc['removed'])}")

    # Errors
    errs = result["errors"]
    if errs["new_errors"]:
        console.print(f"\n  [red]New errors:[/red] {errs['new_errors']}")
    if errs["resolved_errors"]:
        console.print(f"\n  [green]Resolved errors:[/green] {errs['resolved_errors']}")


@main.command()
@click.argument("traces_dir", type=click.Path(exists=True))
@click.option("--baseline", type=click.Path(exists=True), required=True, help="Baseline dir.")
@click.option("--update-baseline", is_flag=True, default=False, help="Update baselines.")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option("--cost-threshold", type=float, default=0.1, help="Cost threshold (0.1=10%).")
@click.option("--token-threshold", type=float, default=0.1, help="Token regression threshold.")
@click.option("--latency-threshold", type=float, default=0.2, help="Latency regression threshold.")
def regression(
    traces_dir: str,
    baseline: str,
    update_baseline: bool,
    fmt: str,
    cost_threshold: float,
    token_threshold: float,
    latency_threshold: float,
) -> None:
    """Detect regressions by comparing traces against baselines."""
    from agentest.regression import RegressionDetector, RegressionThresholds

    thresholds = RegressionThresholds(
        cost_increase=cost_threshold,
        token_increase=token_threshold,
        latency_increase=latency_threshold,
    )
    detector = RegressionDetector(baseline_dir=baseline, thresholds=thresholds)
    results = detector.check_all(traces_dir)

    if not results:
        console.print("[yellow]No traces found.[/yellow]")
        return

    if fmt == "json":
        console.print(json.dumps([r.model_dump() for r in results], indent=2, default=str))
    else:
        from rich.table import Table
        from rich.text import Text

        table = Table(title="Regression Report", show_lines=True)
        table.add_column("Task", style="cyan", max_width=40)
        table.add_column("Status", justify="center")
        table.add_column("Regressions", justify="center")
        table.add_column("Improvements", justify="center")
        table.add_column("Details")

        for r in results:
            status = Text("PASS", style="green") if r.passed else Text("FAIL", style="red")
            details = ""
            if r.regressions:
                details = "; ".join(f"{reg.metric}: {reg.change_pct:+.1%}" for reg in r.regressions)
            table.add_row(
                r.task[:40],
                status,
                str(len(r.regressions)),
                str(len(r.improvements)),
                details,
            )

        console.print(table)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        console.print(f"\n{passed}/{total} tasks passed regression checks")

    if update_baseline:
        for r in results:
            trace_path = Path(traces_dir)
            for f in sorted(trace_path.iterdir()):
                if f.suffix in (".yaml", ".yml", ".json"):
                    try:
                        trace = Recorder.load(f)
                        if trace.task == r.task:
                            detector.update_baseline(trace)
                            console.print(f"  Updated baseline: {r.task}")
                            break
                    except Exception:
                        continue

    if any(not r.passed for r in results):
        sys.exit(1)


@main.command()
@click.argument("history_file", type=click.Path())
@click.option("--task", type=str, default=None, help="Filter to a specific task.")
@click.option("--trend", "show_trend", is_flag=True, help="Show trend analysis.")
@click.option("--ci", "show_ci", is_flag=True, help="Show confidence intervals.")
@click.option(
    "--slo",
    "slo_defs",
    multiple=True,
    help="SLO definition: metric:target:comparison (e.g. cost:0.5:lte).",
)
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def stats(
    history_file: str,
    task: str | None,
    show_trend: bool,
    show_ci: bool,
    slo_defs: tuple[str, ...],
    fmt: str,
) -> None:
    """Analyze performance statistics from run history."""
    from agentest.stats import SLO, StatsAnalyzer

    analyzer = StatsAnalyzer.load(history_file)

    if not analyzer.samples:
        console.print("[yellow]No history data found.[/yellow]")
        return

    tasks = [task] if task else list(analyzer.samples.keys())
    output: dict = {"tasks": {}}

    for t in tasks:
        task_data: dict = {}

        if show_trend:
            for metric in ["score", "cost", "tokens", "latency_ms"]:
                trend_result = analyzer.trend(t, metric=metric)
                task_data.setdefault("trends", {})[metric] = {
                    "direction": trend_result.direction.value,
                    "slope": trend_result.slope,
                    "r_squared": trend_result.r_squared,
                    "samples": trend_result.samples,
                }

        if show_ci:
            for metric in ["score", "cost", "tokens"]:
                ci = analyzer.confidence_interval(t, metric=metric)
                task_data.setdefault("confidence_intervals", {})[metric] = {
                    "mean": ci.mean,
                    "ci_lower": ci.ci_lower,
                    "ci_upper": ci.ci_upper,
                    "std": ci.std,
                    "samples": ci.samples,
                }

        if slo_defs:
            slo_results = []
            for slo_def in slo_defs:
                parts = slo_def.split(":")
                if len(parts) != 3:
                    msg = f"Invalid SLO: {slo_def} (expected metric:target:comparison)"
                    err_console.print(f"[yellow]{msg}[/yellow]")
                    continue
                slo = SLO(metric=parts[0], target=float(parts[1]), comparison=parts[2])
                slo_result = analyzer.check_slo(t, slo)
                slo_results.append(
                    {
                        "metric": slo.metric,
                        "target": slo.target,
                        "comparison": slo.comparison,
                        "compliant": slo_result.compliant,
                        "compliance_rate": slo_result.compliance_rate,
                        "current_value": slo_result.current_value,
                    }
                )
            task_data["slos"] = slo_results

        output["tasks"][t] = task_data

    if fmt == "json":
        console.print(json.dumps(output, indent=2, default=str))
    else:
        for t in tasks:
            console.print(
                f"\n[bold cyan]{t}[/bold cyan] ({len(analyzer.samples.get(t, []))} samples)"
            )

            task_data = output["tasks"].get(t, {})

            if "trends" in task_data:
                console.print("  [bold]Trends:[/bold]")
                for metric, info in task_data["trends"].items():
                    direction = info["direction"]
                    if direction == "improving":
                        style = "green"
                    elif direction == "degrading":
                        style = "red"
                    else:
                        style = ""
                    console.print(
                        f"    {metric}: [{style}]{direction}[/{style}] "
                        f"(slope={info['slope']:.4f}, R\u00b2={info['r_squared']:.2f})"
                    )

            if "confidence_intervals" in task_data:
                console.print("  [bold]95% Confidence Intervals:[/bold]")
                for metric, info in task_data["confidence_intervals"].items():
                    console.print(
                        f"    {metric}: {info['mean']:.4f} "
                        f"[{info['ci_lower']:.4f}, {info['ci_upper']:.4f}]"
                    )

            if "slos" in task_data:
                console.print("  [bold]SLO Compliance:[/bold]")
                for slo_info in task_data["slos"]:
                    status = "[green]OK[/green]" if slo_info["compliant"] else "[red]BREACH[/red]"
                    console.print(
                        f"    {slo_info['metric']} {slo_info['comparison']} {slo_info['target']}: "
                        f"{status} (rate={slo_info['compliance_rate']:.1%})"
                    )


@main.group()
def dataset() -> None:
    """Manage test datasets."""
    pass


@dataset.command("create")
@click.argument("name")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output path.")
@click.option("--description", "-d", type=str, default="", help="Dataset description.")
def dataset_create(name: str, output: str | None, description: str) -> None:
    """Create a new empty dataset."""
    from agentest.datasets import Dataset

    ds = Dataset(name=name, description=description)
    path = output or f"datasets/{name}.yaml"
    ds.save(path)
    console.print(f"Created dataset: [cyan]{path}[/cyan]")


@dataset.command("list")
@click.argument("path", type=click.Path(exists=True))
def dataset_list(path: str) -> None:
    """List test cases in a dataset."""
    from agentest.datasets import Dataset

    ds = Dataset.load(path)
    console.print(f"[bold]{ds.name}[/bold] v{ds.version} ({ds.size} test cases)")

    if ds.description:
        console.print(f"  {ds.description}")

    for tc in ds.test_cases:
        tags = f" [{', '.join(tc.tags)}]" if tc.tags else ""
        console.print(f"  - {tc.name}: {tc.task}{tags}")


@dataset.command("split")
@click.argument("path", type=click.Path(exists=True))
@click.option("--ratio", type=float, default=0.5, help="Split ratio for group A.")
@click.option("--seed", type=int, default=42, help="Random seed.")
@click.option("--output-dir", "-o", type=click.Path(), default=None, help="Output directory.")
def dataset_split(path: str, ratio: float, seed: int, output_dir: str | None) -> None:
    """Split a dataset into two groups for A/B testing."""
    from agentest.datasets import Dataset

    ds = Dataset.load(path)
    a, b = ds.split(ratio=ratio, seed=seed)

    out_dir = Path(output_dir) if output_dir else Path(path).parent
    path_a = a.save(out_dir / f"{ds.name}_A.yaml")
    path_b = b.save(out_dir / f"{ds.name}_B.yaml")

    console.print(f"Split {ds.name} ({ds.size} cases) into:")
    console.print(f"  Group A: {a.size} cases -> [cyan]{path_a}[/cyan]")
    console.print(f"  Group B: {b.size} cases -> [cyan]{path_b}[/cyan]")


@main.command()
@click.argument("trace_dir", type=click.Path(exists=True))
@click.option("--interval", "-i", default=2.0, type=float, help="Polling interval in seconds.")
@click.option("--max-cost", type=float, default=None, help="Max cost budget in USD.")
@click.option("--check-safety/--no-check-safety", default=True, help="Run safety checks.")
def watch(trace_dir: str, interval: float, max_cost: float | None, check_safety: bool) -> None:
    """Watch a traces directory and re-evaluate on changes."""
    import time as time_mod

    trace_path = Path(trace_dir)
    last_mtimes: dict[str, float] = {}

    console.print(f"[bold]Watching[/bold] {trace_dir} (every {interval}s, Ctrl+C to stop)")

    evaluators = [TaskCompletionEvaluator(), ToolUsageEvaluator()]
    if check_safety:
        evaluators.append(SafetyEvaluator())
    if max_cost is not None:
        evaluators.append(CostEvaluator(max_cost=max_cost))

    composite = CompositeEvaluator(evaluators)

    try:
        while True:
            changed = False
            for f in sorted(trace_path.iterdir()):
                if f.suffix not in (".yaml", ".yml", ".json"):
                    continue

                mtime = f.stat().st_mtime
                if f.name not in last_mtimes or last_mtimes[f.name] != mtime:
                    last_mtimes[f.name] = mtime
                    changed = True

                    try:
                        trace = Recorder.load(f)
                        results = composite.evaluate_all(trace)
                        all_ok = all(r.passed for r in results)

                        status = "[green]PASS[/green]" if all_ok else "[red]FAIL[/red]"
                        failed = [r for r in results if not r.passed]
                        detail = ""
                        if failed:
                            detail = " - " + "; ".join(r.message for r in failed)

                        console.print(
                            f"  [{time_mod.strftime('%H:%M:%S')}] {f.name}: {status}{detail}"
                        )
                    except Exception as e:
                        console.print(f"  [yellow]{f.name}: error loading - {e}[/yellow]")

            if not changed and not last_mtimes:
                console.print("  [dim]No trace files found yet...[/dim]")

            time_mod.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")


if __name__ == "__main__":
    main()
