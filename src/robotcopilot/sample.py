"""Original synthetic values with standard ROS interface definitions. No robot data."""

from pathlib import Path

from mcap.writer import CompressionType
from mcap_ros2.writer import Writer

# Standard interfaces are Apache-2.0 (common_interfaces/rcl_interfaces), except
# the UUID layout from unique_identifier_msgs (BSD-3-Clause). These combined
# schemas remove comments, qualify dependencies, and omit action status constants.
# See THIRD_PARTY_NOTICES.md. Definitions include all transitive dependencies.
DIAGNOSTIC_SCHEMA = """std_msgs/Header header
diagnostic_msgs/DiagnosticStatus[] status
================================================================================
MSG: std_msgs/Header
builtin_interfaces/Time stamp
string frame_id
================================================================================
MSG: builtin_interfaces/Time
int32 sec
uint32 nanosec
================================================================================
MSG: diagnostic_msgs/DiagnosticStatus
byte OK=0
byte WARN=1
byte ERROR=2
byte STALE=3
byte level
string name
string message
string hardware_id
diagnostic_msgs/KeyValue[] values
================================================================================
MSG: diagnostic_msgs/KeyValue
string key
string value
"""

STATUS_SCHEMA = """action_msgs/GoalStatus[] status_list
================================================================================
MSG: action_msgs/GoalStatus
action_msgs/GoalInfo goal_info
int8 status
================================================================================
MSG: action_msgs/GoalInfo
unique_identifier_msgs/UUID goal_id
builtin_interfaces/Time stamp
================================================================================
MSG: unique_identifier_msgs/UUID
uint8[16] uuid
================================================================================
MSG: builtin_interfaces/Time
int32 sec
uint32 nanosec
"""

BASE_TIME_NS = 1_700_000_000_000_000_000


def diagnostic_message(level: int, time_ns: int, component: str = "motor_controller") -> dict:
    return {
        "header": {"stamp": {"sec": time_ns // 10**9, "nanosec": time_ns % 10**9}, "frame_id": ""},
        "status": [
            {
                "level": level,
                "name": component,
                "hardware_id": "synthetic-motor-01",
                "message": {
                    0: "nominal",
                    1: "synthetic warning",
                    2: "synthetic overtemperature",
                    3: "stale",
                }[level],
                "values": [{"key": "temperature_c", "value": "95" if level == 2 else "35"}],
            }
        ],
    }


def generate_sample(path: Path) -> None:
    """Create an exclusive file: OK, ERROR, repeated ERROR, observed OK."""
    with path.open("xb") as stream, Writer(stream, compression=CompressionType.NONE) as writer:
        schema = writer.register_msgdef("diagnostic_msgs/msg/DiagnosticArray", DIAGNOSTIC_SCHEMA)
        writer.add_metadata("provenance", {"source": "synthetic", "scenario": "OK ERROR ERROR OK"})
        for sequence, level in enumerate((0, 2, 2, 0)):
            timestamp = BASE_TIME_NS + sequence * 10**9
            writer.write_message(
                "/diagnostics",
                schema,
                diagnostic_message(level, timestamp),
                log_time=timestamp,
                publish_time=timestamp,
                sequence=sequence,
            )
