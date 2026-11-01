import hashlib
import json
import struct
from pathlib import Path

import pytest
from mcap.writer import CompressionType
from mcap.writer import Writer as RawWriter
from mcap_ros2.writer import Writer
from pydantic import ValidationError
from rich.console import Console
from typer.testing import CliRunner

from robotcopilot.analysis import analyze
from robotcopilot.cli import app
from robotcopilot.ingestion import DIAGNOSTIC_TYPE, STATUS_TYPE, RecordingError
from robotcopilot.models import AnalysisConfig, Report
from robotcopilot.reporting import json_report, print_report
from robotcopilot.sample import (
    BASE_TIME_NS,
    DIAGNOSTIC_SCHEMA,
    STATUS_SCHEMA,
    generate_sample,
)

runner = CliRunner()


def test_first_success_criterion_and_exact_evidence(tmp_path):
    path = tmp_path / "sample.mcap"
    generate_sample(path)
    result = runner.invoke(app, ["analyze", str(path)])
    assert result.exit_code == 0, result.output
    assert "ERROR" in result.output
    assert "message #2" in result.output
    report = analyze(path)
    assert report.recording.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report.recording.message_count == 4
    assert len(report.incidents) == 1
    incident = report.incidents[0]
    assert incident.start_time_ns == BASE_TIME_NS + 10**9
    assert incident.end_time_ns == BASE_TIME_NS + 3 * 10**9
    assert incident.occurrences == 2
    assert [r.message_index for r in incident.evidence] == [2, 3, 4]
    first = incident.evidence[0]
    assert first.topic == "/diagnostics" and first.field_path == "status[0]"
    assert first.sequence == 1 and first.channel_id == 1
    assert first.schema_name == DIAGNOSTIC_TYPE
    assert first.publish_time_ns == first.log_time_ns
    assert incident.hypotheses == []
    assert incident.observations["values"] == [("temperature_c", "95")]
    assert incident.detector and incident.limitations and incident.recommended_steps


def test_repeated_warnings_are_one_unresolved_episode(diagnostic_bag):
    report = analyze(diagnostic_bag((1,) * 50))
    assert len(report.incidents) == 1
    incident = report.incidents[0]
    assert incident.severity == "warning" and incident.occurrences == 50
    assert incident.end_time_ns is None
    assert len(incident.evidence) == 2
    assert incident.last_observed_time_ns == BASE_TIME_NS + 49 * 10**9


def test_severity_transitions_and_stale_are_distinct(diagnostic_bag):
    report = analyze(diagnostic_bag((0, 1, 1, 2, 2, 3, 0, 2)))
    assert [i.observations["level"] for i in report.incidents] == [1, 2, 3, 2]
    assert [i.severity for i in report.incidents] == ["warning", "error", "warning", "error"]
    assert [i.end_time_ns for i in report.incidents] == [
        BASE_TIME_NS + 3 * 10**9,
        BASE_TIME_NS + 5 * 10**9,
        BASE_TIME_NS + 6 * 10**9,
        None,
    ]


def test_components_do_not_close_each_others_incidents(diagnostic_bag):
    report = analyze(diagnostic_bag((2, 0, 2), components=("motor", "battery", "motor")))
    assert len(report.incidents) == 1
    assert report.incidents[0].occurrences == 2
    assert report.incidents[0].end_time_ns is None


def test_physical_order_is_sorted_but_message_references_preserved(diagnostic_bag):
    report = analyze(diagnostic_bag((0, 2, 1), offsets=(30, 20, 10)))
    assert [i.observations["level"] for i in report.incidents] == [1, 2]
    assert report.incidents[0].evidence[0].message_index == 3
    assert report.incidents[1].evidence[0].message_index == 2
    assert report.incidents[1].end_time_ns == BASE_TIME_NS + 30
    assert report.incidents[0].evidence[0].publish_time_ns == BASE_TIME_NS + 10 - 123
    assert report.recording.start_time_ns == BASE_TIME_NS + 10


