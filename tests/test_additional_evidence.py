from mcap.writer import CompressionType
from mcap_ros2.writer import Writer

from robotcopilot.analysis import analyze
from robotcopilot.ingestion import DIAGNOSTIC_TYPE, STATUS_TYPE
from robotcopilot.models import AnalysisConfig
from robotcopilot.reporting import json_report
from robotcopilot.sample import DIAGNOSTIC_SCHEMA, STATUS_SCHEMA, diagnostic_message


def test_two_part_ros2_schema_names_are_supported(tmp_path):
    path = tmp_path / "aliases.mcap"
    with path.open("wb") as stream, Writer(stream) as writer:
        schema = writer.register_msgdef("diagnostic_msgs/DiagnosticArray", DIAGNOSTIC_SCHEMA)
        writer.write_message("/diagnostics", schema, diagnostic_message(2, 0), log_time=0)
        status_schema = writer.register_msgdef("action_msgs/GoalStatusArray", STATUS_SCHEMA)
        writer.write_message(
            "/navigation/status",
            status_schema,
            {
                "status_list": [
                    {
                        "goal_info": {
                            "goal_id": {"uuid": [1] * 16},
                            "stamp": {"sec": 0, "nanosec": 0},
                        },
                        "status": 6,
                    }
                ]
            },
            log_time=1,
        )
    report = analyze(path, AnalysisConfig(navigation_status_topics=["/navigation/status"]))
    assert [i.category for i in report.incidents] == ["diagnostic", "navigation"]
    assert all(c.decoded_message_count == 1 for c in report.recording.channels)
    assert report.recording.channels[1].schema_name == "action_msgs/GoalStatusArray"


def test_json_preserves_unicode_through_legacy_stdout_encoding(diagnostic_bag):
    import json

    report = analyze(diagnostic_bag((2,), components=("电机-🤖",)))
    serialized = json_report(report)
    assert serialized.isascii()
    decoded = json.loads(serialized.encode("cp1252").decode("cp1252"))
    assert decoded["incidents"][0]["component"] == "电机-🤖"


def test_status_array_entry_order_is_preserved_in_tied_timeline(tmp_path):
    path = tmp_path / "array-order.mcap"
    message = diagnostic_message(1, 0)
    message["status"] = [dict(message["status"][0], name=f"component-{i}") for i in range(12)]
    with path.open("wb") as stream, Writer(stream) as writer:
        schema = writer.register_msgdef(DIAGNOSTIC_TYPE, DIAGNOSTIC_SCHEMA)
        writer.write_message("/diagnostics", schema, message, log_time=0)
    assert [i.evidence[0].field_path for i in analyze(path).incidents] == [
        f"status[{i}]" for i in range(12)
    ]


def test_empty_diagnostic_array_reports_insufficient_component_evidence(tmp_path):
    path = tmp_path / "no-components.mcap"
    message = diagnostic_message(0, 0)
    message["status"] = []
    with path.open("wb") as stream, Writer(stream) as writer:
        schema = writer.register_msgdef(DIAGNOSTIC_TYPE, DIAGNOSTIC_SCHEMA)
        writer.write_message("/diagnostics", schema, message, log_time=0)
    report = analyze(path)
    assert not report.incidents
    issue = next(i for i in report.coverage if i.code == "empty_diagnostic_array")
    assert issue.first_evidence.log_time_ns == 0
    assert report.recording.start_time_ns == report.recording.end_time_ns == 0


def test_hardware_and_topic_are_part_of_component_identity(tmp_path):
    path = tmp_path / "components.mcap"
    with path.open("wb") as stream, Writer(stream) as writer:
        schema = writer.register_msgdef(DIAGNOSTIC_TYPE, DIAGNOSTIC_SCHEMA)
        for t, (topic, hardware, level) in enumerate(
            [
                ("/a", "one", 2),
                ("/a", "two", 2),
                ("/b", "one", 2),
                ("/a", "one", 0),
            ]
        ):
            message = diagnostic_message(level, t)
            message["status"][0]["hardware_id"] = hardware
            writer.write_message(topic, schema, message, log_time=t)
    incidents = analyze(path).incidents
    assert len(incidents) == 3
    assert [i.end_time_ns for i in incidents] == [3, None, None]
    assert len({i.id for i in incidents}) == 3


def test_unknown_diagnostic_level_is_not_a_fabricated_incident(tmp_path):
    path = tmp_path / "invalid-level.mcap"
    message = diagnostic_message(2, 0)
    message["status"][0]["level"] = 99
    with path.open("wb") as stream, Writer(stream) as writer:
        schema = writer.register_msgdef(DIAGNOSTIC_TYPE, DIAGNOSTIC_SCHEMA)
        writer.write_message("/diagnostics", schema, message, log_time=0)
    report = analyze(path)
    assert not report.incidents
    assert report.recording.channels[0].decode_error_count == 1


def test_distinct_aborted_goals_create_distinct_findings(tmp_path):
    path = tmp_path / "two-aborts.mcap"
    topic = "/navigate_to_pose/_action/status"
    with path.open("wb") as stream, Writer(stream, compression=CompressionType.NONE) as writer:
        schema = writer.register_msgdef(STATUS_TYPE, STATUS_SCHEMA)
        entries = [
            {
                "goal_info": {"goal_id": {"uuid": [i] * 16}, "stamp": {"sec": 0, "nanosec": i}},
                "status": 6,
            }
            for i in (1, 2)
        ]
        for t in (1, 2):
            writer.write_message(topic, schema, {"status_list": entries}, log_time=t)
    report = analyze(path, AnalysisConfig(navigation_status_topics=[topic]))
    assert len(report.incidents) == 2
    assert {i.observations["goal_id"] for i in report.incidents} == {"01" * 16, "02" * 16}
