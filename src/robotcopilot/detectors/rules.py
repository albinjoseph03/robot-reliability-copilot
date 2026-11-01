import hashlib
from fractions import Fraction

from ..models import (
    CoverageBreak,
    DiagnosticEvent,
    Event,
    Evidence,
    GoalStatusEvent,
    Incident,
)


def incident_id(detector: str, ref: Evidence) -> str:
    identity = f"{detector}:{ref.channel_id}:{ref.message_index}:{ref.field_path}"
    return "inc-" + hashlib.sha256(identity.encode()).hexdigest()[:16]


class DiagnosticTransitions:
    name = "diagnostic_severity_transitions/v1"

    def __init__(self) -> None:
        self._active: dict[tuple[str, str, str], tuple[int, Incident]] = {}
        self._incidents: list[Incident] = []

    def observe(self, event: Event) -> None:
        if isinstance(event, CoverageBreak):
            # Do not infer recovery or persistence across an undecoded message.
            self._active = {k: v for k, v in self._active.items() if k[0] != event.evidence.topic}
            return
        if not isinstance(event, DiagnosticEvent):
            return
        ref = event.evidence
        key = (ref.topic, event.component, event.hardware_id)
        previous = self._active.get(key)
        if previous and previous[0] == event.level:
            incident = previous[1]
            incident.occurrences += 1
            incident.last_observed_time_ns = ref.log_time_ns
            # Keep the first and most recent observation, rather than unbounded duplicates.
            incident.evidence[:] = [incident.evidence[0], ref]
            return
        if previous:
            incident = previous[1]
            incident.end_time_ns = ref.log_time_ns
            incident.evidence.append(ref)
            incident.observations["next_observed_level"] = event.level
            del self._active[key]
        if event.level == 0:
            return
        level_name = {1: "WARN", 2: "ERROR", 3: "STALE"}[event.level]
        incident = Incident(
            id=incident_id(self.name, ref),
            category="diagnostic",
            severity="error" if event.level == 2 else "warning",
            detector=self.name,
            start_time_ns=ref.log_time_ns,
            last_observed_time_ns=ref.log_time_ns,
            component=event.component,
            explanation=f"Component {event.component!r} reported {level_name}: {event.message}",
            observations={
                "level": event.level,
                "level_name": level_name,
                "hardware_id": event.hardware_id,
                "message": event.message,
                "header_time_ns": event.header_time_ns,
                "values": event.values,
            },
            evidence=[ref],
            limitations=[
                "A reported diagnostic severity is an observation, "
                "not a verified physical root cause.",
                "Start is the first observed message at this severity, not necessarily onset.",
                "End, if present, is a later observed severity change; absence is not recovery.",
                "Same-level repeats are aggregated; changes in message text "
                "do not create incidents.",
            ],
            recommended_steps=[
                "Inspect the referenced component, hardware ID and diagnostic key/value fields.",
                "Correlate component logs and measurements at the recorded log/header times.",
                "Verify the condition independently and check subsequent diagnostic state.",
            ],
        )
        self._incidents.append(incident)
        self._active[key] = (event.level, incident)

    def finish(self) -> list[Incident]:
        return self._incidents


class NavigationAborts:
    name = "navigation_action_aborted/v1"

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()
        self._incidents: list[Incident] = []

    def observe(self, event: Event) -> None:
        if not isinstance(event, GoalStatusEvent) or event.status != 6:
            return
        key = (event.evidence.topic, event.goal_id)
        if key in self._seen:
            return
        self._seen.add(key)
        ref = event.evidence
        self._incidents.append(
            Incident(
                id=incident_id(self.name, ref),
                category="navigation",
                severity="error",
                detector=self.name,
                start_time_ns=ref.log_time_ns,
                last_observed_time_ns=ref.log_time_ns,
                evidence=[ref],
                explanation=f"Navigation goal {event.goal_id} reported action status ABORTED (6).",
                observations={
                    "goal_id": event.goal_id,
                    "status": event.status,
                    "goal_stamp_ns": event.goal_stamp_ns,
                },
                limitations=[
                    "Navigation context comes from the explicitly configured status topic.",
                    "ABORTED is server-reported termination; no Nav2 result code "
                    "or root cause is inferred.",
                    "Start is first observed abort status; actual termination time may be earlier.",
                    "Succeeded/canceled/rejected goals and action service results "
                    "are not failure evidence here.",
                ],
                recommended_steps=[
                    "Match the goal UUID with the action client result and Nav2 server logs.",
                    "Inspect planner/controller errors, transforms and costmaps "
                    "before assigning a cause.",
                ],
            )
        )

    def finish(self) -> list[Incident]:
        return self._incidents


def telemetry_gaps(refs: list[Evidence], rates: dict[str, float], factor: float) -> list[Incident]:
    previous: dict[str, Evidence] = {}
    result: list[Incident] = []
    for ref in refs:
        prior = previous.get(ref.topic)
        previous[ref.topic] = ref
        if prior is None:
            continue
        interval = ref.log_time_ns - prior.log_time_ns
        threshold = Fraction(10**9) * Fraction(str(factor)) / Fraction(str(rates[ref.topic]))
        if interval <= threshold:
            continue
        name = "configured_telemetry_gap/v1"
        result.append(
            Incident(
                id=incident_id(name, ref),
                category="missing_telemetry",
                severity="warning",
                detector=name,
                start_time_ns=prior.log_time_ns,
                end_time_ns=ref.log_time_ns,
                last_observed_time_ns=ref.log_time_ns,
                evidence=[prior, ref],
                explanation=(
                    f"Observed interval of {interval} ns on {ref.topic} exceeds "
                    f"{factor} configured periods at {rates[ref.topic]} Hz."
                ),
                observations={
                    "interval_ns": interval,
                    "expected_rate_hz": str(rates[ref.topic]),
                    "gap_factor": str(factor),
                },
                limitations=[
                    "Interval boundaries are adjacent recorded messages, "
                    "not exact outage onset/recovery.",
                    "Recording silence can reflect QoS, transport, recorder pause/drop "
                    "or intentional inactivity.",
                    "Only configured rates are used; absent topics and recording "
                    "boundaries are not inferred gaps.",
                ],
                recommended_steps=[
                    "Confirm the topic was expected to publish continuously during this interval.",
                    "Check recorder pause/drop statistics, QoS, clock jumps and publisher logs.",
                ],
            )
        )
    return result
