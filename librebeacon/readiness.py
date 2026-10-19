"""Plain-language checks for the first-run setup screen."""
from __future__ import annotations

from dataclasses import dataclass
import math
from .settings import Settings
from .contacts import read_routes


@dataclass(frozen=True)
class SetupCheck:
    title: str
    ready: bool
    explanation: str


def setup_checks(settings: Settings, has_token: bool) -> list[SetupCheck]:
    connection = bool(settings.ha_url.strip() and has_token)
    sensors = bool(settings.glucose_entity.strip() and settings.timestamp_entity.strip()
                   and settings.glucose_entity != settings.timestamp_entity)
    thresholds = False
    try:
        low = float(settings.low_mmol)
        high = float(settings.high_mmol)
        thresholds = math.isfinite(low) and math.isfinite(high) and 0 < low < high <= 60
        if settings.critical_low_mmol:
            critical = float(settings.critical_low_mmol)
            thresholds = thresholds and math.isfinite(critical) and 0 < critical < low
    except (ValueError, TypeError):
        pass
    accessibility = bool(settings.enable_sound or settings.enable_speech or
                         settings.enable_visual or settings.enable_ha_visual)
    contacts = False
    try:
        routes = read_routes(settings.emergency_routes)
        contacts = bool(routes and all(route.consent for route in routes))
    except (TypeError, ValueError):
        pass
    return [
        SetupCheck('Connection', connection, 'Save the Home Assistant address and token, then test the connection.'),
        SetupCheck('Sensor selection', sensors, 'Select glucose and the genuine measurement-time sensor; test a reading.'),
        SetupCheck('Alert thresholds', thresholds, 'Enter agreed low/high thresholds in Alert rules; do not guess.'),
        SetupCheck('Local accessibility', accessibility, 'Choose sound, speech or visual notices and test each device.'),
        SetupCheck('Emergency contacts (optional)', contacts, 'Add consented contacts, test delivery and ask each to reply.'),
    ]
