"""Attach bounded recorded log context without changing deterministic findings."""

import heapq
from bisect import bisect_left, bisect_right
from fractions import Fraction

from .ingestion import LOG_TYPES, Scan
from .models import AnalysisConfig, Incident, LogContext


def attach_log_context(incidents: list[Incident], scan: Scan, config: AnalysisConfig) -> None:
    enabled = bool(config.log_topics) and config.context_window_seconds > 0
    channels = [c for c in scan.recording.channels if c.topic in config.log_topics]
    available_topics = {
        c.topic for c in channels if c.schema_name in LOG_TYPES and c.decoded_message_count
    }
    if not enabled:
        availability = "disabled"
    elif not available_topics:
        availability = "unavailable"
    elif available_topics != set(config.log_topics) or any(
        c.decode_error_count or c.skipped_message_count for c in channels
    ):
        availability = "partial"
    else:
        availability = "available"
    window_ns = int(Fraction(str(config.context_window_seconds)) * 10**9)
    times = [entry.evidence.log_time_ns for entry in scan.logs]
    for incident in incidents:
        start = max(0, incident.start_time_ns - window_ns)
        end = incident.start_time_ns + window_ns
        left, right = (bisect_left(times, start), bisect_right(times, end)) if enabled else (0, 0)
        nearest = heapq.nsmallest(
            config.max_context_logs,
            (scan.logs[i] for i in range(left, right)),
            key=lambda entry: (
                abs(entry.evidence.log_time_ns - incident.start_time_ns),
                entry.evidence.log_time_ns,
                entry.evidence.message_index,
            ),
        )
        nearest.sort(key=lambda entry: (entry.evidence.log_time_ns, entry.evidence.message_index))
        limitations = [
            "Logs are associated by MCAP log-time proximity only; they may be unrelated "
            "and do not establish a cause or create an incident.",
            "The window surrounds the first observed incident timestamp, not its entire duration.",
            "Source log stamps are preserved separately; clock differences and delayed delivery "
            "can distort proximity. Absence of recorded logs is not evidence of no errors.",
        ]
        if availability in ("unavailable", "partial"):
            limitations.append(
                "Configured log data is absent or incompletely decodable; "
                "the context may omit relevant logs."
            )
        if (
            scan.recording.start_time_ns is not None
            and start < scan.recording.start_time_ns
            or scan.recording.end_time_ns is not None
            and end > scan.recording.end_time_ns
        ):
            limitations.append("The recording does not span the entire requested context window.")
        incident.log_context = LogContext(
            availability=availability,
            window_start_time_ns=start,
            window_end_time_ns=end,
            matching_log_count=right - left,
            omitted_log_count=right - left - len(nearest),
            logs=nearest,
            limitations=limitations,
        )
