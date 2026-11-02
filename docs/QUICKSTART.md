# Try Robot Reliability Copilot v0.2.0

You need Python 3.11 or newer and an internet connection to install the wheel
and its dependencies. Analysis runs offline; ROS, a robot and a user account
are not required for this demo. Start in an empty folder so the example file
names are available.

## Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install "https://github.com/albinjoseph03/robot-reliability-copilot/releases/download/v0.2.0/robot_reliability_copilot-0.2.0-py3-none-any.whl"
.\.venv\Scripts\robotcopilot.exe --version
.\.venv\Scripts\robotcopilot.exe sample demo.mcap
.\.venv\Scripts\robotcopilot.exe analyze demo.mcap
.\.venv\Scripts\robotcopilot.exe analyze demo.mcap --format json --output report.json
```

These commands use the virtual environment directly; activation is unnecessary.
If `py` is unavailable, use your installed Python 3.11+ executable instead.

## Linux and macOS

```sh
python3 -m venv .venv
.venv/bin/python -m pip install "https://github.com/albinjoseph03/robot-reliability-copilot/releases/download/v0.2.0/robot_reliability_copilot-0.2.0-py3-none-any.whl"
.venv/bin/robotcopilot --version
.venv/bin/robotcopilot sample demo.mcap
.venv/bin/robotcopilot analyze demo.mcap
.venv/bin/robotcopilot analyze demo.mcap --format json --output report.json
```

## Check the result

The version is `0.2.0`. The sample contains four synthetic diagnostic messages:
OK, ERROR, ERROR, then OK. The report contains one diagnostic error incident
with two observations. Its evidence starts at message 2, field `status[0]`,
at MCAP log time `1700000001000000000` nanoseconds.

Finding this intentional error confirms the demo worked. Analysis exits
successfully even when it finds incidents. JSON output uses report schema 0.2;
`report.json` includes the recording SHA-256, message references and limitations.
Choose new sample/output filenames when repeating the commands: existing files
are never overwritten.

For a native Nav2 example, inspect the [saved JSON report](examples/nav2-report.json)
or follow the [source checkout example](../README.md#nearby-log-context-02).
That fixture contains 30 messages, one abort and seven nearby qualifying logs.
The log association is temporal and does not establish a cause.

## Analyze your recording

Use the same virtual-environment executable, replacing the demo path with an
individual `.mcap` file. For example, on Windows:

```powershell
.\.venv\Scripts\robotcopilot.exe analyze "C:\recordings\recording_0.mcap" --navigation-status-topic /navigate_to_pose/_action/status
```

On Linux/macOS, use `.venv/bin/robotcopilot`. Navigation status topics and
expected telemetry rates must be configured explicitly. Embedded supported
schemas are required; see [supported evidence and limits](../README.md#supported-evidence)
and the [tested rosbag2 schema workaround](INTEGRATION_RESULTS.md).

Download packages and `SHA256SUMS` from the [release page](https://github.com/albinjoseph03/robot-reliability-copilot/releases/tag/v0.2.0).
Use `sha256sum --check SHA256SUMS` with all three listed files present, or
compare each file's PowerShell `Get-FileHash -Algorithm SHA256` value.

If the report surprises you, [open an issue](https://github.com/albinjoseph03/robot-reliability-copilot/issues)
with your command, tool and ROS/recorder versions, expected result and coverage
output. Public issues should use small synthetic or otherwise permitted data.
