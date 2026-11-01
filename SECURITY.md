# Security and sensitive robot data

This early CLI performs local analysis only. It has no upload API, telemetry
service, LLM connection or recording-content execution. Dependency installation
may use the network; analysis itself does not.

Recordings and reports may expose component names, hardware identifiers,
locations in topic names, diagnostic text and local paths. Review and redact
reports before sharing. Do not attach private robot data to public issues.

The parser validates available chunk/data CRCs, uses an outer-record size
limit and caps messages/retained observations. CRCs do not establish provenance.
Schema parsing, compressed expansion, nested fields, attachments read by the
underlying parser, CPU usage and memory are not completely bounded. For
hostile inputs use a disposable process/container with OS resource limits,
read-only input and no network. This CLI is not a sandbox or a robot safety
system. It must not control a robot or certify safe operation.

Report suspected vulnerabilities through
[GitHub's private vulnerability reporting form](https://github.com/albinjoseph03/robot-reliability-copilot/security/advisories/new).
Private reporting is enabled for this repository. Include package versions and
a minimal synthetic reproduction, not secrets. Do not open a public issue for
an undisclosed vulnerability. No response SLA is promised.

Only the current development version is supported. Keep dependencies current
and repeat the test suite after updates. If a vulnerability is confirmed,
maintainers should coordinate a fix and disclosure before releasing details
that would put users' data at risk.