def test_equal_timestamps_follow_physical_order(diagnostic_bag):
    report = analyze(diagnostic_bag((1, 2, 0), offsets=(7, 7, 7)))
    assert [i.observations["level"] for i in report.incidents] == [1, 2]
    assert all(i.start_time_ns == i.end_time_ns for i in report.incidents)


@pytest.mark.parametrize("compression", [CompressionType.ZSTD, CompressionType.LZ4])
def test_compressed_recordings(diagnostic_bag, compression):
    assert len(analyze(diagnostic_bag(compression=compression)).incidents) == 1


def test_empty_recording_is_unknown_not_healthy(tmp_path):
    path = tmp_path / "empty.mcap"
    with path.open("wb") as stream:
        writer = RawWriter(stream)
        writer.start(profile="ros2")
        writer.finish()
    report = analyze(path)
    assert report.recording.message_count == 0 and not report.incidents
    assert report.recording.start_time_ns is None
    assert "no_diagnostics" in {i.code for i in report.coverage}
    assert "not a robot health verdict" in report.summary


@pytest.mark.parametrize("encoding", ["ros2idl", "jsonschema", "ros2msg"])
def test_unsupported_schema_or_type_is_counted(tmp_path, encoding):
    path = tmp_path / "unsupported.mcap"
    with path.open("wb") as stream:
        writer = RawWriter(stream)
        writer.start(profile="ros2")
        schema = writer.register_schema(
            DIAGNOSTIC_TYPE if encoding != "ros2msg" else "custom_msgs/msg/Thing",
            encoding,
            b"{}",
        )
        channel = writer.register_channel("/unknown", "cdr", schema)
        writer.add_message(channel, 12, b"unsupported", 11)
        writer.finish()
    report = analyze(path)
    ci = report.recording.channels[0]
    assert ci.message_count == ci.skipped_message_count == 1
    assert ci.schema_encoding == encoding and not report.incidents
    assert any(i.code == "no_diagnostics" for i in report.coverage)


def test_unknown_schema_id_is_not_a_crash(tmp_path):
    path = tmp_path / "unknown.mcap"
    with path.open("wb") as stream:
        writer = RawWriter(stream)
        writer.start(profile="ros2")
        channel = writer.register_channel("/unknown", "cdr", 999)
        writer.add_message(channel, 10, b"", 10)
        writer.finish()
    assert analyze(path).recording.channels[0].schema_name is None


@pytest.mark.parametrize("contents", [b"", b"not MCAP", b"\x89MCAP0\r\n"])
def test_corrupted_files_fail_cleanly(tmp_path, contents):
    path = tmp_path / "bad.mcap"
    path.write_bytes(contents)
    with pytest.raises(RecordingError):
        analyze(path)
    result = runner.invoke(app, ["analyze", str(path), "--format", "json"])
    assert result.exit_code == 1 and "Analysis failed:" in result.output
    assert "Traceback" not in result.output


def test_truncated_and_trailing_data_rejected(diagnostic_bag):
    path = diagnostic_bag()
    original = path.read_bytes()
    for altered in (original[:-10], original + b"trailing data"):
        path.write_bytes(altered)
        with pytest.raises(RecordingError):
            analyze(path)


def test_crc_corruption_rejected(diagnostic_bag):
    path = diagnostic_bag()
    data = path.read_bytes()
    assert b"synthetic overtemperature" in data
    path.write_bytes(data.replace(b"synthetic overtemperature", b"synthetic underpressure!!", 1))
    # Mutation preserves length; MCAP chunk CRC, not an invalid string length, must fail.
    assert len(path.read_bytes()) == len(data)
    with pytest.raises(RecordingError, match="CRC"):
        analyze(path)


