import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from . import __version__
from .analysis import analyze as analyze_recording
from .ingestion import RecordingError
from .models import AnalysisConfig, Report
from .reporting import json_report, literal, print_report
from .sample import generate_sample

app = typer.Typer(no_args_is_help=True, help="Offline, evidence-backed ROS 2 MCAP analysis.")


class OutputFormat(StrEnum):
    terminal = "terminal"
    json = "json"


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[
        bool, typer.Option("--version", help="Print version and exit.", is_eager=True)
    ] = False,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def sample(
    path: Annotated[Path, typer.Argument(help="New synthetic MCAP path; never overwrites.")],
) -> None:
    try:
        generate_sample(path)
    except Exception as exc:
        typer.echo(literal(f"Could not create sample: {exc}"), err=True)
        raise typer.Exit(1) from exc
    typer.echo(literal(f"Created synthetic diagnostic recording: {path}"))


@app.command("schema")
def report_schema() -> None:
    """Print the JSON Schema for report consumers."""
    typer.echo(json.dumps(Report.model_json_schema(), indent=2))


@app.command()
def analyze(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    format: Annotated[
        OutputFormat, typer.Option("--format", help="Stdout report format.")
    ] = OutputFormat.terminal,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Also write JSON to a new file.")
    ] = None,
    navigation_status_topic: Annotated[
        list[str] | None,
        typer.Option(
            "--navigation-status-topic",
            help="Declare a navigation GoalStatusArray topic; repeatable.",
        ),
    ] = None,
    expect_rate: Annotated[
        list[str] | None,
        typer.Option(
            "--expect-rate", help="Expected continuous topic rate: /topic=HZ; repeatable."
        ),
    ] = None,
    gap_factor: Annotated[
        float,
        typer.Option("--gap-factor", help="Flag intervals strictly longer than this many periods."),
    ] = 3.0,
    max_messages: Annotated[int, typer.Option("--max-messages", min=1)] = 1_000_000,
    max_events: Annotated[int, typer.Option("--max-events", min=1)] = 1_000_000,
    max_record_bytes: Annotated[int, typer.Option("--max-record-bytes", min=1)] = 64 * 1024 * 1024,
) -> None:
    """Analyze a single MCAP file. No data leaves this machine."""
    rates: dict[str, float] = {}
    try:
        for entry in expect_rate or []:
            topic, value = entry.rsplit("=", 1)
            if topic in rates:
                raise ValueError(f"duplicate expected-rate topic: {topic}")
            rates[topic] = float(value)
        topics = list(dict.fromkeys(navigation_status_topic or []))
        if any(not topic.startswith("/") for topic in topics):
            raise ValueError("navigation topics must be absolute ROS topic names")
        config = AnalysisConfig(
            navigation_status_topics=topics,
            expected_rates_hz=rates,
            gap_factor=gap_factor,
            max_messages=max_messages,
            max_events=max_events,
            max_record_bytes=max_record_bytes,
        )
    except (ValueError, ValidationError) as exc:
        raise typer.BadParameter(literal(str(exc))) from exc
    try:
        # Never overwrite existing files, including the input and symlinks to it.
        if output is not None and (output.exists() or output.is_symlink()):
            raise FileExistsError(f"Output already exists: {output}")
        report = analyze_recording(path, config)
        serialized = json_report(report)
        if output is not None:
            with output.open("x", encoding="utf-8", newline="\n") as destination:
                destination.write(serialized + "\n")
        if format == OutputFormat.json:
            typer.echo(serialized)
        else:
            print_report(report, Console())
    except (RecordingError, OSError) as exc:
        typer.echo(literal(f"Analysis failed: {exc}"), err=True)
        raise typer.Exit(1) from exc
