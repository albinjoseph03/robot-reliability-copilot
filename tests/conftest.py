from pathlib import Path

import pytest
from mcap.writer import CompressionType
from mcap_ros2.writer import Writer

from robotcopilot.sample import BASE_TIME_NS, DIAGNOSTIC_SCHEMA, diagnostic_message


@pytest.fixture
def diagnostic_bag(tmp_path: Path):
    def write(levels=(0, 2, 2, 0), offsets=None, components=None, compression=CompressionType.NONE):
        path = tmp_path / "diagnostics.mcap"
        with path.open("wb") as stream, Writer(stream, compression=compression) as writer:
            schema = writer.register_msgdef(
                "diagnostic_msgs/msg/DiagnosticArray", DIAGNOSTIC_SCHEMA
            )
            for i, level in enumerate(levels):
                timestamp = BASE_TIME_NS + (offsets[i] if offsets else i * 10**9)
                message = diagnostic_message(
                    level, timestamp, components[i] if components else "motor"
                )
                writer.write_message(
                    "/diagnostics",
                    schema,
                    message,
                    log_time=timestamp,
                    publish_time=timestamp - 123,
                    sequence=i,
                )
        return path

    return write
