import json

import pytest
from mcap.writer import CompressionType
from mcap.writer import Writer as RawWriter
from mcap_ros2.writer import Writer
from rich.console import Console
from typer.testing import CliRunner

from robotcopilot.analysis import analyze
from robotcopilot.cli import app
from robotcopilot.models import AnalysisConfig, Report
from robotcopilot.reporting import json_report, print_report
from robotcopilot.sample import BASE_TIME_NS, DIAGNOSTIC_SCHEMA, LOG_SCHEMA, diagnostic_message

SECOND = 10**9


def log_message(level=40, text="BT file not found: missing.xml", logger="bt_navigator", stamp=123):
    return {
        "stamp": {"sec": stamp // SECOND, "nanosec": stamp % SECOND},
        "level": level,
        "name": logger,
        "msg": text,
        "file": "navigate_to_pose.cpp",
        "function": "goalReceived",
        "line": 97,
    }


@pytest.fixture
def log_bag(tmp_path):
    def write(
        logs=(), levels=(2,), offsets=None, topic="/rosout", datatype="rcl_interfaces/msg/Log"
    ):
        path = tmp_path / "context.mcap"
        with path.open("wb") as stream, Writer(stream, compression=CompressionType.NONE) as writer:
            diag = writer.register_msgdef("diagnostic_msgs/msg/DiagnosticArray", DIAGNOSTIC_SCHEMA)
            for index, level in enumerate(levels):
                t = BASE_TIME_NS + (offsets[index] if offsets else index * SECOND)
                writer.write_message(
                    "/diagnostics", diag, diagnostic_message(level, t), log_time=t, sequence=index
                )
            schema = writer.register_msgdef(datatype, LOG_SCHEMA)
            for sequence, (delta, message) in enumerate(logs):
                t = BASE_TIME_NS + delta
                writer.write_message(
                    topic, schema, message, log_time=t, publish_time=t - 17, sequence=sequence
                )
        return path

    return write


def test_context_has_structured_fields_and_separate_exact_references(log_bag):
    path = log_bag(
        [
            (-1, log_message(20)),
            (-100, log_message()),
            (200, log_message(30, "Unrelated warning", "other_node")),
        ]
    )
    report = analyze(path)
    incident = report.incidents[0]
    context = incident.log_context
    assert context.association == "time_proximity_only" and context.availability == "available"
    assert len(incident.evidence) == 1 and incident.hypotheses == []
    assert context.matching_log_count == 2
    assert [entry.level_name for entry in context.logs] == ["ERROR", "WARN"]
    entry = context.logs[0]
    assert entry.logger == "bt_navigator" and entry.stamp_time_ns == 123
    assert entry.file == "navigate_to_pose.cpp" and entry.function == "goalReceived"
    assert entry.line == 97 and entry.message.startswith("BT file not found")
    assert entry.evidence.message_index == 3 and entry.evidence.field_path == "msg"
    assert entry.evidence.publish_time_ns == BASE_TIME_NS - 117
    assert entry.evidence.topic == "/rosout" and entry.evidence.sequence == 1


def test_window_boundaries_use_log_time_and_exact_nanoseconds(log_bag):
    path = log_bag(
        [
            (delta, log_message(stamp=0))
            for delta in (-5 * SECOND - 1, -5 * SECOND, 5 * SECOND, 5 * SECOND + 1)
        ]
    )
    context = analyze(path).incidents[0].log_context
    assert [e.evidence.log_time_ns for e in context.logs] == [
        BASE_TIME_NS - 5 * SECOND,
        BASE_TIME_NS + 5 * SECOND,
    ]
    assert context.window_start_time_ns == BASE_TIME_NS - 5 * SECOND
    assert context.window_end_time_ns == BASE_TIME_NS + 5 * SECOND


def test_nearest_limit_then_chronological_output_and_omission_count(log_bag):
    path = log_bag(
        [
            (delta, log_message(text=str(delta)))
            for delta in (-4 * SECOND, SECOND, -SECOND, 4 * SECOND, 0)
        ]
    )
    config = AnalysisConfig(max_context_logs=3)
    context = analyze(path, config).incidents[0].log_context
    assert [e.message for e in context.logs] == [str(-SECOND), "0", str(SECOND)]
    assert context.matching_log_count == 5 and context.omitted_log_count == 2
    assert json_report(analyze(path, config)) == json_report(analyze(path, config))


def test_equal_timestamp_limit_is_deterministic_by_physical_message_order(log_bag):
    path = log_bag([(0, log_message(text=str(i))) for i in range(5)])
    context = analyze(path, AnalysisConfig(max_context_logs=2)).incidents[0].log_context
    assert [e.message for e in context.logs] == ["0", "1"]


def test_long_incident_does_not_pull_in_distant_end_time_logs(log_bag):
    path = log_bag(
        [(99 * SECOND, log_message())], levels=(2, 2, 0), offsets=(0, 100 * SECOND, 101 * SECOND)
    )
    incident = analyze(path).incidents[0]
    assert incident.occurrences == 2 and incident.end_time_ns == BASE_TIME_NS + 101 * SECOND
    assert not incident.log_context.logs


def test_logs_alone_never_create_an_incident(log_bag):
    report = analyze(
        log_bag([(0, log_message(30)), (1, log_message(40)), (2, log_message(50))], levels=())
    )
    assert not report.incidents
    assert report.recording.channels[0].decoded_message_count == 3


def test_missing_logs_explicitly_unavailable(diagnostic_bag):
    report = analyze(diagnostic_bag())
    assert report.incidents[0].log_context.availability == "unavailable"
    assert "log_context_unavailable:/rosout" in {i.code for i in report.coverage}


def test_info_only_is_available_with_no_qualifying_matches(log_bag):
    report = analyze(log_bag([(0, log_message(20))]))
    context = report.incidents[0].log_context
    assert context.availability == "available" and not context.logs
    assert report.recording.channels[1].decoded_message_count == 1


def test_custom_warn_or_higher_level_is_preserved(log_bag):
    context = analyze(log_bag([(0, log_message(35))])).incidents[0].log_context
    assert context.logs[0].level == 35 and context.logs[0].level_name == "LEVEL_35"


@pytest.mark.parametrize("datatype", ["rcl_interfaces/msg/Log", "rcl_interfaces/Log"])
def test_configured_remapped_log_topic_and_aliases(log_bag, datatype):
    path = log_bag([(0, log_message())], topic="/robot/rosout", datatype=datatype)
    assert not analyze(path).incidents[0].log_context.logs
    report = analyze(path, AnalysisConfig(log_topics=["/robot/rosout"]))
    assert report.incidents[0].log_context.logs[0].evidence.schema_name == datatype


def test_one_missing_configured_topic_marks_context_partial(log_bag):
    report = analyze(
        log_bag([(0, log_message())]), AnalysisConfig(log_topics=["/rosout", "/other"])
    )
    assert report.incidents[0].log_context.availability == "partial"
    assert report.incidents[0].log_context.matching_log_count == 1


def test_decode_loss_marks_context_partial_without_altering_incident(log_bag):
    bad = log_message()
    bad["stamp"]["nanosec"] = SECOND
    report = analyze(log_bag([(-1, log_message()), (0, bad)]))
    incident = report.incidents[0]
    assert incident.log_context.availability == "partial"
    assert incident.log_context.matching_log_count == 1
    assert len(incident.evidence) == 1 and incident.hypotheses == []
    assert report.recording.channels[1].decode_error_count == 1


def test_fractional_window_retains_nanosecond_precision(log_bag):
    path = log_bag([(delta, log_message()) for delta in (-2, -1, 1, 2)])
    context = analyze(path, AnalysisConfig(context_window_seconds=1e-9)).incidents[0].log_context
    assert [e.evidence.log_time_ns for e in context.logs] == [BASE_TIME_NS - 1, BASE_TIME_NS + 1]


def test_disabled_context_does_not_decode_or_attach_logs(log_bag):
    report = analyze(log_bag([(0, log_message())]), AnalysisConfig(context_window_seconds=0))
    assert report.incidents[0].log_context.availability == "disabled"
    assert not report.incidents[0].log_context.logs
    assert report.recording.channels[1].decoded_message_count == 0
    assert "log_context_disabled" in {i.code for i in report.coverage}


@pytest.mark.parametrize("encoding,data", [("ros2msg", b"bad cdr"), ("ros2idl", b"idl")])
def test_malformed_or_unsupported_logs_are_unavailable_not_incident_evidence(
    tmp_path, encoding, data
):
    path = tmp_path / "unsupported-logs.mcap"
    from mcap.records import Message
    from mcap.stream_reader import StreamReader

    from robotcopilot.sample import generate_sample

    original = tmp_path / "diag.mcap"
    generate_sample(original)
    with original.open("rb") as stream:
        diag_messages = [r for r in StreamReader(stream).records if isinstance(r, Message)]
    with path.open("wb") as stream:
        writer = RawWriter(stream)
        writer.start(profile="ros2")
        sid = writer.register_schema(
            "diagnostic_msgs/msg/DiagnosticArray", "ros2msg", DIAGNOSTIC_SCHEMA.encode()
        )
        cid = writer.register_channel("/diagnostics", "cdr", sid)
        for message in diag_messages:
            writer.add_message(cid, message.log_time, message.data, message.publish_time)
        sid = writer.register_schema("rcl_interfaces/msg/Log", encoding, LOG_SCHEMA.encode())
        cid = writer.register_channel("/rosout", "cdr", sid)
        writer.add_message(cid, BASE_TIME_NS + SECOND, data, BASE_TIME_NS + SECOND)
        writer.finish()
    report = analyze(path)
    assert len(report.incidents) == 1 and len(report.incidents[0].evidence) == 3
    assert report.incidents[0].log_context.availability == "unavailable"
    assert any(
        i.code in ("decode_error", "unsupported_encoding") and i.first_evidence.topic == "/rosout"
        for i in report.coverage
        if i.first_evidence
    )


def test_log_observations_count_toward_resource_limit(log_bag):
    path = log_bag([(0, log_message()) for _ in range(5)], levels=())
    from robotcopilot.ingestion import RecordingError

    with pytest.raises(RecordingError, match="observation limit"):
        analyze(path, AnalysisConfig(max_events=2))


def test_json_and_terminal_keep_untrusted_log_text_literal(log_bag):
    message = log_message(text="[bold]故障🤖[/bold]\x1b[2J\nforged", logger="[red]node[/red]")
    report = analyze(log_bag([(0, message)]))
    serialized = json_report(report)
    assert serialized.isascii() and Report.model_validate_json(serialized) == report
    console = Console(record=True, color_system=None, width=120)
    print_report(report, console)
    output = console.export_text()
    assert "[bold]故障🤖[/bold]" in output and "[red]node[/red]" in output
    assert "\\x1b[2J\\x0aforged" in output and "\x1b" not in output
    assert "time proximity only; not a verified cause" in output
    assert "message #2" in output and "navigate_to_pose.cpp:97" in output


@pytest.mark.parametrize(
    "args",
    [
        ["--context-window", "-1"],
        ["--context-window", "nan"],
        ["--context-window", "inf"],
        ["--context-window", "3601"],
        ["--max-context-logs", "0"],
        ["--max-context-logs", "1001"],
        ["--log-topic", "relative"],
    ],
)
def test_context_cli_rejects_invalid_configuration(diagnostic_bag, args):
    assert CliRunner().invoke(app, ["analyze", str(diagnostic_bag()), *args]).exit_code == 2


def test_context_cli_controls_are_exported_and_applied(log_bag):
    path = log_bag([(1, log_message()), (2, log_message())], topic="/remapped")
    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(path),
            "--format",
            "json",
            "--log-topic",
            "/remapped",
            "--max-context-logs",
            "1",
            "--context-window",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["report_version"] == "0.2" and report["tool_version"] == "0.2.0"
    assert report["incidents"][0]["log_context"]["omitted_log_count"] == 1


@pytest.mark.parametrize("malformed", [False, True])
def test_mixed_topic_log_data_never_resets_diagnostics_or_changes_findings(
    log_bag, tmp_path, malformed
):
    from mcap.reader import make_reader

    original = log_bag([(1, log_message())])
    with original.open("rb") as stream:
        diagnostic_cdr = next(make_reader(stream).iter_messages(topics=["/diagnostics"]))[2].data
    with original.open("rb") as stream:
        log_cdr = next(make_reader(stream).iter_messages(topics=["/rosout"]))[2].data
    path = tmp_path / "mixed-topic.mcap"
    with path.open("wb") as stream:
        writer = RawWriter(stream)
        writer.start(profile="ros2")
        diag = writer.register_schema(
            "diagnostic_msgs/msg/DiagnosticArray", "ros2msg", DIAGNOSTIC_SCHEMA.encode()
        )
        log = writer.register_schema("rcl_interfaces/msg/Log", "ros2msg", LOG_SCHEMA.encode())
        diagnostic_channel = writer.register_channel("/mixed", "cdr", diag)
        log_channel = writer.register_channel("/mixed", "cdr", log)
        writer.add_message(diagnostic_channel, BASE_TIME_NS, diagnostic_cdr, BASE_TIME_NS)
        writer.add_message(
            log_channel, BASE_TIME_NS + 1, b"bad cdr" if malformed else log_cdr, BASE_TIME_NS + 1
        )
        writer.add_message(diagnostic_channel, BASE_TIME_NS + 2, diagnostic_cdr, BASE_TIME_NS + 2)
        writer.finish()
    enabled = analyze(path, AnalysisConfig(log_topics=["/mixed"]))
    disabled = analyze(path, AnalysisConfig(log_topics=["/mixed"], context_window_seconds=0))
    assert len(enabled.incidents) == len(disabled.incidents) == 1
    assert enabled.incidents[0].occurrences == 2
    assert enabled.incidents[0].model_dump(exclude={"log_context"}) == (
        disabled.incidents[0].model_dump(exclude={"log_context"})
    )
