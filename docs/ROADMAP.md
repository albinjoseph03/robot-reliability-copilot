# Technical roadmap

The first release should earn trust through reproducible observations, not
through a large feature list. Milestones and acceptance criteria are in
[ARCHITECTURE.md](ARCHITECTURE.md).

## Implemented in the initial increment

- Single-file MCAP scan, metadata/counts, exact evidence references and SHA-256.
- ROS 2 embedded ros2msg/CDR diagnostic decoding and severity episodes.
- Explicitly configured generic navigation action ABORTED status detection.
- Explicit-rate inter-message gap detection with conservative limitations.
- Terminal/JSON reports, report schema, local synthetic sample generator.
- Tests, packaging, CI configuration, contribution and security policies.

## Completed: real ROS integration gate (2026-11-01)

- ROS 2 Jazzy / rosbag2 diagnostic capture: six messages, expected WARN and ERROR
  episodes, exact publisher timestamps and message counts verified.
- Nav2 1.3.13 / Gazebo Harmonic 8.15.0: successful, aborted and canceled goals,
  matched against native client UUIDs/results. Exactly one abort finding.
- rosbag2 0.26.11 schema omission reproduced and documented. A native writer
  companion embeds installed definitions through the equivalent ROS type alias;
  CDR bytes and publish timestamps match the untouched CLI recording.
- Saved native fixtures run in the regular tests without a ROS installation.

See [the evidence and limits](INTEGRATION_RESULTS.md).

## Next: release and broader compatibility

The public repository, five-job Python/OS CI matrix and private vulnerability
reporting are now configured and verified. Next, test another supported
recorder/distribution combination and benchmark representative large recordings
before advertising memory or performance budgets. Collect developer feedback
through reproducible issue reports before broadening detector scope.

## Completed: log context (0.2.0)

Recorded ROS Log messages can now accompany existing incidents, with exact
references, configurable windows and limits, explicit coverage and temporal-only
association. A fresh Nav2/Gazebo capture verifies the real missing-BT server log
against native client results and the untouched CLI recording. Unrelated logs
create no incidents. See [the feature contract](LOG_CONTEXT.md).

## Then: improve reliability based on users

- Ask five robotics developers to analyze one permitted recording and explain
  which report evidence helped or misled them. Track false positives and
  missing schema/topic coverage before adding detectors.
- Add action-result support only with recorded service-event fixtures and
  documented per-distribution layouts. Add useful TF/lifecycle/rosout rules
  with explicit evidence contracts, rather than generic warning matching.
- Consider streaming/external sorting, split-bag sessions, machine-readable
  regression policy, packaging benchmarks and supported resource budgets.
- Add opt-in AI explanations only after deterministic findings are trusted;
  keep hypotheses visibly distinct and preserve local/offline usage.

Live monitoring, fleet backends, auth, databases and dashboards are outside
this release. Commercial experiments are tracked separately.
