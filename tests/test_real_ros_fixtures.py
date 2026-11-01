"""Regression on saved native recordings; this test run does not launch ROS."""

import json
import runpy
import shutil
from pathlib import Path

import pytest
from mcap.records import Message
from mcap.stream_reader import StreamReader
from mcap.writer import Writer

from robotcopilot.analysis import analyze
from robotcopilot.models import AnalysisConfig

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/ros2_jazzy"
verify = runpy.run_path(str(ROOT / "scripts/integration/verify_capture.py"))["verify"]


def test_native_rosbag2_diagnostics_have_exact_publisher_evidence():
    folder = FIXTURES / "diagnostics"
    truth = json.loads((folder / "ground-truth.json").read_text())
    report = analyze(folder / "recording.mcap")
    assert report.recording.message_count == 6
    assert report.recording.library.startswith("libmcap")
    assert [i.observations["level"] for i in report.incidents] == [1, 2]
    assert [i.occurrences for i in report.incidents] == [2, 2]
    assert report.incidents[1].observations["header_time_ns"] == truth["sent"][3]["header_time_ns"]


def test_native_nav2_abort_matches_uuid_and_ignores_zero_result_error_code():
    folder = FIXTURES / "navigation"
    truth = json.loads((folder / "ground-truth.json").read_text())
    report = analyze(
        folder / "recording.mcap",
        AnalysisConfig(
            navigation_status_topics=[truth["topic"]],
        ),
    )
    assert report.recording.message_count == 7
    assert report.recording.channels[0].decoded_message_count == 7
    assert len(report.incidents) == 1
    abort = next(g for g in truth["goals"] if g["status"] == 6)
    assert abort["accepted"] and abort["error_code"] == 0
    assert report.incidents[0].observations["goal_id"] == abort["goal_id"]
    assert report.incidents[0].hypotheses == []


def test_schema_less_native_nav2_cli_capture_is_unknown_not_a_false_negative_verdict():
    folder = FIXTURES / "navigation"
    truth = json.loads((folder / "ground-truth.json").read_text())
    report = analyze(
        folder / "navigation/raw.mcap",
        AnalysisConfig(
            navigation_status_topics=[truth["topic"]],
        ),
    )
    assert report.recording.message_count == 7 and not report.incidents
    assert report.recording.channels[0].skipped_message_count == 7
    assert "unsupported_encoding" in {c.code for c in report.coverage}
    assert f"navigation_unavailable:{truth['topic']}" in {c.code for c in report.coverage}


def test_native_companion_payloads_are_identical_to_cli_capture(tmp_path):
    folder = tmp_path / "navigation"
    shutil.copytree(FIXTURES / "navigation", folder)
    result = verify(folder)
    assert result["payload_identity_verified"]
    assert result["status"] == "passed"


def test_verifier_rejects_companion_with_different_publish_timestamps(tmp_path):
    folder = tmp_path / "navigation"
    shutil.copytree(FIXTURES / "navigation", folder)
    # Keep valid CDR, counts and container structure, but alter a source timestamp.
    path = folder / "navigation/raw.mcap"
    with path.open("rb") as stream:
        messages = [r for r in StreamReader(stream).records if isinstance(r, Message)]
    with path.open("wb") as stream:
        writer = Writer(stream)
        writer.start(profile="ros2")
        schema = writer.register_schema("action_msgs/msg/GoalStatusArray", "", b"")
        channel = writer.register_channel("/navigate_to_pose/_action/status", "cdr", schema)
        for message in messages:
            writer.add_message(channel, message.log_time, message.data, message.publish_time + 1)
        writer.finish()
    with pytest.raises(AssertionError, match="CDR bytes/publish timestamps"):
        verify(folder)
