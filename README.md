# Robot Reliability Copilot

[![CI](https://github.com/albinjoseph03/robot-reliability-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/albinjoseph03/robot-reliability-copilot/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/albinjoseph03/robot-reliability-copilot)](https://github.com/albinjoseph03/robot-reliability-copilot/releases/latest)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

Find evidence-backed incidents in ROS 2 recordings without uploading robot data.

`robotcopilot` is an early, deterministic Python CLI for MCAP recordings. It
reports diagnostic severity episodes, explicitly configured navigation aborts,
and configured telemetry gaps, with nearby recorded ROS log context. Every
finding and context entry links back to recorded messages.
It does not infer a root cause or use an LLM.

## Install and run

Python 3.11+ is required. No ROS installation is needed for offline analysis.
Install the published v0.2.0 wheel in an activated Python virtual environment:

```bash
python -m pip install "https://github.com/albinjoseph03/robot-reliability-copilot/releases/download/v0.2.0/robot_reliability_copilot-0.2.0-py3-none-any.whl"
robotcopilot --version
robotcopilot sample demo.mcap
robotcopilot analyze demo.mcap
```

Expected: **version 0.2.0, four recorded messages, one diagnostic ERROR incident**.
The demo intentionally records an error; finding it means the demo worked.
See the [Windows, Linux and macOS quickstart](docs/QUICKSTART.md) for isolated
installation and JSON output. No account or robot is needed to try the demo.

The [release page](https://github.com/albinjoseph03/robot-reliability-copilot/releases/tag/v0.2.0)
includes the wheel, source archive, SHA-256 checksums and release notes.
The project is not published to PyPI.

### Run from source

For the bundled native ROS fixtures or development, install
[uv](https://docs.astral.sh/uv/getting-started/installation/) and clone the project:

```bash
git clone https://github.com/albinjoseph03/robot-reliability-copilot.git
cd robot-reliability-copilot
uv sync --locked --dev
uv run robotcopilot sample demo.mcap
uv run robotcopilot analyze demo.mcap
uv run robotcopilot analyze demo.mcap --format json --output report.json
```

Alternatively, create a virtual environment and run `python -m pip install .`
from this directory; then use `robotcopilot` directly. Activate with
`.venv\Scripts\Activate.ps1` on PowerShell or `source .venv/bin/activate` on POSIX.

The sample is synthetic: **OK → ERROR → ERROR → OK**. Expected result: four
messages, one ERROR incident, two severity observations, and a later observed
OK transition. Its first ERROR is at **1700000001000000000 ns**, on
`/diagnostics`, message **#2**, field **status[0]**. This scenario is a software
fixture, not proof of a physical overtemperature or a Nav2 simulation.

Sample and report files are created exclusively; choose a new filename if one
already exists. Input recordings are never overwritten.

```bash
# Point at an individual .mcap, not a rosbag2 directory.
robotcopilot analyze recording_0.mcap \
  --navigation-status-topic /navigate_to_pose/_action/status \
  --expect-rate /odom=10 --gap-factor 3

robotcopilot schema > report.schema.json
robotcopilot --help
```

On PowerShell, put the analyze command on one line or use its backtick line
continuation instead of `\`. Options may be repeated for multiple topics.

## Nearby log context (0.2)

Try the native Nav2 fixture, including recorded `/rosout`, without installing ROS:

```bash
uv run robotcopilot analyze tests/fixtures/ros2_jazzy/navigation_context/recording.mcap \
  --navigation-status-topic /navigate_to_pose/_action/status
```

Expected: **30 messages, one abort incident, seven nearby WARN-or-higher logs**,
including the server's recorded missing-behavior-tree error. Successful and
canceled goals are excluded. The deliberately unrelated warning is context only.
Read the [example JSON report](docs/examples/nav2-report.json) to inspect the
evidence and log references before installing anything. It was generated with
the published v0.2.0 wheel against this saved native fixture.

Context defaults to the 20 nearest logs within **five seconds before/after the
first incident observation**, returned in chronological order. It is labelled
**time proximity only**, separate from detector evidence and hypotheses.
`--context-window 2` changes the window, `--max-context-logs 10` changes the cap,
`--log-topic /robot/rosout` overrides the default topic (repeatable), and
`--context-window 0` disables it. Missing or undecodable logs and omitted matches
are explicit. See [the context contract and validation](docs/LOG_CONTEXT.md).

JSON reports now declare `report_version: "0.2"`; consumers should use
`robotcopilot schema` to obtain the updated contract.

## Supported evidence

| Rule | Input and behavior | What it cannot establish |
| --- | --- | --- |
| Diagnostic severity transitions | `diagnostic_msgs/msg/DiagnosticArray`, embedded `ros2msg` schema + CDR; WARN/ERROR/STALE episodes per topic, name, hardware ID; same-level repeats aggregated | Physical root cause, actual onset, recovery without a later state |
| Navigation abort | `action_msgs/msg/GoalStatusArray` on an explicitly configured navigation topic; one ABORTED (6) finding per topic and UUID | Nav2 error code, rejected goal, generic log warning, canceled goal as failure |
| Missing telemetry | Inter-message intervals exceeding `gap-factor / expected Hz`, using MCAP log time and explicit continuous-rate configuration | Failure of publisher, rate of intermittent topics, whole-topic absence, startup/shutdown gaps |
| Related log context | `rcl_interfaces/msg/Log` (or `rcl_interfaces/Log`) on configured topics, embedded ros2msg/CDR; numeric levels >=30 | Causation, logger relevance, a navigation failure without action evidence |

ROS interface layouts were checked against Jazzy definitions. Navigation is
supported at the generic ROS 2 action-status schema level. Equivalent two-part
ROS 2 names (`action_msgs/GoalStatusArray`, `diagnostic_msgs/DiagnosticArray`)
are also supported; original names remain in metadata. Nav2 action results and
service event recordings are not decoded in this increment.

Runtime validation passed on ROS 2 Jazzy, rosbag2 0.26.11, Nav2 1.3.13 and
Gazebo Harmonic 8.15.0 in Ubuntu 24.04 / WSL2. This combination has a rosbag2
action-status schema omission: the integration harness preserves the raw CLI
capture and uses a native writer companion with the equivalent two-part type
name. It verifies identical CDR bytes/publish timestamps and client goal UUIDs.
See [actual integration results](docs/INTEGRATION_RESULTS.md).

## Reports and coverage

Terminal and JSON reports include file hash, profile/writer, per-channel types,
encodings, counts and log-time bounds; a chronological incident timeline;
evidence; verification steps; and detection limitations. JSON timestamps remain
integer nanoseconds. JavaScript consumers must preserve large JSON integers
(for example with a lossless JSON parser); native `JSON.parse` can round them.

Message identity is the file SHA-256 plus one-based physical message traversal
ordinal and field path. Channel and sequence are also included; sequences can
repeat. A diagnostic header timestamp is retained separately. No timestamp is
assumed to be wall-clock UTC. Incident IDs are deterministic within a report.

Unsupported messages remain counted and are reported as coverage gaps. Decode
errors retain message references and break diagnostic continuity. Missing or
empty diagnostic data means **unknown**, not healthy. Unresolved incident end
times are `null`. A transition to another severity ends an episode but does not
prove that the underlying physical condition was fixed. Hypotheses stay empty.

## Current limits

- One local MCAP file at a time. No SQLite `.db3`, ROS 1 bags, bag-directory
  aggregation, external schema lookup, IDL decoding, live monitoring or LLM.
- The recording activity summary describes message/incident counts, not robot
  motion, task completion or scene understanding.
- The official Python MCAP reader/ROS 2 decoder is used. Compressed Zstd/LZ4 and
  files without summary indexes are covered by synthetic tests.
- Fatal container corruption returns exit 1 without a partial report. Payload
  decode failures can produce a report with explicit incomplete coverage.
- Defaults: 64 MiB outer MCAP record limit, one million messages and one
  million retained observations; adjustable CLI options. Counts come from a
  full scan. Sorting observations costs memory; this is not yet a large-fleet
  or bounded-memory tool. Compressed expansion is not fully bounded.
- Analysis success is exit 0 even if incidents or coverage gaps exist. Invalid
  usage is exit 2. There is no CI regression pass/fail policy yet.

The analyzer does not execute recorded content, extract attachments, or send
data over a network. Reports can contain sensitive names, log text, source paths and telemetry; review
before sharing. See [SECURITY.md](SECURITY.md).

## Development and project direction

```bash
uv sync --locked --dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv build
```

- [Research and alternatives](docs/RESEARCH.md)
- [Architecture, detector contract and milestones](docs/ARCHITECTURE.md)
- [Validation: evidence and limits](docs/VALIDATION.md)
- [ROS 2 / Nav2 reproduction path](docs/ROS_REPRODUCTION.md)
- [Technical roadmap](docs/ROADMAP.md)
- [Commercial hypotheses](docs/COMMERCIAL_STRATEGY.md)
- [Contributing](CONTRIBUTING.md), [Code of conduct](CODE_OF_CONDUCT.md)

Bug reports and detector proposals are welcome through
[GitHub Issues](https://github.com/albinjoseph03/robot-reliability-copilot/issues).
Include a minimal synthetic reproduction and the coverage/evidence output.
Report vulnerabilities privately using [the security policy](SECURITY.md).

Trying this on another ROS distribution or recorder? Include the tool version,
ROS/recorder versions, topic types, exact command and expected versus observed
findings. A small permitted reproduction helps us expand tested compatibility.
See [community announcement drafts and a short demo script](docs/COMMUNITY_LAUNCH.md)
if you would like to introduce the project to other robotics developers.

Apache-2.0. Synthetic values are original project fixtures. Standard ROS
interface definitions and dependencies retain their upstream licenses; see
[third-party notices](THIRD_PARTY_NOTICES.md). No external robot datasets are
included. Small original ROS/Nav2 recordings and their ground truth are retained
as regression fixtures. Runtime compatibility claims cover only the tested
combination and documented schema workaround. The configured Python/OS CI matrix
passes; additional ROS/recorder combinations still need runtime validation.
