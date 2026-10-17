"""Validated readings and an intentionally conservative alert state machine."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import math

MG_DL_PER_MMOL = 18.0182

class ReadingError(ValueError):
    pass

@dataclass(frozen=True)
class Reading:
    mmol: float
    measured_at: datetime
    raw_unit: str

    def age_minutes(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        return (now - self.measured_at).total_seconds() / 60

    def validated(self, maximum_age: float, now: datetime | None = None) -> 'Reading':
        age = self.age_minutes(now)
        if age < -2 or age > maximum_age:
            raise ReadingError(f"Reading is outside permitted age ({age:.1f} minutes)")
        return self


def decode_reading(glucose_state: dict, timestamp_state: dict) -> Reading:
    try:
        raw = glucose_state['state']
        mmol = float(raw)
        if not math.isfinite(mmol):
            raise ValueError('non-finite')
        unit = str(glucose_state['attributes']['unit_of_measurement']).strip().lower()
        if unit in {'mmol/l', 'mmol/litre', 'mmol/liter'}:
            pass
        elif unit in {'mg/dl'}:
            mmol /= MG_DL_PER_MMOL
        else:
            raise ValueError('unrecognised or missing glucose unit')
        if mmol <= 0 or mmol > 60:
            raise ValueError('implausible glucose value')
        date_text = timestamp_state['state']
        stamp = datetime.fromisoformat(date_text.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('timestamp has no timezone')
        return Reading(mmol=mmol, measured_at=stamp.astimezone(timezone.utc), raw_unit=unit)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ReadingError(f'Unusable reading: {exc}') from exc

@dataclass
class AlertEngine:
    """One alert per continuous low/high episode, with cooldown on state changes.

    Stale, missing and invalid readings NEVER become glucose alarms.
    Transitions to normal reset the episode; repeat requires a new episode.
    """
    prior: str = 'unknown'
    last_sent: datetime | None = None
    last_sent_event: str | None = None

    def observe(self, reading: Reading, low: float, high: float, max_age: float,
                now: datetime | None = None, cooldown_minutes: float = 15,
                critical_low: float | None = None) -> str | None:
        now = now or datetime.now(timezone.utc)
        reading.validated(max_age, now)
        if not (0 < low < high <= 60):
            raise ValueError('Thresholds must be valid and ordered')
        if critical_low is not None and not (0 < critical_low < low):
            raise ValueError('Critical-low threshold must be below the low threshold')
        event = ('critical_low' if critical_low is not None and reading.mmol < critical_low
                 else 'low' if reading.mmol < low else 'high' if reading.mmol > high
                 else 'normal')
        if event == 'normal':
            self.prior = 'normal'
            return None
        if event == self.prior:
            return None
        previous = self.prior
        self.prior = event
        # Improving from critical to low is not another emergency. Keep it quiet.
        if previous == 'critical_low' and event == 'low':
            return None
        # Distinct high/low states must not silence one another via global cooldown.
        if (event == self.last_sent_event and self.last_sent is not None
                and (now-self.last_sent).total_seconds() < cooldown_minutes * 60):
            return None
        self.last_sent = now
        self.last_sent_event = event
        return event

    def invalidate(self) -> None:
        """Unknown data cannot silently resolve an active glucose episode."""
        # Preserve the last episode to avoid treating a cloud outage/reconnect as a new alarm.
        return
