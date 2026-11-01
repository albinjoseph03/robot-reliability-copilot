"""Stateful deterministic rules; no automatic discovery or external code loading."""

from typing import Protocol

from ..models import Event, Incident


class Detector(Protocol):
    def observe(self, event: Event) -> None: ...

    def finish(self) -> list[Incident]: ...
