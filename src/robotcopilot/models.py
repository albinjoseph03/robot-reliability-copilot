"""Public report contracts. Timestamps are exact integers, never float seconds."""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Model):
    message_index: int = Field(ge=1, description="One-based physical message traversal ordinal")
    channel_id: int
    sequence: int
    topic: str
    schema_name: str | None
    log_time_ns: int
    publish_time_ns: int
    field_path: str = ""


class DiagnosticEvent(Model):
    kind: Literal["diagnostic"] = "diagnostic"
    evidence: Evidence
    header_time_ns: int
    component: str
    hardware_id: str
    level: int
    message: str
    values: list[tuple[str, str]] = Field(default_factory=list)


class GoalStatusEvent(Model):
    kind: Literal["goal_status"] = "goal_status"
    evidence: Evidence
    goal_id: str
    goal_stamp_ns: int
    status: int


class CoverageBreak(Model):
    kind: Literal["coverage_break"] = "coverage_break"
    evidence: Evidence


Event = DiagnosticEvent | GoalStatusEvent | CoverageBreak


class Incident(Model):
    id: str
    category: Literal["diagnostic", "navigation", "missing_telemetry"]
    severity: Literal["warning", "error"]
    detector: str
    start_time_ns: int
    end_time_ns: int | None = None
    last_observed_time_ns: int
    occurrences: int = 1
    component: str | None = None
    explanation: str
    observations: dict[str, str | int | list[tuple[str, str]]] = Field(default_factory=dict)
    evidence: list[Evidence]
    limitations: list[str]
    hypotheses: list[str] = Field(default_factory=list)
    recommended_steps: list[str]


class ChannelInfo(Model):
    channel_id: int
    topic: str
    schema_name: str | None
    schema_encoding: str | None
    message_encoding: str
    message_count: int = 0
    decoded_message_count: int = 0
    skipped_message_count: int = 0
    decode_error_count: int = 0
    start_time_ns: int | None = None
    end_time_ns: int | None = None


class CoverageIssue(Model):
    code: str
    message: str
    channel_id: int | None = None
    count: int = 1
    first_evidence: Evidence | None = None


class RecordingInfo(Model):
    path: str
    sha256: str
    size_bytes: int
    profile: str
    library: str
    message_count: int
    start_time_ns: int | None
    end_time_ns: int | None
    channels: list[ChannelInfo]


class AnalysisConfig(Model):
    navigation_status_topics: list[str] = Field(default_factory=list)
    expected_rates_hz: dict[str, float] = Field(default_factory=dict)
    gap_factor: float = Field(default=3.0, gt=1, allow_inf_nan=False)
    max_messages: int = Field(default=1_000_000, ge=1)
    max_events: int = Field(default=1_000_000, ge=1)
    max_record_bytes: int = Field(default=64 * 1024 * 1024, ge=1)

    @field_validator("navigation_status_topics")
    @classmethod
    def valid_navigation_topics(cls, topics: list[str]) -> list[str]:
        if any(not topic.startswith("/") for topic in topics):
            raise ValueError("navigation topics must be absolute ROS topic names")
        return list(dict.fromkeys(topics))

    @field_validator("expected_rates_hz")
    @classmethod
    def valid_rates(cls, rates: dict[str, float]) -> dict[str, float]:
        for topic, rate in rates.items():
            if not topic.startswith("/") or not math.isfinite(rate) or not 0 < rate <= 1e9:
                raise ValueError(
                    "expected rates require absolute topics and finite rates in (0, 1e9]"
                )
        return rates


class Report(Model):
    report_version: Literal["0.1"] = "0.1"
    tool_version: str
    recording: RecordingInfo
    config: AnalysisConfig
    summary: str
    time_basis: str = "MCAP log time; integer nanoseconds; not necessarily wall-clock UTC"
    evidence_identity: str = "recording SHA-256 + message_index + field_path"
    coverage: list[CoverageIssue]
    incidents: list[Incident]
    limitations: list[str]
