# ROS 2 Jazzy runtime fixtures

Captured locally on 2026-11-01 (Asia/Calcutta) in Ubuntu 24.04 / WSL2 using
`scripts/integration/capture_ros.py`. These are original controlled fixtures,
not external datasets or real hardware failure labels.

- `diagnostics/recording.mcap`: six synthetic DiagnosticArray messages sent
  through ROS DDS and recorded by rosbag2 0.26.11. Levels: 0, 1, 1, 2, 2, 0.
- `navigation/recording.mcap`: seven raw DDS action-status messages from
  Nav2 1.3.13 in the packaged headless Gazebo TurtleBot3 simulation, recorded
  with native rosbag2_py and its installed MSG definitions.
- `navigation/navigation/raw.mcap`: the simultaneous unmodified rosbag2 CLI
  capture. Its payloads and publish timestamps are identical, but rosbag2
  omitted the action-status schema. It is a real negative coverage fixture.

The native writer uses `action_msgs/GoalStatusArray` (two-part type alias) to
avoid the rosbag2 0.26.11 definition-source bug for the equivalent canonical
name. There is no schema fallback in the analyzer. Ground truth requires a
successful goal (4), accepted goal aborted by a deliberately missing behavior
tree (6), and acknowledged cancellation (5). UUIDs and results were saved by
the native action client. The abort result's `error_code` was zero; terminal
status is the verified abort evidence.

Each directory includes ground-truth data with exact runtime/package versions
and the original verification result/SHA-256. Only file locations in the
ground-truth manifests were updated when relocating the captures; MCAP bytes
are unchanged. Full exploratory logs remain in the local ignored `artifacts/`
directory. Reproduce using the integration harness, not by treating these
messages as evidence of a physical motor fault or navigation defect.

Provenance: original project-generated values/goals and locally simulated
statuses. Apache-2.0 for project-generated content; embedded standard ROS
definitions retain their Apache-2.0/BSD-3-Clause terms in THIRD_PARTY_NOTICES.md
and licenses/UUID-BSD-3-Clause.txt. No Gazebo model, world, map, texture, robot
description or third-party dataset is redistributed in these fixtures.
