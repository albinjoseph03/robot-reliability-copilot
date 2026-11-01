# Reproducing observations

## Tested offline path

Run `robotcopilot sample demo.mcap` followed by `robotcopilot analyze demo.mcap`.
The sample uses the official Python writer with embedded ROS 2 message
definitions and real CDR serialization. It does not run a ROS node or simulator.
Tests generate their own temporary recordings; no third-party dataset is used.

## Completed runtime validation

The automated harness has now run real ROS diagnostics and headless Nav2/Gazebo
controls. See [integration results](INTEGRATION_RESULTS.md) and the
[capture/verifier instructions](../scripts/integration/README.md). It preserves
native client results and handles the observed rosbag2 schema omission.
The following manual commands are reference alternatives, not the exact harness run.

## Manual real ROS diagnostic capture

On an installed, sourced ROS 2 Jazzy environment, install the distribution's
rosbag2 MCAP plugin if needed. In one terminal:

```bash
ros2 bag record -s mcap -o diagnostic_capture --topics /diagnostics
```

In another sourced terminal, publish one known observation:

```bash
ros2 topic pub --once /diagnostics diagnostic_msgs/msg/DiagnosticArray \
  "{status: [{level: 2, name: synthetic_motor, message: synthetic_error, hardware_id: synthetic_01, values: []}]}"
```

Ensure rosbag2 has discovered the publisher/subscriber before sending a single
message. Use `ros2 topic echo /diagnostics` or repeat publishing if delivery is
uncertain. Stop recording cleanly, run `ros2 bag info diagnostic_capture`, then:

```bash
robotcopilot analyze diagnostic_capture/diagnostic_capture_0.mcap
```

Use the actual filename produced by rosbag2. Acceptance: the incident refers
to `synthetic_motor`, ERROR=2, `/diagnostics`, and a decodable message. Compare
counts with rosbag2. Record ROS, rosbag2, MCAP plugin and Python versions.

## Manual simulation exploration

Use the official [Nav2 Jazzy quickstart](https://docs.nav2.org/jazzy/getting_started/quickstart/quickstart/)
on Ubuntu 24.04 with Gazebo Harmonic; confirm the current install/launch options
against the installed packages. Gazebo documents [compatible pairs](https://gazebosim.org/docs/harmonic/ros_installation/).

1. Launch `ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False`.
   Initialize localization in RViz and verify one successful navigation first.
2. Inspect `ros2 topic list --include-hidden-topics -t` and confirm the actual
   navigation action status name and `action_msgs/msg/GoalStatusArray` type.
3. Record it explicitly, including hidden topics:

   ```bash
   ros2 bag record -s mcap -o nav_failure --include-hidden-topics \
     --topics /navigate_to_pose/_action/status /diagnostics /rosout
   ```

4. On the disposable simulation, send a navigation goal using a deliberately
   nonexistent behavior-tree file. This is a candidate deterministic failure
   injection; its outcome is not assumed:

   ```bash
   ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
     "{pose: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 0.0}, orientation: {w: 1.0}}}, behavior_tree: /tmp/robotcopilot-intentionally-missing.xml}"
   ```

5. Save the action client's goal UUID, accepted/rejected state, terminal status
   and result/error fields as ground truth. Require an **accepted goal with
   ABORTED=6 actually recorded**. Rejection, failed discovery or generic warnings
   do not satisfy this test. If this injection is rejected before acceptance,
   select an unreachable goal in a verified map, document it, and rerun.
6. Analyze the resulting individual MCAP with
   `--navigation-status-topic /navigate_to_pose/_action/status`. Require a UUID
   match and no claimed physical cause. Follow with successful and canceled
   controls, which must not produce abort findings.

Status QoS, hidden-topic discovery, map geometry and Nav2 behavior vary by
version. Preserve exact versions, launch options, permitted recording and client
result before labeling a fixture. These manual commands are reference alternatives,
not a claim that they have been executed verbatim. The tested harness and native
regression fixtures document the actual executed simulation. Raw CLI status
recordings from rosbag2 0.26.11 can omit schemas and are insufficient for offline
decoding; use the documented companion writer. No Gazebo assets or external
recordings are redistributed by this project.
