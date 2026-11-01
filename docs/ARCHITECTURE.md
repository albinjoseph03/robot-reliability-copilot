# Architecture and implementation milestones

Decision date: 2026-10-31. Start with deterministic, offline analysis. No ROS
runtime, network service, database, LLM, or plugin loading is needed to analyze.

## Structure

```text
src/robotcopilot/
  cli.py             Typer commands and exit codes
  models.py          Pydantic report, event, incident, evidence models
  ingestion.py       MCAP scan, schema decoding, normalization, coverage
  detectors/         Stateful diagnostic, action-status, configured-gap rules
  analysis.py        Chronological processing and report assembly
  reporting.py       Rich text and JSON serialization
  sample.py          Reproducible, synthetic CDR/ros2msg recording
tests/               Generated MCAP fixtures and end-to-end tests
docs/                Research, contracts, validation, roadmap, strategy
.github/             CI and contribution templates
```

## Contracts

An evidence reference identifies a message by the input file SHA-256, its
one-based message ordinal in physical MCAP traversal, channel ID, sequence,
topic, schema, exact log and publish timestamps in integer nanoseconds, and
field path. Sequence alone is not unique. Header time is retained separately;
it is never silently substituted for log time. The report owns the file hash.

Normalized diagnostic and goal-status events contain observed fields and
evidence. Detectors implement `observe(event)` and `finish()`. They consume
events sorted by MCAP log time, then physical message ordinal, preserving array entry order.
Each detector owns its state; analysis assembles incidents and coverage. Gap
detection consumes message references, independent of payload decoding.

Incidents have deterministic IDs, category, severity, start/end time, evidence,
explanation, limitations, and verification steps. Hypotheses are a separate
field, empty by default. An end time means a later observed state change, not
proof of physical recovery. An unresolved incident ends at `null`.

## CLI

- `robotcopilot sample demo.mcap`: generate synthetic diagnostics.
- `robotcopilot analyze demo.mcap`: metadata, timeline, evidence, coverage.
- `robotcopilot analyze demo.mcap --format json`: JSON on stdout.
- `--output report.json`: JSON file alongside the selected stdout format.
- `--navigation-status-topic /navigate_to_pose/_action/status`: explicitly
  declare an action-status topic as navigation evidence; no naming inference.
- `--expect-rate /odom=10 --gap-factor 3`: flag observed intervals exceeding
  three configured periods. No automatically inferred rate or boundary gaps.

Exit 0 means analysis completed (including incidents or incomplete coverage),
1 means unreadable/corrupt input or output failure, 2 means invalid CLI usage.

## Tradeoffs and risks

- Use official `mcap` + `mcap-ros2-support`, with `DecoderFactory`; no dependency
  on distribution-specific `rosbag2_py`. Only embedded `ros2msg` + CDR is decoded.
  IDL, ROS 1, SQLite bags, action service results and split bag directories are
  outside this increment. Unsupported channels remain visible in metadata.
- Scan physical order and compute counts instead of trusting summary indexes.
  Sort normalized events, coverage barriers and configured-topic references. This handles
  out-of-order/unindexed recordings, but memory scales with these observations.
- Repeated diagnostics at the same severity are one episode per
  `(topic, component name, hardware ID)`. A different severity closes it. STALE
  is its own warning state, never an ERROR. Decode loss resets diagnostic state
  so it cannot manufacture continuity through missing evidence.
- Navigation ABORTED status proves server-reported termination, not its cause.
  CANCELED is not a navigation failure. Explicit topic configuration supplies
  navigation context; the generic message type cannot identify the action type.
- Gap evidence proves recording silence between observations, not publisher
  failure. No inference for completely absent, startup, or shutdown telemetry.
- Validate CRCs when present, bound record sizes and message counts, catch
  parsing/decoding failures, render recorded text literally, never extract
  attachments or execute content. These are guardrails, not a hostile-input
  sandbox or a bounded-decompression guarantee.

## Independently testable milestones

1. **Research and contracts**: record official APIs, format limitations,
   alternatives, dependency and data licenses; define the report and evidence.
2. **First vertical slice**: generate a real CDR/ros2msg MCAP, decode diagnostics,
   report one ERROR with exact evidence in terminal and JSON. Test via CLI.
3. **Diagnostic episodes and ingestion robustness**: WARN/ERROR/STALE transitions,
   deduplication, ordering, recovery, empty/unsupported/malformed data, CRC and
   resource errors. Do not hide incomplete coverage.
4. **Narrow additional rules**: configured navigation ABORTED status and explicit
   telemetry-rate gaps with reproducible positive and negative fixtures.
5. **Release preparation**: CI, packaging, docs, license review, reproducible
   sample, security/contribution policies; validate installation and commands.
6. **Real ROS integration gate (completed 2026-11-01)**: capture diagnostics with rosbag2,
   then a Nav2/Gazebo abort, preserve action UUID and client result as ground
   truth, and compare reports. See [executed results](INTEGRATION_RESULTS.md) for
   the tested runtime, schema omission workaround and retained native fixtures.

## Testing strategy

Generate temporary MCAPs with the official writers. Test the full pipeline and
CLI, then boundary cases and negative detection examples. Keep a separate
manually serialized CDR diagnostic fixture to avoid relying exclusively on a
writer/reader round trip. CI covers Python 3.11–3.14 on Linux and 3.13 on Windows.
Local results are recorded separately; a configured CI matrix is not a claim
that all environments have passed.