def test_malformed_cdr_preserves_coverage_and_breaks_episode(tmp_path):
    path = tmp_path / "bad-cdr.mcap"
    with path.open("wb") as stream:
        writer = RawWriter(stream, compression=CompressionType.NONE)
        writer.start(profile="ros2")
        schema = writer.register_schema(DIAGNOSTIC_TYPE, "ros2msg", DIAGNOSTIC_SCHEMA.encode())
        channel = writer.register_channel("/diagnostics", "cdr", schema)
        writer.add_message(channel, 10, manual_diagnostic_cdr(), 10)
        writer.add_message(channel, 20, b"bad cdr", 20)
        writer.add_message(channel, 30, manual_diagnostic_cdr(), 30)
        writer.finish()
    report = analyze(path)
    assert len(report.incidents) == 2
    assert all(i.end_time_ns is None for i in report.incidents)
    assert report.recording.channels[0].decode_error_count == 1
    issue = next(i for i in report.coverage if i.code == "decode_error")
    assert issue.first_evidence.message_index == 2


def test_no_summary_or_chunk_index_required(tmp_path):
    path = tmp_path / "unindexed.mcap"
    with path.open("wb") as stream:
        writer = RawWriter(
            stream,
            use_chunking=False,
            use_statistics=False,
            repeat_channels=False,
            repeat_schemas=False,
        )
        writer.start(profile="ros2")
        sid = writer.register_schema(DIAGNOSTIC_TYPE, "ros2msg", DIAGNOSTIC_SCHEMA.encode())
        channel = writer.register_channel("/diagnostics", "cdr", sid)
        writer.add_message(channel, 100, manual_diagnostic_cdr(), 100)
        writer.finish()
    assert analyze(path).incidents[0].severity == "error"


def manual_diagnostic_cdr():
    """Independent little-endian XCDR1 payload; no MCAP dynamic encoder involved."""
    payload = bytearray()

    def align(boundary):
        payload.extend(b"\0" * (-len(payload) % boundary))

    def uint32(value):
        align(4)
        payload.extend(struct.pack("<I", value))

    def string(value):
        data = value.encode() + b"\0"
        uint32(len(data))
        payload.extend(data)

    uint32(0)  # header stamp sec
    uint32(100)  # header stamp nanosec
    string("")
    uint32(1)  # status array count
    payload.append(2)  # ERROR
    string("independent_motor")
    string("independent error")
    string("test-hardware")
    uint32(0)  # no KeyValue entries
    return b"\x00\x01\x00\x00" + bytes(payload)


def navigation_bag(path: Path, statuses, topic="/navigate_to_pose/_action/status"):
    with path.open("wb") as stream, Writer(stream, compression=CompressionType.NONE) as writer:
        schema = writer.register_msgdef(STATUS_TYPE, STATUS_SCHEMA)
        for i, status in enumerate(statuses):
            writer.write_message(
                topic,
                schema,
                {
                    "status_list": [
                        {
                            "goal_info": {
                                "goal_id": {"uuid": list(range(16))},
                                "stamp": {"sec": 0, "nanosec": 0},
                            },
                            "status": status,
                        }
                    ],
                },
                log_time=10 + i,
                publish_time=10 + i,
            )
    return path


def test_navigation_abort_deduplicates_uuid_and_requires_context(tmp_path):
    topic = "/navigate_to_pose/_action/status"
    path = navigation_bag(tmp_path / "nav.mcap", [1, 2, 6, 6])
    assert not analyze(path).incidents
    report = analyze(path, AnalysisConfig(navigation_status_topics=[topic]))
    assert len(report.incidents) == 1
    incident = report.incidents[0]
    assert incident.category == "navigation" and incident.observations["status"] == 6
    assert incident.evidence[0].message_index == 3
    assert incident.observations["goal_id"] == bytes(range(16)).hex()


@pytest.mark.parametrize("status", [0, 1, 2, 3, 4, 5])
def test_other_navigation_statuses_are_not_failures(tmp_path, status):
    path = navigation_bag(tmp_path / "not-failed.mcap", [status])
    report = analyze(
        path, AnalysisConfig(navigation_status_topics=["/navigate_to_pose/_action/status"])
    )
    assert not report.incidents


