"""Minimal client for the NASA POWER daily point API.

Only the three parameters the model needs are requested. The network call is
isolated behind an injectable ``opener`` so that the parser can be tested
offline and so that a cached file can replace the API in an air-gapped run.

API documentation: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, datetime
from typing import Any, Protocol

from agroclim.climate import DailyRecord

__all__ = [
    "PARAMETERS",
    "POWER_ENDPOINT",
    "PowerAPIError",
    "build_request_url",
    "fetch_daily",
    "parse_power_payload",
]

POWER_ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"

#: POWER parameter codes: mean air temperature, corrected precipitation, relative humidity.
PARAMETERS: tuple[str, ...] = ("T2M", "PRECTOTCORR", "RH2M")


class PowerAPIError(RuntimeError):
    """Raised when the POWER service returns something the client cannot use."""


class Opener(Protocol):
    """Callable that returns the body of a URL as text."""

    def __call__(self, url: str, timeout: float) -> str:  # pragma: no cover - protocol
        ...


def build_request_url(
    latitude: float,
    longitude: float,
    start: date,
    end: date,
    parameters: tuple[str, ...] = PARAMETERS,
    community: str = "AG",
) -> str:
    """Build the POWER request URL for a point and a date range."""
    if end < start:
        raise ValueError("end date is before start date")
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("latitude must be in -90..90")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("longitude must be in -180..180")
    query = urllib.parse.urlencode(
        {
            "parameters": ",".join(parameters),
            "community": community,
            "latitude": f"{latitude:.4f}",
            "longitude": f"{longitude:.4f}",
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        }
    )
    return f"{POWER_ENDPOINT}?{query}"


def parse_power_payload(payload: dict[str, Any]) -> list[DailyRecord]:
    """Convert a POWER JSON payload into daily records.

    Missing values keep the POWER flag (-999) and are dropped later by
    :func:`agroclim.climate.season_records`.
    """
    try:
        parameters = payload["properties"]["parameter"]
        temperature = parameters["T2M"]
        precipitation = parameters["PRECTOTCORR"]
        humidity = parameters["RH2M"]
    except (KeyError, TypeError) as exc:
        raise PowerAPIError(f"unexpected POWER payload: {exc}") from exc

    records: list[DailyRecord] = []
    for stamp in sorted(temperature):
        try:
            day = datetime.strptime(stamp, "%Y%m%d").date()
        except ValueError as exc:
            raise PowerAPIError(f"unexpected date key {stamp!r}") from exc
        records.append(
            DailyRecord(
                day=day,
                t_mean=float(temperature[stamp]),
                precipitation=float(precipitation.get(stamp, -999.0)),
                relative_humidity=float(humidity.get(stamp, -999.0)),
            )
        )
    if not records:
        raise PowerAPIError("POWER payload contained no daily values")
    return records


def _default_opener(url: str, timeout: float) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body: str = response.read().decode("utf-8")
    return body


def fetch_daily(
    latitude: float,
    longitude: float,
    start: date,
    end: date,
    *,
    opener: Opener | Callable[[str, float], str] | None = None,
    timeout: float = 60.0,
) -> list[DailyRecord]:
    """Download daily records for a point from NASA POWER."""
    url = build_request_url(latitude, longitude, start, end)
    fetch = opener or _default_opener
    try:
        body = fetch(url, timeout)
    except OSError as exc:
        raise PowerAPIError(f"cannot reach the POWER service: {exc}") from exc
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PowerAPIError(f"POWER returned invalid JSON: {exc}") from exc
    return parse_power_payload(payload)
