# Community launch kit: v0.2.0

These are announcement drafts for the maintainer to review and post from their
own account. No community posts or direct messages have been sent by Codex.
The aim is to find five robotics developers who can try one permitted recording
and explain which evidence was useful, missing or misleading.

## Where to start

The [Projects category on Open Robotics Discourse](https://discourse.openrobotics.org/c/projects/10)
is intended for projects built with or for open-source robotics. Its category
description and [forum guidelines](https://discourse.openrobotics.org/guidelines)
were checked on 2026-11-01. This is a suggested audience, not an endorsement
or a guarantee that a post will be accepted.

Post the technical introduction there once, then answer feedback in the same
thread. Share the shorter announcement with your existing LinkedIn audience.
For other communities, check their current project-sharing rules first.
Keep the maintainer affiliation explicit and describe the tested configuration.

## Open Robotics Discourse draft

**Title:** Robot Reliability Copilot v0.2.0: offline ROS 2 MCAP incident reports with message-level evidence

I'm sharing an early open-source project I maintain: Robot Reliability Copilot,
an offline Python CLI for investigating supported ROS 2 MCAP recordings.

It reports diagnostic severity episodes, ABORTED navigation goals on explicitly
configured action-status topics, and telemetry gaps against configured rates.
Each finding includes exact recorded-message references. v0.2.0 adds nearby
WARN-or-higher ROS log context with logger, source location and timestamps.
Those logs are associated by time only; the tool does not infer a root cause.

A saved native ROS 2 Jazzy / Nav2 1.3.13 / Gazebo Harmonic fixture produces one
abort and seven nearby qualifying logs from 30 messages. Success, cancellation
and an unrelated warning are covered by negative checks. The tested rosbag2
0.26.11 runtime needs a documented action-status schema capture workaround;
the analyzer requires supported embedded schemas.

You can try the synthetic demo without ROS or a robot. Python 3.11+ is required;
install the release wheel in a virtual environment and run:

```sh
robotcopilot sample demo.mcap
robotcopilot analyze demo.mcap
```

The expected result is four messages and one intentional diagnostic error.
The project uses Apache-2.0, runs analysis locally and does not use an LLM.
It currently analyzes one MCAP file at a time; large-recording resource budgets
and additional ROS/recorder combinations still need validation.

- [Repository and supported evidence](https://github.com/albinjoseph03/robot-reliability-copilot)
- [Install and demo](https://github.com/albinjoseph03/robot-reliability-copilot/blob/main/docs/QUICKSTART.md)
- [Wheel, source and checksums](https://github.com/albinjoseph03/robot-reliability-copilot/releases/tag/v0.2.0)
- [Native example JSON report](https://github.com/albinjoseph03/robot-reliability-copilot/blob/main/docs/examples/nav2-report.json)

I'd welcome feedback from developers working with rosbag2/MCAP: does this report
make a recorded incident easier to verify? Which topic or schema support is
missing from your workflow? Please share versions and small permitted
reproductions in GitHub Issues; proprietary recordings are unnecessary.

## LinkedIn draft

I've released Robot Reliability Copilot v0.2.0, an open-source Python CLI for
investigating ROS 2 MCAP recordings locally.

It reports diagnostic episodes, explicitly configured navigation aborts and
telemetry gaps, with exact message references. The new release adds nearby
recorded ROS logs as context, with timestamps and source locations.

No ROS installation is needed for offline analysis. Python 3.11+ is required.
There is a synthetic demo, a native ROS 2 Jazzy/Nav2 fixture and an example JSON
report. Log proximity is not a root-cause diagnosis.

I'm looking for five robotics developers to try a permitted recording and tell
me which evidence helps, which coverage is missing and what should come next.

Code, install instructions and Apache-2.0 license:
https://github.com/albinjoseph03/robot-reliability-copilot

#ROS2 #Robotics #OpenSource #Nav2

## 45-second demo recording script

1. Start with the release wheel already installed in a virtual environment.
   Show `robotcopilot --version` and explain that this is offline analysis.
2. Run `robotcopilot sample demo.mcap` in an empty folder, then
   `robotcopilot analyze demo.mcap`. Explain that four messages produce one
   intentional diagnostic error episode, with two observations.
3. In a source checkout, run the saved native example:
   `robotcopilot analyze tests/fixtures/ros2_jazzy/navigation_context/recording.mcap --navigation-status-topic /navigate_to_pose/_action/status`.
   Point to the abort evidence and nearby logs. Say that temporal context
   does not prove causation.
4. End on the release link and ask viewers which ROS/recorder combination
   they want supported next. Mention the documented schema workaround.

Use only the bundled original fixtures in the recording. The script is ready
to record; no video has been produced as part of this kit.

## Learn from the launch

For the first five trials, collect tool/ROS/recorder versions, configured topic
types, the exact command, expected versus observed findings and a useful or
missing evidence reference. Ask for a minimal permitted reproduction when
needed. Track findings in GitHub Issues and prioritize repeated problems.

GitHub's Traffic view and release asset downloads can help measure visits
and trials. Compare them with substantive feedback; downloads alone do not
establish that someone successfully analyzed a recording. This plan adds no
tracking to the CLI and makes no adoption or performance claims.
