"""Deterministic, testable alert decisions. Not clinical risk prediction."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from .settings import Settings
from .source import Reading


class Status(str, Enum):
    NORMAL = "NORMAL"
    LOW = "LOW"
    HIGH = "HIGH"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    UNCONFIGURED = "UNCONFIGURED"


@dataclass(frozen=True)
class Decision:
    status: Status
    local_alarm: bool = False
    home_alert: bool = False
    contact_alert: bool = False
    acknowledged: bool = False
    details: str = ""


def classify(reading: Reading | None, now: datetime, settings: Settings) -> Status:
    if reading is None:
        return Status.UNAVAILABLE
    elapsed = now.astimezone(timezone.utc) - reading.measured_at.astimezone(timezone.utc)
    # A future measurement also indicates an unreliable device/server clock.
    if elapsed < timedelta(minutes=-2) or elapsed > timedelta(minutes=settings.stale_minutes):
        return Status.STALE
    if settings.low_mmol is None or settings.high_mmol is None:
        return Status.UNCONFIGURED
    if reading.mmol_l < settings.low_mmol:
        return Status.LOW
    if reading.mmol_l > settings.high_mmol:
        return Status.HIGH
    return Status.NORMAL


class RuleEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.status: Status | None = None
        self.since: datetime | None = None
        self.last_alarm: datetime | None = None
        self.sent_contact = False
        self.ack = False
        self.normal_samples = 0

    def acknowledge(self) -> None:
        # Acknowledgement silences LibreBeacon's supplementary notices for this episode.
        self.ack = True

    def check(self, reading: Reading | None, now: datetime) -> Decision:
        status = classify(reading, now, self.settings)
        if status is Status.NORMAL and self.status in {Status.LOW, Status.HIGH}:
            # Keep current episode until two consecutive fresh, normal samples.
            self.normal_samples += 1
            if self.normal_samples < 2:
                status = self.status
        else:
            self.normal_samples = 0
        if status != self.status:
            self.status = status
            self.since = now
            self.last_alarm = None
            self.sent_contact = False
            self.ack = False
        is_warning = status in {Status.LOW, Status.HIGH, Status.STALE, Status.UNAVAILABLE}
        interval = timedelta(minutes=self.settings.repeat_minutes)
        due = is_warning and not self.ack and (self.last_alarm is None or now - self.last_alarm >= interval)
        if due:
            self.last_alarm = now
        contacts_due = (
            status in {Status.LOW, Status.HIGH}
            and not self.sent_contact and not self.ack
            and self.since is not None
            and now - self.since >= timedelta(minutes=self.settings.escalation_minutes)
        )
        if contacts_due:
            self.sent_contact = True
        return Decision(status=status, local_alarm=due, home_alert=due,
                        contact_alert=contacts_due, acknowledged=self.ack,
                        details="Supplementary notice only; check official Libre alarms.")
