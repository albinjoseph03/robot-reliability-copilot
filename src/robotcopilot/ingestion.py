"""Scan MCAP records without trusting summary counts or executing recorded content."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from mcap.records import Channel, Footer, Header, Message, Schema
from mcap.stream_reader import StreamReader
from mcap_ros2.decoder import DecoderFactory

from .models import (
    AnalysisConfig,
    ChannelInfo,
    CoverageBreak,
    CoverageIssue,
    DiagnosticEvent,
    Event,
    Evidence,
    GoalStatusEvent,
    LogEntry,
    RecordingInfo,
)

DIAGNOSTIC_TYPE = "diagnostic_msgs/msg/DiagnosticArray"
STATUS_TYPE = "action_msgs/msg/GoalStatusArray"
DIAGNOSTIC_TYPES = {DIAGNOSTIC_TYPE, "diagnostic_msgs/DiagnosticArray"}
STATUS_TYPES = {STATUS_TYPE, "action_msgs/GoalStatusArray"}
LOG_TYPES = {"rcl_interfaces/msg/Log", "rcl_interfaces/Log"}
LOG_LEVEL_NAMES = {10: "DEBUG", 20: "INFO", 30: "WARN", 40: "ERROR", 50: "FATAL"}


class RecordingError(Exception):
    """The recording could not be analyzed completely; no partial report is returned."""


@dataclass
class Scan:
    recording: RecordingInfo
    events: list[Event]
    telemetry: list[Evidence]
    coverage: list[CoverageIssue]
    logs: list[LogEntry]


def _stamp(stamp: object) -> int:
    sec, nanosec = stamp.sec, stamp.nanosec
    if not isinstance(sec, int) or not isinstance(nanosec, int) or not 0 <= nanosec < 10**9:
        raise ValueError("invalid ROS timestamp")
    return sec * 10**9 + nanosec


def _normalize(decoded: object, ref: Evidence, diagnostic: bool) -> list[Event]:
    result: list[Event] = []
    entries = decoded.status if diagnostic else decoded.status_list
    if len(entries) > 10_000:
        raise ValueError("more than 10000 entries in one supported message")
    header = _stamp(decoded.header.stamp) if diagnostic else None
    for i, entry in enumerate(entries):
        item_ref = ref.model_copy(
            update={"field_path": f"{'status' if diagnostic else 'status_list'}[{i}]"}
        )
        if diagnostic:
            if entry.level not in (0, 1, 2, 3):
                raise ValueError("unknown diagnostic level")
            result.append(
                DiagnosticEvent(
                    evidence=item_ref,
                    header_time_ns=header,
                    component=entry.name,
                    hardware_id=entry.hardware_id,
                    level=entry.level,
                    message=entry.message,
                    values=[(v.key, v.value) for v in entry.values],
                )
            )
        else:
            uuid = bytes(entry.goal_info.goal_id.uuid)
            if len(uuid) != 16 or entry.status not in range(7):
                raise ValueError("invalid goal UUID or action status")
            result.append(
                GoalStatusEvent(
                    evidence=item_ref,
                    goal_id=uuid.hex(),
                    goal_stamp_ns=_stamp(entry.goal_info.stamp),
                    status=entry.status,
                )
            )
    return result


def _normalize_log(decoded: object, ref: Evidence) -> LogEntry:
    return LogEntry(
        evidence=ref.model_copy(update={"field_path": "msg"}),
        stamp_time_ns=_stamp(decoded.stamp),
        level=decoded.level,
        level_name=LOG_LEVEL_NAMES.get(decoded.level, f"LEVEL_{decoded.level}"),
        logger=decoded.name,
        message=decoded.msg,
        file=decoded.file,
        function=decoded.function,
        line=decoded.line,
    )


def scan_recording(path: Path, config: AnalysisConfig) -> Scan:
    schemas: dict[int, Schema] = {}
    channels: dict[int, Channel] = {}
    info: dict[int, ChannelInfo] = {}
    events: list[Event] = []
    telemetry: list[Evidence] = []
    logs: list[LogEntry] = []
    context_enabled = bool(config.log_topics) and config.context_window_seconds > 0
    issues: dict[tuple[str, int | None], CoverageIssue] = {}
    factory = DecoderFactory()
    count = 0
    start = end = None
    header = None
    footer = False

    def issue(code: str, message: str, ref: Evidence | None = None) -> None:
        key = (code, ref.channel_id if ref else None)
        if key in issues:
            issues[key].count += 1
        else:
            issues[key] = CoverageIssue(
                code=code,
                message=message,
                channel_id=key[1],
                first_evidence=ref,
            )

    try:
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            stream.seek(0)
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            stream.seek(0)
            reader = StreamReader(
                stream, validate_crcs=True, record_size_limit=config.max_record_bytes
            )
            for record in reader.records:
                if isinstance(record, Header):
                    if header is not None:
                        raise ValueError("duplicate MCAP header")
                    header = record
                elif isinstance(record, Schema):
                    if record.id in schemas and schemas[record.id] != record:
                        raise ValueError("conflicting schema ID")
                    schemas[record.id] = record
                elif isinstance(record, Channel):
                    if record.id in channels and channels[record.id] != record:
                        raise ValueError("conflicting channel ID")
                    channels[record.id] = record
                    schema = schemas.get(record.schema_id)
                    if record.id not in info:
                        info[record.id] = ChannelInfo(
                            channel_id=record.id,
                            topic=record.topic,
                            schema_name=schema.name if schema else None,
                            schema_encoding=schema.encoding if schema else None,
                            message_encoding=record.message_encoding,
                        )
                elif isinstance(record, Footer):
                    footer = True
                elif isinstance(record, Message):
                    count += 1
                    if count > config.max_messages:
                        raise ValueError(f"message limit ({config.max_messages}) exceeded")
                    channel = channels.get(record.channel_id)
                    if channel is None:
                        raise ValueError(
                            f"message references undefined channel {record.channel_id}"
                        )
                    schema = schemas.get(channel.schema_id)
                    ci = info[channel.id]
                    ci.message_count += 1
                    t = record.log_time
                    ci.start_time_ns = t if ci.start_time_ns is None else min(ci.start_time_ns, t)
                    ci.end_time_ns = t if ci.end_time_ns is None else max(ci.end_time_ns, t)
                    start = t if start is None else min(start, t)
                    end = t if end is None else max(end, t)
                    ref = Evidence(
                        message_index=count,
                        channel_id=channel.id,
                        sequence=record.sequence,
                        topic=channel.topic,
                        schema_name=schema.name if schema else None,
                        log_time_ns=t,
                        publish_time_ns=record.publish_time,
                    )
                    if channel.topic in config.expected_rates_hz:
                        telemetry.append(ref)
                    diagnostic = schema is not None and schema.name in DIAGNOSTIC_TYPES
                    navigation = (
                        schema is not None
                        and schema.name in STATUS_TYPES
                        and channel.topic in config.navigation_status_topics
                    )
                    # Typed log data never changes detector state, even if context is disabled
                    # or the log cannot be decoded on a mixed-type topic.
                    known_log = schema is not None and schema.name in LOG_TYPES
                    ros_log = context_enabled and known_log and channel.topic in config.log_topics
                    if not (diagnostic or navigation or ros_log):
                        ci.skipped_message_count += 1
                        issue(
                            "unsupported_message",
                            "Payload not analyzed by an enabled detector.",
                            ref,
                        )
                        if not known_log:
                            events.append(CoverageBreak(evidence=ref))
                    elif schema.encoding != "ros2msg" or channel.message_encoding != "cdr":
                        ci.skipped_message_count += 1
                        issue(
                            "unsupported_encoding",
                            "Requires embedded ros2msg schema and CDR encoding.",
                            ref,
                        )
                        if not known_log:
                            events.append(CoverageBreak(evidence=ref))
                    else:
                        try:
                            decoder = factory.decoder_for(channel.message_encoding, schema)
                            if decoder is None:
                                raise ValueError("no compatible decoder")
                            decoded = decoder(record.data)
                            log = _normalize_log(decoded, ref) if ros_log else None
                            normalized = [] if ros_log else _normalize(decoded, ref, diagnostic)
                        except Exception as exc:
                            # Parsing untrusted schemas/CDR is the isolation boundary. Do not
                            # expose exception text that may contain arbitrary recorded data.
                            ci.decode_error_count += 1
                            issue(
                                "decode_error",
                                f"Message could not be decoded/validated ({type(exc).__name__}).",
                                ref,
                            )
                            if not known_log:
                                events.append(CoverageBreak(evidence=ref))
                        else:
                            ci.decoded_message_count += 1
                            events.extend(normalized)
                            # Lower severities are decoded for coverage, not retained as context.
                            if log is not None and log.level >= 30:
                                logs.append(log)
                            if diagnostic and not normalized:
                                issue(
                                    "empty_diagnostic_array",
                                    "Diagnostic array has no component statuses; "
                                    "health is unknown.",
                                    ref,
                                )
                    if len(events) + len(telemetry) + len(logs) > config.max_events:
                        raise ValueError(f"observation limit ({config.max_events}) exceeded")
            if stream.read(1):
                raise ValueError("trailing data after MCAP footer")
            if not header or not footer:
                raise ValueError("missing MCAP header or footer")
    except Exception as exc:
        raise RecordingError(f"Cannot analyze recording ({type(exc).__name__}): {exc}") from exc

    if not any(
        ci.decoded_message_count and ci.schema_name in DIAGNOSTIC_TYPES for ci in info.values()
    ):
        issue("no_diagnostics", "No decodable diagnostic messages; diagnostic health is unknown.")
    if not config.navigation_status_topics:
        issue(
            "navigation_not_configured",
            "Navigation detection requires explicitly configured status topics.",
        )
    for topic in config.navigation_status_topics:
        if not any(
            ci.topic == topic and ci.schema_name in STATUS_TYPES and ci.decoded_message_count
            for ci in info.values()
        ):
            issue(
                "navigation_unavailable:" + topic,
                f"No decodable navigation status messages on {topic}.",
            )
    if not config.expected_rates_hz:
        issue(
            "gap_detection_not_configured",
            "Telemetry gaps are not assessed without configured rates.",
        )
    for topic in config.expected_rates_hz:
        if sum(ci.message_count for ci in info.values() if ci.topic == topic) < 2:
            issue(
                "insufficient_telemetry:" + topic,
                f"Fewer than two messages on {topic}; cannot assess intervals.",
            )
    if context_enabled:
        for topic in config.log_topics:
            if not any(
                c.topic == topic and c.schema_name in LOG_TYPES and c.decoded_message_count
                for c in info.values()
            ):
                issue(
                    "log_context_unavailable:" + topic,
                    f"No decodable ROS Log messages on {topic}; nearby log context is unavailable.",
                )
    else:
        issue("log_context_disabled", "Nearby log context is disabled by configuration.")
    # Stable sorting preserves entry order within a DiagnosticArray/GoalStatusArray.
    events.sort(key=lambda e: (e.evidence.log_time_ns, e.evidence.message_index))
    telemetry.sort(key=lambda e: (e.log_time_ns, e.message_index))
    logs.sort(key=lambda entry: (entry.evidence.log_time_ns, entry.evidence.message_index))
    return Scan(
        recording=RecordingInfo(
            path=str(path),
            sha256=digest,
            size_bytes=size,
            profile=header.profile,
            library=header.library,
            message_count=count,
            start_time_ns=start,
            end_time_ns=end,
            channels=sorted(info.values(), key=lambda c: c.channel_id),
        ),
        events=events,
        telemetry=telemetry,
        coverage=list(issues.values()),
        logs=logs,
    )
