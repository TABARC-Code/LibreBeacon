"""In-session contact attempt records; no health readings or addresses stored."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Attempt:
    accepted: bool
    kind: str
    confirmed_manually: bool = False

    @property
    def description(self) -> str:
        if not self.accepted:
            return 'request failed'
        if self.confirmed_manually:
            return 'recipient confirmation recorded manually'
        return 'request accepted; delivery unconfirmed'


class DeliveryTracker:
    def __init__(self) -> None:
        self.attempts: dict[str, Attempt] = {}

    def record(self, destination: str, *, accepted: bool, kind: str) -> Attempt:
        if not destination or kind not in {'test', 'critical_low'}:
            raise ValueError('Invalid destination or attempt type')
        attempt = Attempt(accepted=accepted, kind=kind)
        self.attempts[destination] = attempt
        return attempt

    def confirm(self, destination: str) -> None:
        attempt = self.attempts.get(destination)
        if attempt is None or not attempt.accepted:
            raise ValueError('Send a test first and confirm with the recipient outside this app')
        attempt.confirmed_manually = True

    def description(self, destination: str) -> str:
        attempt = self.attempts.get(destination)
        return attempt.description if attempt else 'not tested this session'
