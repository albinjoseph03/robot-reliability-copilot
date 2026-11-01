# Validation evidence and boundaries

Analyzer environment: Windows, CPython 3.13.5, uv 0.12.1. Initial checks ran
2026-10-31; real ROS integration and the expanded suite ran 2026-11-01.
See `uv.lock` for the exact resolved dependency graph.

## Automated checks

`pytest -q`: **65 passed**. The suite uses actual temporary MCAP files, the
official Python writers, CLI invocation, and an independently serialized
little-endian XCDR1 diagnostic payload. No LLM supplies labels or telemetry.
It also checks saved native ROS/rosbag2/Nav2 recordings, including a real
missing-schema negative fixture. These saved-fixture tests do not relaunch ROS.

| Tests/scenario | What it proves | What it does not prove |
| --- | --- | --- |
| First success criterion / sample CLI | Four-message OK/ERROR/ERROR/OK recording yields one evidence-backed ERROR with two observations and later state change | Physical motor overtemperature |
| Repeated warnings, transitions, STALE | Same-level duplicates aggregate; severity changes close episodes; STALE stays distinct | Repeated text changes have the same underlying cause |
| Component, topic, hardware identity | Different reporters keep independent episodes | Reporter names or IDs are authentic |
| Out-of-order and equal timestamps | Log-time chronology preserves physical message references and array order | Wall-clock synchronization or correct chronology after clock reset |
| Zstd, LZ4, no summary/index | Official reader handles these generated variants | Every recorder/version/MCAP variant |
| Empty recording / missing or empty diagnostics | Explicit unknown coverage without fabricated incidents; zero timestamps retained | Robot health without observations |
| Unsupported schema/encoding / unknown schema ID | Counts and coverage remain available without a crash | Decoding IDL or arbitrary message types |
| Malformed CDR / invalid diagnostic level | Referenced decode issue, no invented severity, diagnostic continuity reset | All hostile CDR inputs or parser safety |
| Corrupt magic, truncation, CRC mutation, trailing bytes | Clean failure with no partial report on tested container damage | Exhaustive structural conformance or authenticity |
| Navigation abort / UUID deduplication | Explicit-topic ABORTED=6 yields one finding per UUID; different goals remain distinct | Nav2 runtime interoperability or action result error codes |
| Action status 0–5 / unconfigured topic | Cancellation/success/nonterminal states and unconfigured generic actions do not become navigation failures | Goal rejection detection |
| Configured telemetry interval | Strict threshold, exact nanosecond interval and adjacent evidence | Publisher failure, inferred rates, startup/shutdown/whole-topic outages |
| Missing configured topics / invalid config / limits | Insufficient evidence and clear usage/resource errors | Fully bounded memory, CPU or decompression |
| JSON round trip / repeatability / Unicode | Pydantic report validation, integer timestamps, file/stdout consistency, deterministic IDs, Unicode preserved through legacy output encodings | Lossless timestamp handling in JavaScript's default JSON parser |
| Output/sample overwrite protection | Existing input/output files remain unchanged | Arbitrary filesystem race resistance |
| Literal telemetry rendering / CLI schema/help/version | Recorded diagnostic text cannot activate tested markup/ANSI; commands are usable | A formal terminal security audit |
| Native ROS diagnostics | Saved DDS/rosbag2 recording yields the expected levels, repetition counts and publisher timestamps | Physical motor failure |
| Native Nav2 controls | Abort UUID matches client result; success/cancellation excluded even when result error_code=0 | Every Nav2/ROS distribution or physical navigation defect |
| Native schema-less recording | The actual rosbag2 omission remains explicit incomplete coverage | Recovery of missing schemas |
| Companion identity / verifier rejection | Native CDR bytes and publish timestamps match CLI recording; changed timestamps are rejected | Authenticity of arbitrary external manifests |

`ruff check .` and `ruff format --check .` passed. Wheel and source
distribution are built with `uv build --offline` using the cached build backend.
The release artifact must include the report modules, console entry point,
Apache license, notices and retained UUID BSD license. The source distribution
also includes docs, fixtures, tests and CI configuration.

## Not yet validated

- GitHub Actions is configured for Linux Python 3.11–3.14 and Windows Python
  3.13, but no remote CI run is claimed for this unpublished workspace.
- Real runtime validation covers Ubuntu 24.04 / WSL2, Jazzy, rosbag2 0.26.11,
  Nav2 1.3.13 and Gazebo 8.15.0 with the documented schema workaround. Other
  runtime combinations have not been validated.
- No real-world dataset, failure labels, fleet benchmark, memory budget,
  accuracy/recall metric or causal root-cause evaluation is claimed.
- The parser uses third-party code. Resource caps and checksum validation are
  guardrails, not hostile-input isolation or a safety certification.

The [executed integration evidence](INTEGRATION_RESULTS.md) documents native
client-result/UUID ground truth and positive/negative controls. Before
publication, configure a real private security reporting channel and run the
configured CI matrix.
