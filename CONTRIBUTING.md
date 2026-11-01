# Contributing

Start with a reproducible problem: a small synthetic MCAP, the exact command,
expected observation and actual report. Do not upload proprietary recordings,
credentials, robot maps or personal data to public issues.

Use Python 3.11+ and `uv sync --locked --dev`. Run `uv run pytest -q`,
`uv run ruff check .`, `uv run ruff format --check .` and `uv build` before a PR.
Update the lockfile with `uv lock` only when dependency changes are intentional.

Useful first contributions include real rosbag2 integration tests, documented
schema variants, coverage messages, and small detector rules with positive
and negative fixtures. Read [the architecture](docs/ARCHITECTURE.md) first.

Every new detector must explain its evidence, assumptions, false positives,
supported schemas and limitations. Add a reproducible fixture and a negative
test that would otherwise look like a failure. Preserve exact timestamps and
message references. Do not invent missing telemetry or ground-truth labels.

Keep PRs focused; include the problem, resulting behavior and checks actually
run. Distinguish synthetic validation from a real ROS runtime test. Discuss
new dependencies or broad architecture changes in an issue first. Contributors
retain copyright and submit contributions under Apache-2.0; no CLA is required.
Use respectful, constructive communication and follow the code of conduct.
