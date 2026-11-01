# Changelog

## 0.2.0 — 2026-11-01

- Add recorded ROS log context to existing incidents, with exact message and
  source-location references, explicit temporal-only association and coverage.
- Add configurable log topics, time windows and nearest-log caps. Preserve
  custom levels and source stamps; show omitted counts and incomplete data.
- Add a fresh native Nav2/rosout capture with client/subscriber ground truth,
  raw CLI payload verification and positive/negative regression fixtures.
- Reports use schema version 0.2; strict 0.1 consumers must update their schema.

## 0.1.0 — 2026-11-01

- Initial public offline CLI with diagnostic severity episodes, configured
  navigation abort and telemetry gap detection, terminal/JSON reports and
  evidence references. Includes native ROS/Nav2 fixture validation.
