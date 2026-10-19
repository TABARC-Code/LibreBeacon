"""Connection and reading-age diagnostics for the desktop display.

A successful poll is not proof of a recent measurement. Keep those two
clocks separate; older integrations can refresh an unchanged sensor state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta


@dataclass(frozen=True)
class HealthReport:
    state: str
    detail: str


@dataclass
class ConnectionHealth:
    measured_at: datetime | None = None
    last_success: datetime | None = None
    last_failure: datetime | None = None
    consecutive_failures: int = 0

    def success(self, measured_at: datetime, now: datetime) -> None:
        if measured_at.tzinfo is None or now.tzinfo is None:
            raise ValueError('Measurement and current time must contain time zones')
        self.measured_at = measured_at.astimezone(timezone.utc)
        self.last_success = now.astimezone(timezone.utc)
        self.consecutive_failures = 0
        self.last_failure = None

    def failure(self, now: datetime) -> None:
        if now.tzinfo is None:
            raise ValueError('Current time must contain a time zone')
        self.last_failure = now.astimezone(timezone.utc)
        self.consecutive_failures += 1

    def report(self, now: datetime, max_age_minutes: int) -> HealthReport:
        if self.last_failure is not None:
            return HealthReport('UNAVAILABLE',
                f'Home Assistant reading failed ({self.consecutive_failures} consecutive attempt(s)). '
                'Check the phone, network and connection. Keep official Libre alarms active.')
        if self.measured_at is None:
            return HealthReport('NOT CHECKED', 'No verified sensor reading has been received this session.')
        age = now.astimezone(timezone.utc) - self.measured_at
        if age < timedelta(minutes=-2):
            return HealthReport('CLOCK ERROR', 'The sensor timestamp is in the future. Check clock settings.')
        if age > timedelta(minutes=max_age_minutes):
            return HealthReport('STALE', f'Last sensor measurement is {age.total_seconds()/60:.0f} minutes old. '
                                 'The displayed number is hidden until a fresh reading arrives.')
        return HealthReport('CURRENT', f'Last sensor measurement {max(0, age.total_seconds()/60):.0f} minutes ago. '
                               'Connected here does not mean an emergency message was delivered.')