def test_configured_gaps_use_exact_integer_intervals(diagnostic_bag):
    path = diagnostic_bag((0, 0, 0, 0), offsets=(0, 100_000_000, 400_000_000, 700_000_001))
    assert not analyze(path).incidents
    config = AnalysisConfig(expected_rates_hz={"/diagnostics": 10}, gap_factor=3)
    report = analyze(path, config)
    assert len(report.incidents) == 1
    incident = report.incidents[0]
    assert incident.category == "missing_telemetry"
    assert incident.observations["interval_ns"] == 300_000_001
    assert [r.message_index for r in incident.evidence] == [3, 4]


def test_absent_topics_are_insufficient_not_telemetry_failures(diagnostic_bag):
    report = analyze(
        diagnostic_bag((0,)),
        AnalysisConfig(
            expected_rates_hz={"/odom": 10},
            navigation_status_topics=["/missing/_action/status"],
        ),
    )
    assert not report.incidents
    assert {i.code for i in report.coverage} >= {
        "insufficient_telemetry:/odom",
        "navigation_unavailable:/missing/_action/status",
    }


@pytest.mark.parametrize(
    "options",
    [
        ["--expect-rate", "/odom=0"],
        ["--expect-rate", "/odom=nan"],
        ["--expect-rate", "/odom=inf"],
        ["--expect-rate", "bad"],
        ["--expect-rate", "odom=1"],
        ["--gap-factor", "1"],
        ["--gap-factor", "nan"],
        ["--navigation-status-topic", "relative"],
        ["--expect-rate", "/a=1", "--expect-rate", "/a=2"],
    ],
)
def test_invalid_configuration_is_usage_error(diagnostic_bag, options):
    result = runner.invoke(app, ["analyze", str(diagnostic_bag()), *options])
    assert result.exit_code == 2


def test_python_api_rejects_invalid_rates():
    with pytest.raises(ValidationError):
        AnalysisConfig(expected_rates_hz={"/x": -1})


@pytest.mark.parametrize("limit", ["--max-messages", "--max-events", "--max-record-bytes"])
def test_resource_limits_fail_without_partial_report(diagnostic_bag, limit):
    result = runner.invoke(app, ["analyze", str(diagnostic_bag()), limit, "1", "--format", "json"])
    assert result.exit_code == 1 and "limit" in result.output.lower()


def test_json_round_trip_cli_output_and_repeatability(diagnostic_bag, tmp_path):
    path = diagnostic_bag()
    output = tmp_path / "report.json"
    result = runner.invoke(app, ["analyze", str(path), "--format", "json", "--output", str(output)])
    assert result.exit_code == 0, result.output
    parsed = Report.model_validate_json(result.stdout)
    assert parsed == Report.model_validate_json(output.read_text(encoding="utf-8"))
    assert json.loads(result.stdout)["incidents"][0]["start_time_ns"] == BASE_TIME_NS + 10**9
    assert json_report(analyze(path)) == json_report(analyze(path))


def test_cli_cannot_overwrite_input_or_existing_output(diagnostic_bag, tmp_path):
    path = diagnostic_bag()
    original = path.read_bytes()
    assert runner.invoke(app, ["analyze", str(path), "--output", str(path)]).exit_code == 1
    assert path.read_bytes() == original
    assert runner.invoke(app, ["sample", str(path)]).exit_code == 1
    assert path.read_bytes() == original
    existing = tmp_path / "existing.json"
    existing.write_text("keep", encoding="utf-8")
    assert runner.invoke(app, ["analyze", str(path), "-o", str(existing)]).exit_code == 1
    assert existing.read_text() == "keep"


def test_terminal_telemetry_is_literal_and_control_sequences_are_escaped(diagnostic_bag):
    path = diagnostic_bag((2,), components=("[bold]motor[/bold]\x1b[2J\nforged",))
    console = Console(record=True, width=120, color_system=None)
    print_report(analyze(path), console)
    output = console.export_text()
    assert "[bold]motor[/bold]" in output
    assert "\\x1b[2J" in output and "\x1b" not in output


def test_cli_help_version_and_report_schema():
    assert runner.invoke(app, ["--help"]).exit_code == 0
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0 and "0.1.0" in result.output
    assert json.loads(runner.invoke(app, ["schema"]).output)["title"] == "Report"
