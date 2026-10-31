"""In-session delivery attempts. No message bodies, glucose or address history."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re


@dataclass
class Attempt:
    accepted: bool
    kind: str
    attempted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_type: str = ''
    reference: str = ''
    confirmed_manually: bool = False

    @property
    def description(self) -> str:
        time = self.attempted_at.astimezone().strftime('%H:%M')
        if not self.accepted:
            suffix = f' ({self.error_type})' if self.error_type else ''
            return f'{time}: request failed{suffix}'
        ref = f' ({self.reference})' if self.reference else ''
        if self.confirmed_manually:
            return f'{time}: recipient reply recorded manually{ref}'
        return f'{time}: request accepted; delivery unconfirmed{ref}'


class DeliveryTracker:
    def __init__(self) -> None:
        self.attempts: dict[str, Attempt] = {}

    def record(self, destination: str, *, accepted: bool, kind: str,
               error_type: str = '', now: datetime | None = None,
               reference: str = '') -> Attempt:
        if not destination or kind not in {'test', 'critical_low'}:
            raise ValueError('Invalid destination or attempt type')
        if not isinstance(accepted, bool):
            raise ValueError('Accepted must be true or false')
        if not isinstance(reference, str) or (reference and not re.fullmatch(r'LB-[0-9A-F]{16}', reference)):
            raise ValueError('Invalid request reference')
        # Error class name only. A raw service exception may carry addresses,
        # URLs or token fragments. Not useful to print that to the screen.
        safe_error = error_type if error_type in {
            'HomeAssistantError', 'TimeoutError', 'ConnectionError', 'ValueError'
        } else 'ServiceError' if error_type else ''
        attempt = Attempt(accepted=accepted, kind=kind,
                          attempted_at=now or datetime.now(timezone.utc),
                          error_type=safe_error if not accepted else '',
                          reference=reference)
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

    def summary(self, destinations: list[str]) -> str:
        attempts = [self.attempts[d] for d in destinations if d in self.attempts]
        if not attempts:
            return 'No message requests attempted this session. Use Test Selected, then ask the person.'
        accepted = sum(a.accepted for a in attempts)
        failed = len(attempts) - accepted
        replies = sum(a.confirmed_manually for a in attempts)
        return (f'{accepted} request(s) accepted, {failed} failed; {replies} manually recorded reply/replies. '
                'Requests are not delivery receipts. Only the latest attempt per contact is retained.')
