# Real ROS integration harness

These scripts are development tools. The CLI never installs ROS or starts a
simulation. Run the capture with ROS's **system Python**, and the verifier with
the CLI's own Python environment. This keeps `rclpy` ABI requirements separate
from the offline application.

## Setup on Ubuntu 24.04

`install_ros_jazzy.py` explicitly configures the official ROS APT source and
installs Jazzy, rosbag2/MCAP, Nav2 and the minimal TurtleBot3 Gazebo simulation.
It needs root access, network access and several GB of disk space. Inspect it
before running on the intended development environment. It does not upgrade
the Ubuntu distribution or modify shell startup files.

```bash
sudo python3 scripts/integration/install_ros_jazzy.py --install
```

The ROS APT-source `.deb` is fetched from the official GitHub release and
verified against its published SHA-256 asset digest. Subsequent packages use
APT's signed repository metadata. APT may update installed library dependencies.

## Capture and verify

Choose fresh output directories; scripts do not overwrite captures or reports.
Use an unused DDS domain ID on a disposable simulation system. The default is
73 with localhost discovery. Do not run these tests against a physical robot.

```bash
bash scripts/integration/run_capture.sh diagnostics --output artifacts/ros-diagnostics
bash scripts/integration/run_capture.sh navigation --output artifacts/nav2-gazebo
bash scripts/integration/run_capture.sh navigation --with-rosout --output artifacts/nav2-rosout

# Back in the analyzer environment (does not need sourced ROS):
uv run python scripts/integration/verify_capture.py artifacts/ros-diagnostics
uv run python scripts/integration/verify_capture.py artifacts/nav2-gazebo
uv run python scripts/integration/verify_capture.py artifacts/nav2-rosout
```

For Windows/WSL, call `wsl -d Ubuntu -- bash` with the absolute `/mnt/f/...`
path to `run_capture.sh`. Pass capture output as a Linux path in the shared
workspace. Run verification on Windows using the matching Windows path.

The diagnostic scenario publishes six actual ROS messages with levels
`OK, WARN, WARN, ERROR, ERROR, OK`. It waits for rosbag2's subscriber and saves
publisher header timestamps as independent ground truth.

The navigation scenario launches the packaged headless Gazebo world and Nav2,
initializes localization, and waits for the map-to-base transform. It records
the hidden action-status topic and saves each action client's accepted state,
goal UUID, terminal status and result fields. Its controls require:

1. A goal at the localized robot pose succeeds (`4`).
2. A goal with an intentionally missing behavior-tree file aborts (`6`).
3. A running goal is acknowledged as canceled (`5`).

Jazzy rosbag2 0.26.11 omits the schema for the canonical GoalStatusArray type.
The harness preserves this unmodified CLI capture in `navigation/` and records
a companion `navigation_embedded/` using the native `rosbag2_py` writer with
the equivalent two-part ROS type name. This uses the installed standard message
definitions through rosbag2's normal MSG lookup, without editing the ROS install.
The subscriber receives **raw DDS CDR bytes**. Verification requires identical
status CDR bytes and publish timestamps in both recordings, matching per-topic
counts, and the same goal UUIDs as client results. The offline analyzer never fills in missing
schemas. See the [upstream definition-selection code](https://github.com/ros2/rosbag2/blob/jazzy/rosbag2_cpp/src/rosbag2_cpp/message_definitions/local_message_definition_source.cpp).

`--with-rosout` also records live raw ROS logs through the companion writer and
requires exactly one observed missing-BT ERROR from bt_navigator. It injects
an explicitly unrelated warning to verify logs do not become incidents. The
verifier checks the exact log fields/reference in the incident's temporal-only
context, and requires every companion log payload/publish timestamp to occur
in the untouched CLI recording. The CLI may include additional latched startup
logs, so total log counts can differ. Companion metadata counts must still match
the analyzer. Source log stamps and MCAP log time are not substituted for one another.

Rejected goals, missing recordings, timeouts and failed controls fail the
capture. The verifier checks counts against rosbag2 metadata, decodability,
publisher timestamps or action UUIDs, and exclusion of successful/canceled
goals from incidents. A failed attempt retains logs and any completed goal
results for inspection; it does not write a passing ground-truth manifest.

## Outputs and interpretation

- `environment.json`: runtime/package versions.
- `ground-truth.json`: publisher observations or client results and bag metadata.
- `diagnostics/`, `navigation/`, `navigation_embedded/`: rosbag2 metadata and MCAPs.
- `recorder.log`, `nav2-gazebo.log`, `ros-logs/`: debugging artifacts.
- `report.json`, `verification.json`: written only after verification passes.

An injected diagnostic error remains synthetic telemetry, even though it was
transported and recorded by real ROS. A missing behavior tree is a software
configuration failure; it is not evidence of a physical navigation defect.
The packaged world/models are used locally, not redistributed by these tools.
Only successful executed runs establish compatibility for their saved versions.
