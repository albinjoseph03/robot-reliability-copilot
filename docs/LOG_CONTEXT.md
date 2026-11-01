# Recorded ROS log context (0.2.0)

The analyzer can show nearby recorded logs alongside a deterministic incident.
They remain labelled `time_proximity_only`, separate from the detector's
evidence and hypotheses. Log messages never create, close or change incidents.

## Selection contract

- Supported types: `rcl_interfaces/msg/Log` and `rcl_interfaces/Log`, embedded
  `ros2msg` schema with CDR encoding. The [standard ROS definition](https://github.com/ros2/rcl_interfaces/blob/jazzy/rcl_interfaces/msg/Log.msg)
  provides stamp, level, logger, text, file, function and line.
- Default topic: `/rosout`. Repeat `--log-topic` to override it, for example
  `/robot1/rosout` and `/robot2/rosout`. Topic configuration is literal.
- Numeric severities >=30 qualify. Standard labels are WARN=30, ERROR=40 and
  FATAL=50. Custom levels retain their numeric value and `LEVEL_n` label.
  DEBUG/INFO messages are decoded for coverage but not retained as context.
- Match MCAP **log time**, within an inclusive symmetric window around the
  incident's **first observed start**. Default is +/-5 seconds, configurable
  with `--context-window` from 0 to 3600 seconds. Zero disables decoding and
  association. Fractional seconds are rounded down to whole nanoseconds.
- Default cap: 20 nearest entries (`--max-context-logs`, range 1–1000). Select
  by absolute time distance, earlier log time, then physical message ordinal;
  display the selected entries chronologically. Matching and omitted counts
  remain visible. Same-level repeated log messages are separate observations.

`log_context` on each incident contains the window, association label,
availability, matching/omitted counts, selected structured logs and limitations.
Each log retains its source stamp, MCAP log/publish times, original topic/type,
channel, sequence, physical message ordinal and `msg` field reference. Recording
SHA-256 identifies the source file. Context does not extend to a long incident's
end timestamp, or silently use simulation/header time in place of log time.

## Coverage and interpretation

`available` means each configured topic has some decodable Log data and no
observed skipped/failed messages. It is not a guarantee of continuous delivery
or complete coverage of every time window. `partial` means some configured data
is missing, unsupported or undecodable; `unavailable` means none is decodable;
`disabled` reflects the explicit configuration. A recording/window boundary and
data loss remain limitations. Available context can have zero matching logs.

Different nodes' logs may be nearby but unrelated. Delayed delivery, recorder
pauses, QoS drops and clock differences can distort proximity. The feature
does not assign a causal confidence score, parse error text into a navigation
failure, or infer root causes. Sensitive log text and file paths remain local;
review reports before sharing. Terminal text is rendered literally.

## Executed Nav2 acceptance check

On 2026-11-01, `capture_ros.py navigation --with-rosout` ran headless Gazebo
8.15.0 / Nav2 1.3.13 on ROS 2 Jazzy, rosbag2 0.26.11, Ubuntu 24.04 / WSL2.
The native client verified SUCCEEDED=4, accepted ABORTED=6 for a missing BT file,
and acknowledged CANCELED=5. The companion recorded 30 messages: seven action
statuses and 23 live Log messages. The report contains one abort, seven nearby
qualifying logs, the exact recorded `BT file not found:` error, and an unrelated
fixture warning kept only as context.

The verifier matches the error's logger, severity, message, source stamp and
publish time against the ROS subscriber observation. Every companion log CDR
payload/publish timestamp occurs in the unmodified CLI recording; the complete
status sequence is identical. The CLI capture has 186 logs because of additional
latched startup history. No telemetry or schemas were invented by the analyzer.
The [rosbag2 schema workaround](INTEGRATION_RESULTS.md) is still required for
this runtime's canonical status topic.

Companion SHA-256:
`6183da0a00f09d4b0e153a7a75a2db9b1fa71d69080e18162882cdbf37c29fca`.
Native bytes, client ground truth and subscriber observations are retained in
[the context fixture](../tests/fixtures/ros2_jazzy/navigation_context/ground-truth.json).
Normal tests recheck these saved bytes without launching ROS; this is a
controlled software configuration failure, not a real-world physical failure label.

## JSON consumers

Reports now declare `report_version: "0.2"` and tool version 0.2.0. Consumers
that validate the previous strict 0.1 schema must update. Use
`robotcopilot schema` for the new schema. Toggling context does not alter detector
findings, IDs or original incident evidence, including for mixed-type topics;
new optional context fields are independent. Nanosecond values remain JSON integers, so JavaScript
consumers still need lossless integer handling.
