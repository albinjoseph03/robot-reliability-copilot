"""Analyze a real integration capture and verify observations against saved ground truth.

Runs with the analyzer environment, independent of ROS's system Python.
Returns nonzero for absent evidence, lost messages, or failed negative controls.
"""

import argparse
import json
from pathlib import Path

from mcap.records import Message
from mcap.stream_reader import StreamReader

from robotcopilot.analysis import analyze
from robotcopilot.models import AnalysisConfig
from robotcopilot.reporting import json_report


def payload_identity(path):
    with path.open("rb") as stream:
        messages = []
        for record in StreamReader(
            stream, validate_crcs=True, record_size_limit=64 * 1024**2
        ).records:
            if isinstance(record, Message):
                messages.append((record.publish_time, record.data))
                if len(messages) > 1_000_000:
                    raise ValueError("Integration message limit exceeded.")
        return messages


def verify(folder: Path) -> dict:
    truth = json.loads((folder / "ground-truth.json").read_text(encoding="utf-8"))
    if truth["kind"] not in ("rosbag2_diagnostics", "nav2_gazebo"):
        raise ValueError("Unsupported integration manifest kind.")
    relative_files = truth["metadata"]["relative_file_paths"]
    if len(relative_files) != 1:
        raise ValueError("Integration verification requires exactly one MCAP.")
    relative = Path(relative_files[0])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Manifest recording path must stay inside the capture bag directory.")
    path = folder / truth["bag"] / relative
    if not path.resolve().is_relative_to(folder.resolve()):
        raise ValueError("Manifest recording path escapes the capture directory.")
    # This verifier consumes local harness manifests, never labels arbitrary external data.
    navigation = truth["kind"] == "nav2_gazebo"
    config = AnalysisConfig(navigation_status_topics=[truth["topic"]] if navigation else [])
    report = analyze(path, config)
    if report.recording.message_count != truth["metadata"]["message_count"]:
        raise AssertionError("Analyzer count differs from rosbag2 metadata.")
    if "raw_cli_metadata" in truth and (
        truth["raw_cli_metadata"]["message_count"] != report.recording.message_count
    ):
        raise AssertionError("Native and CLI recorder message counts differ.")
    if "raw_cli_metadata" in truth:
        raw_files = truth["raw_cli_metadata"]["relative_file_paths"]
        if len(raw_files) != 1:
            raise ValueError("Expected one raw CLI MCAP.")
        raw_path = folder / "navigation" / raw_files[0]
        if not raw_path.resolve().is_relative_to(folder.resolve()):
            raise ValueError("Raw CLI recording path escapes capture directory.")
        if payload_identity(path) != payload_identity(raw_path):
            raise AssertionError(
                "Companion CDR bytes/publish timestamps differ from CLI recording."
            )
    channels = [c for c in report.recording.channels if c.topic == truth["topic"]]
    if not channels or any(c.skipped_message_count or c.decode_error_count for c in channels):
        raise AssertionError("Expected test topic was absent or not fully decoded.")
    if navigation:
        goals = truth["goals"]
        if not all(goal["accepted"] for goal in goals):
            raise AssertionError("Ground truth includes rejected goals.")
        expected_statuses = {"success": 4, "missing_behavior_tree": 6, "cancellation": 5}
        if {g["scenario"]: g["status"] for g in goals} != expected_statuses:
            raise AssertionError("Missing successful, aborted or canceled client-result control.")
        expected = {g["goal_id"] for g in goals if g["status"] == 6}
        actual = {i.observations["goal_id"] for i in report.incidents if i.category == "navigation"}
        if actual != expected or len(report.incidents) != len(expected):
            raise AssertionError(
                f"Abort evidence differs from client results: {actual} vs {expected}"
            )
    else:
        sent = truth["sent"]
        if report.recording.message_count != len(sent):
            raise AssertionError(
                "Not all published diagnostic messages were recorded exactly once."
            )
        if [i.observations["level"] for i in report.incidents] != [1, 2]:
            raise AssertionError("Expected one WARN episode followed by one ERROR episode.")
        for incident, index in zip(report.incidents, (1, 3), strict=True):
            if incident.occurrences != 2 or incident.end_time_ns is None:
                raise AssertionError("Repeated severity or observed transition is missing.")
            if incident.observations["header_time_ns"] != sent[index]["header_time_ns"]:
                raise AssertionError("Incident header timestamp differs from publisher truth.")
            if incident.evidence[0].message_index != index + 1:
                raise AssertionError("Incident reference differs from publisher ordering.")
    if any(i.hypotheses for i in report.incidents):
        raise AssertionError("Deterministic report must not invent hypotheses.")
    with (folder / "report.json").open("x", encoding="utf-8") as stream:
        stream.write(json_report(report) + "\n")
    return {
        "kind": truth["kind"],
        "status": "passed",
        "recording_sha256": report.recording.sha256,
        "message_count": report.recording.message_count,
        "incident_ids": [i.id for i in report.incidents],
        "payload_identity_verified": "raw_cli_metadata" in truth,
        "checked": "rosbag2 counts, decoding, ground-truth timestamps/UUIDs and negative controls",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    result = verify(args.capture)
    with (args.capture / "verification.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
