from rich.console import Console
from rich.table import Table
from rich.text import Text

from .models import Report


def literal(value: object) -> str:
    """Display telemetry without ANSI/control sequences, Rich markup or layout injection."""
    return "".join(
        f"\\x{ord(c):02x}" if ord(c) < 32 or 127 <= ord(c) < 160 else c for c in str(value)
    )


def print_report(report: Report, console: Console) -> None:
    def line(value: object = "") -> None:
        console.print(literal(value), markup=False, highlight=False, soft_wrap=True)

    line("Robot Reliability Copilot")
    line(report.summary)
    rec = report.recording
    line(f"Recording: {rec.path}")
    line(f"SHA-256: {rec.sha256}")
    line(f"Profile: {rec.profile}; writer: {rec.library}; bytes: {rec.size_bytes}")
    line(f"Log time range (ns): {rec.start_time_ns} .. {rec.end_time_ns}")
    line(report.time_basis)
    table = Table(title="Recording channels", show_lines=True)
    for col in (
        "ID / topic",
        "Type / encoding",
        "Messages",
        "Decoded / skipped / errors",
        "Log ns range",
    ):
        table.add_column(col)
    for channel in rec.channels:
        table.add_row(
            Text(literal(f"{channel.channel_id}: {channel.topic}")),
            Text(
                literal(
                    f"{channel.schema_name or 'unknown'} "
                    f"({channel.schema_encoding}, {channel.message_encoding})"
                )
            ),
            str(channel.message_count),
            f"{channel.decoded_message_count} / {channel.skipped_message_count} / "
            f"{channel.decode_error_count}",
            f"{channel.start_time_ns} .. {channel.end_time_ns}",
        )
    console.print(table)
    line("Incident timeline")
    if not report.incidents:
        line("No incidents detected by enabled rules. Available evidence may be insufficient.")
    for incident in report.incidents:
        line(
            f"{incident.id} | {incident.severity.upper()} | "
            f"{incident.category} | {incident.detector}"
        )
        line(
            f"  Start ns: {incident.start_time_ns}; "
            f"end ns: {incident.end_time_ns if incident.end_time_ns is not None else 'unknown'}; "
            f"observations: {incident.occurrences}"
        )
        line(f"  Observed: {incident.explanation}")
        for key, value in incident.observations.items():
            line(f"  {key}: {value}")
        for evidence in incident.evidence:
            line(
                f"  Evidence: message #{evidence.message_index}, channel {evidence.channel_id}, "
                f"topic {evidence.topic}, sequence {evidence.sequence}, "
                f"log ns {evidence.log_time_ns}, publish ns {evidence.publish_time_ns}, "
                f"field {evidence.field_path or '(message)'}"
            )
        for limitation in incident.limitations:
            line(f"  Limitation: {limitation}")
        context = incident.log_context
        if context is not None:
            line(
                f"  Related log context (time proximity only; not a verified cause): "
                f"{context.availability}"
            )
            line(
                f"  Log-time window ns: {context.window_start_time_ns} .. "
                f"{context.window_end_time_ns}; matching: {context.matching_log_count}; "
                f"omitted by limit: {context.omitted_log_count}"
            )
            for entry in context.logs:
                line(f"    {entry.level_name} [{entry.logger}]: {entry.message}")
                line(
                    f"    Source stamp ns: {entry.stamp_time_ns}; "
                    f"source: {entry.file}:{entry.line} ({entry.function})"
                )
                ref = entry.evidence
                line(
                    f"    Context reference: message #{ref.message_index}, "
                    f"channel {ref.channel_id}, "
                    f"topic {ref.topic}, sequence {ref.sequence}, log ns {ref.log_time_ns}, "
                    f"publish ns {ref.publish_time_ns}, field {ref.field_path}"
                )
            for limitation in context.limitations:
                line(f"  Context limitation: {limitation}")
        for step in incident.recommended_steps:
            line(f"  Verify: {step}")
    line("Coverage / insufficient evidence")
    for issue in report.coverage:
        line(f"  {issue.code} (count {issue.count}): {issue.message}")
    for limitation in report.limitations:
        line(f"  {limitation}")


def json_report(report: Report) -> str:
    # ASCII escapes preserve Unicode even when stdout uses a Windows legacy code page.
    return report.model_dump_json(indent=2, ensure_ascii=True)
