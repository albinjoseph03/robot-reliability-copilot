from pathlib import Path

from . import __version__
from .context import attach_log_context
from .detectors import Detector
from .detectors.rules import DiagnosticTransitions, NavigationAborts, telemetry_gaps
from .ingestion import scan_recording
from .models import AnalysisConfig, Report


def analyze(path: Path, config: AnalysisConfig | None = None) -> Report:
    config = config or AnalysisConfig()
    scan = scan_recording(path, config)
    detectors: list[Detector] = [DiagnosticTransitions(), NavigationAborts()]
    for event in scan.events:
        for detector in detectors:
            detector.observe(event)
    incidents = [incident for detector in detectors for incident in detector.finish()]
    incidents.extend(telemetry_gaps(scan.telemetry, config.expected_rates_hz, config.gap_factor))
    incidents.sort(key=lambda i: (i.start_time_ns, i.evidence[0].message_index))
    attach_log_context(incidents, scan, config)
    errors = sum(i.severity == "error" for i in incidents)
    warnings = len(incidents) - errors
    return Report(
        tool_version=__version__,
        recording=scan.recording,
        config=config,
        summary=(
            f"{scan.recording.message_count} recorded messages; {len(incidents)} incidents "
            f"({errors} error, {warnings} warning). "
            "Only supported, enabled detectors were assessed; this is not a robot health verdict."
        ),
        coverage=scan.coverage,
        incidents=incidents,
        limitations=[
            "Chronology uses MCAP log time; clock resets or mixed clock domains "
            "can distort ordering.",
            "No causal correlation, real-world activity reconstruction or "
            "root-cause inference is performed.",
            "Unsupported payloads and missing evidence cannot establish that a robot was healthy.",
            "CRC validation covers checksums present in the file, not authenticity "
            "or every structural invariant.",
            "Resource limits are guardrails; use OS isolation for hostile files "
            "or decompression bombs.",
        ],
    )
