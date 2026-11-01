# Executed ROS/Nav2 integration results

Completed 2026-11-01, Asia/Calcutta. The existing Ubuntu WSL environment was
equipped with ROS/Nav2/Gazebo using the explicit integration bootstrap. The
analyzer runs separately in Windows; it does not acquire a ROS dependency.

## Runtime and results

| Component | Executed version |
| --- | --- |
| OS | Ubuntu 24.04 in WSL2, x86_64 |
| Capture Python / rclpy | 3.12.3 / 7.1.12 |
| ROS distribution / RMW | Jazzy / rmw_fastrtps_cpp |
| rosbag2 / storage_mcap | 0.26.11 / 0.26.11 (libmcap 1.3.1) |
| Nav2 | 1.3.13 |
| Gazebo Sim | Harmonic 8.15.0 |
| Analyzer Python / mcap / mcap-ros2-support | 3.13.5 / 1.6.0 / 0.6.0 |

Exact Debian package versions are retained in each fixture's ground-truth
manifest under [tests/fixtures/ros2_jazzy](../tests/fixtures/ros2_jazzy/README.md).

**Diagnostics passed.** A real rclpy publisher sent six DiagnosticArray messages
over DDS: OK, WARN, WARN, ERROR, ERROR, OK. rosbag2 recorded six messages. The
analyzer produced exactly two episodes, each with two severity observations
and a later observed state change. Header timestamps matched publisher ground
truth. Recording SHA-256:
`1cde04d1fc2128f3879c3171a8d9ce8b68cae63f9a33b27425a0f335865bbac2`.

**Navigation passed with the schema workaround below.** The harness launched
the packaged headless TurtleBot3/Gazebo simulation with separate Nav2 processes,
initialized AMCL, and waited for localization. A native NavigateToPose client
saved accepted state, UUID, terminal status and result fields for three goals:

| Scenario | Accepted | Client terminal status | Analyzer behavior |
| --- | --- | --- | --- |
| Goal at localized robot pose | yes | SUCCEEDED (4) | No failure |
| Deliberately missing behavior-tree file | yes | ABORTED (6) | Exactly one navigation incident |
| Running goal canceled by client | yes | CANCELED (5), cancellation acknowledged | No failure |

The seven recorded status messages produced exactly one abort finding, UUID
`acb6b8a6e55142af999ebb474173f5dc`, matching the native client. The action result
error_code was **0 for all three goals**, including the abort. Thus a nonzero
result code alone would miss this failure; ABORTED status is the verified
evidence. The analyzer does not invent a missing result code or physical cause.
Companion recording SHA-256:
`bc3a67255224ae526645beafe02599736751dc219dbaa7cb232e11df49229176`.

## Verified rosbag2 compatibility limitation

The unmodified rosbag2 CLI recorded seven valid CDR payloads on the hidden
navigation status topic but left its schema encoding/data empty. Its log states
that the message definition was not found. The analyzer reported unsupported
encoding and unavailable navigation evidence, correctly withholding a verdict.

The Jazzy [definition-source implementation](https://github.com/ros2/rosbag2/blob/jazzy/rosbag2_cpp/src/rosbag2_cpp/message_definitions/local_message_definition_source.cpp)
classifies the canonical `action_msgs/msg/GoalStatusArray` as an action type,
then reaches the unsupported branch instead of ordinary MSG lookup. The actual
standard `.msg` files were present in the installation.

The harness therefore records a second bag through public
`rosbag2_py.SequentialWriter`, using the equivalent supported two-part type
name `action_msgs/GoalStatusArray`. rosbag2 embeds its installed MSG definitions.
The subscriber passes **raw DDS bytes** to the writer; no telemetry or schema
is fabricated. The verifier requires equal message counts, exact CDR bytes and
publish timestamps against the untouched CLI capture, plus the client UUID and
terminal-status controls. All checks passed. The analyzer now accepts both
explicitly supported ROS 2 type-name spellings while preserving original metadata.

This is a capture-time workaround, not automatic recovery of a schema-less
input. Both recordings are retained as positive/negative regression fixtures.

## Issues found during integration

- Native Jazzy DiagnosticStatus `byte` fields require a one-byte Python `bytes`
  value. The publisher was corrected after a native assertion; the orphaned
  test recorder was stopped using its exact workspace output path.
- Jazzy subscription MessageInfo is a dictionary; the harness now uses its
  documented timestamp keys.
- Re-serializing a decoded status can change trailing CDR padding, so the final
  companion writer captures raw bytes and verifies exact equality.
- An exploratory composed Nav2 run completed its controls but crashed during
  teardown. The final validated harness uses separate processes. Failed attempts
  and logs remain under ignored local `artifacts/`; only final successful
  captures were promoted to positive regression fixtures.

## Reproduction and limits

Follow [the integration harness instructions](../scripts/integration/README.md).
The normal test suite rechecks the saved native bytes without launching ROS.
The final suite reports **65 passed** with Ruff checks passing.

These observations validate this controlled software scenario and runtime
combination. They do not establish real-world failure labels, fleet-scale
performance, physical safety, causal root-cause detection, or compatibility
with other distributions/recorders. A GitHub CI run and a concrete private
security reporting channel are still required before public release.
