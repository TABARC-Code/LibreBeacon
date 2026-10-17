"""Read already-authorised Home Assistant entities; never scrape Phone Link."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

MGDL_PER_MMOLL = 18.0182


class SourceError(Exception):
    """An unreadable, missing or invalid glucose source."""


@dataclass(frozen=True)
class Reading:
    mmol_l: float
    measured_at: datetime


def parse_reading(glucose: dict, timestamp: dict) -> Reading:
    try:
        raw = glucose["state"]
        unit = glucose["attributes"]["unit_of_measurement"]
        if isinstance(raw, bool):
            raise ValueError("Boolean readings are invalid")
        value = float(raw)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Reading is not a positive finite number")
        unit = str(unit).strip().lower().replace(" ", "")
        if unit == "mmol/l":
            mmol_l = value
        elif unit in ("mg/dl", "mgdl"):
            mmol_l = value / MGDL_PER_MMOLL
        else:
            raise ValueError("Unrecognised glucose unit")
        if mmol_l > 50:
            raise ValueError("Reading outside accepted parsing range")
        stamp = timestamp["state"]
        measured = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if measured.tzinfo is None or measured.utcoffset() is None:
            raise ValueError("Timestamp requires timezone")
        return Reading(mmol_l, measured)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise SourceError("Glucose or actual measurement timestamp is invalid/unavailable") from exc


class HomeAssistant:
    def __init__(self, url: str | None = None, token: str | None = None):
        self.url = (url or os.getenv("LIBREBEACON_HA_URL", "")).rstrip("/")
        self.token = token or os.getenv("LIBREBEACON_HA_TOKEN", "")
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise SourceError("Set LIBREBEACON_HA_URL to your Home Assistant base URL")
        if not self.token:
            raise SourceError("Set LIBREBEACON_HA_TOKEN in your environment")

    def request(self, endpoint: str, data: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(self.url + endpoint, method="POST" if data is not None else "GET",
                      data=json.dumps(data).encode("utf-8") if data is not None else None,
                      headers=headers)
        try:
            with urlopen(req, timeout=7) as response:
                body = response.read(2_000_000)
            result = json.loads(body)
            return result
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            raise SourceError("Home Assistant request failed (check connection, entity and token)") from exc

    def read(self, glucose_entity: str, timestamp_entity: str) -> Reading:
        # A separate actual measurement timestamp is mandatory. Home Assistant's
        # last_updated often refers to polling, NOT when the CGM measured blood glucose.
        glucose = self.request("/api/states/" + quote(glucose_entity, safe="."))
        timestamp = self.request("/api/states/" + quote(timestamp_entity, safe="."))
        return parse_reading(glucose, timestamp)

    def call(self, domain: str, action: str, payload: dict) -> None:
        if domain not in {"light", "notify", "tts"}:
            raise ValueError("Unsupported action domain")
        self.request(f"/api/services/{domain}/{action}", payload)
