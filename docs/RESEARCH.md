# Research and dependency decisions

Reviewed 2026-10-31 against official documentation, source and locally installed
Python package APIs. Version numbers below reflect the resolved environment,
not a claim that every future version is compatible.

## MCAP and ROS 2

Use `mcap` 1.6.0 and `mcap-ros2-support` 0.6.0. Their installed APIs were inspected
and exercised on Windows / CPython 3.13.5. `DecoderFactory.decoder_for(encoding,
schema)` returns a CDR decoder for an embedded `ros2msg` definition. It does not
support IDL. The direct sequential `StreamReader(..., validate_crcs=True,
record_size_limit=...)` avoids trusting summary statistics and works without an
index. `mcap_ros2.writer.Writer.register_msgdef` and `write_message` generate the
synthetic diagnostic recording. Avoid the deprecated high-level reader helper.
[Official Python API](https://mcap.dev/docs/python/),
[decoder implementation](https://mcap.dev/docs/python/_modules/mcap_ros2/decoder),
[writer implementation](https://mcap.dev/docs/python/_modules/mcap_ros2/writer).

`rosbag2_py` is useful when a ROS workspace and distribution-specific Python
environment already exist. It adds unnecessary installation constraints for an
offline CLI. Recording remains a job for rosbag2 with its MCAP storage plugin;
this project analyzes a resulting individual file.
[ROS integration example](https://mcap.dev/docs/python/ros2_example),
[rosbag2 repository](https://github.com/ros2/rosbag2),
[MCAP plugin](https://github.com/ros2/rosbag2/tree/rolling/rosbag2_storage_mcap).

## Evidence semantics

Diagnostics have OK=0, WARN=1, ERROR=2 and STALE=3. STALE must not be relabeled
as ERROR. Component identity includes topic, name and hardware ID. Severity is
reported evidence, not an automatic causal label.
[DiagnosticStatus source](https://github.com/ros2/common_interfaces/blob/jazzy/diagnostic_msgs/msg/DiagnosticStatus.msg),
[DiagnosticArray source](https://github.com/ros2/common_interfaces/blob/jazzy/diagnostic_msgs/msg/DiagnosticArray.msg).

An action GoalStatusArray is generic; the type alone cannot identify Nav2.
Explicit topic configuration provides that context. Status 6 means the server
aborted the goal, while status 5 is cancellation. Nav2's NavigateToPose result
has additional error information; it arrives through action services, not
ordinary diagnostic messages. Do not presume that recording visible topics
captures action results or hidden status topics.
[ROS 2 action states](https://github.com/ros2/rcl_interfaces/blob/jazzy/action_msgs/msg/GoalStatus.msg),
[Jazzy NavigateToPose](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_msgs/action/NavigateToPose.action),
[rosbag2 service recording design](https://github.com/ros2/rosbag2/blob/rolling/docs/design/rosbag2_record_replay_service.md).

For later integration, a documented baseline is Ubuntu 24.04 + ROS 2 Jazzy +
Gazebo Harmonic. Gazebo's current page also recommends the newer Lyrical/Jetty
LTS combination. Choose one baseline and verify it before broadening the
matrix. Subsequent runtime validation on 2026-11-01 used Jazzy/Nav2/Gazebo;
see [integration results](INTEGRATION_RESULTS.md).
[Gazebo compatibility table](https://gazebosim.org/docs/harmonic/ros_installation/),
[Nav2 Jazzy quickstart](https://docs.nav2.org/jazzy/getting_started/quickstart/quickstart/).

## Existing tools

The [MCAP CLI](https://mcap.dev/guides/cli) already provides container inspection,
statistics, structural checks, filtering and recovery. Recommend it for repair;
do not build a competing repair engine.
[PlotJuggler](https://github.com/PlotJuggler/PlotJuggler) provides interactive
time-series exploration. This project's proposed value is repeatable incident
rules with portable evidence reports that complement existing viewers. This
review does not establish uniqueness or product demand.

## Dependency choices

| Direct dependency | Tested version | Purpose |
| --- | --- | --- |
| mcap | 1.6.0 | Sequential MCAP records, checksums, compression |
| mcap-ros2-support | 0.6.0 | Dynamic ROS 2 CDR decoder and fixture writer |
| pydantic | 2.14.2 | Strict-field report contracts and JSON Schema |
| typer | 0.27.3 | CLI argument validation, commands and help |
| rich | 15.0.0 | Readable local reports |
| pytest / ruff | 9.2.0 / 0.17.3 | Behavioral validation and code checks |

`uv.lock` records exact dependencies and hashes; package metadata declares
compatible version ranges. CI targets Python 3.11–3.14; local evidence is for
3.13.5 only. Native compression/Pydantic wheels and older Python compatibility
are verified by actual installation/CI, not by assuming pure-Python portability.
The license inventory is in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Main risks

1. Missing/IDL schemas and hidden action topics prevent decoding or leave
   navigation evidence absent. Coverage must remain explicit.
2. Log, publish, header and simulation clocks may differ or reset. Exact
   timestamps are preserved, but sorting does not solve clock synchronization.
3. Diagnostics may be stale, duplicated or contradictory; observations do not
   prove hardware causes. No fuzzy log matching or LLM labels are used.
4. Recorder drops and QoS can resemble publisher failure. Configured gap rules
   describe inter-message silence only.
5. Third-party parsers and decompression operate on untrusted bytes. Limits
   mitigate accidental exhaustion but are not a security sandbox.
6. Synthetic writer/reader agreement is weaker than real ROS interoperability.
   Native rosbag2/Nav2 fixtures now supplement the independent CDR fixture;
   additional distributions and recorder versions still need their own validation.
