"""The verifier must reject inadequate ground truth; these are not live ROS tests."""

import json
import runpy
from pathlib import Path

import pytest

from robotcopilot.sample import BASE_TIME_NS

verify = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/integration/verify_capture.py")
)["verify"]


def manifest(path):
    return {
        "kind": "rosbag2_diagnostics",
        "bag": ".",
        "topic": "/diagnostics",
        "sent": [
            {"index": i, "level": level, "header_time_ns": BASE_TIME_NS + i * 10**9}
            for i, level in enumerate((0, 1, 1, 2, 2, 0))
        ],
        "metadata": {"relative_file_paths": [path.name], "message_count": 6},
    }


def save(folder, truth):
    (folder / "ground-truth.json").write_text(json.dumps(truth), encoding="utf-8")


def test_integration_verifier_matches_complete_diagnostic_evidence(diagnostic_bag):
    path = diagnostic_bag((0, 1, 1, 2, 2, 0))
    save(path.parent, manifest(path))
    result = verify(path.parent)
    assert result["status"] == "passed" and len(result["incident_ids"]) == 2
    assert (
        json.loads((path.parent / "report.json").read_text())["recording"]["sha256"]
        == (result["recording_sha256"])
    )


@pytest.mark.parametrize("damage", ["counts", "timestamp", "missing_message"])
def test_integration_verifier_rejects_mismatched_truth(diagnostic_bag, damage):
    path = diagnostic_bag((0, 1, 1, 2, 2, 0))
    truth = manifest(path)
    if damage == "counts":
        truth["metadata"]["message_count"] = 7
    elif damage == "timestamp":
        truth["sent"][1]["header_time_ns"] += 1
    else:
        truth["sent"].pop()
    save(path.parent, truth)
    with pytest.raises(AssertionError):
        verify(path.parent)
    assert not (path.parent / "report.json").exists()


def test_integration_verifier_requires_navigation_controls(diagnostic_bag):
    path = diagnostic_bag((0, 1, 1, 2, 2, 0))
    truth = manifest(path)
    truth.update(
        kind="nav2_gazebo",
        goals=[
            {
                "scenario": "missing_behavior_tree",
                "accepted": True,
                "status": 6,
                "goal_id": "01" * 16,
            },
        ],
    )
    save(path.parent, truth)
    with pytest.raises(AssertionError, match="control"):
        verify(path.parent)


@pytest.mark.parametrize("escape", ["filename", "bag"])
def test_integration_verifier_rejects_paths_outside_capture(tmp_path, escape):
    truth = manifest(tmp_path / "test.mcap")
    if escape == "filename":
        truth["metadata"]["relative_file_paths"] = ["../other.mcap"]
    else:
        truth["bag"] = ".."
    save(tmp_path, truth)
    with pytest.raises(ValueError, match="path"):
        verify(tmp_path)
