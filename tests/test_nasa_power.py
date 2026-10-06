"""Tests for the NASA POWER client (offline: the opener is injected)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from agroclim.nasa_power import (
    PowerAPIError,
    build_request_url,
    fetch_daily,
    parse_power_payload,
)

PAYLOAD = {
    "properties": {
        "parameter": {
            "T2M": {"20240501": 12.3, "20240502": 14.1},
            "PRECTOTCORR": {"20240501": 0.0, "20240502": 4.2},
            "RH2M": {"20240501": 48.0, "20240502": 61.5},
        }
    }
}


def test_build_request_url_contains_every_parameter() -> None:
    url = build_request_url(51.5864, 70.8406, date(2024, 5, 1), date(2024, 8, 31))
    assert url.startswith("https://power.larc.nasa.gov/api/temporal/daily/point?")
    for parameter in ("T2M", "PRECTOTCORR", "RH2M"):
        assert parameter in url
    assert "start=20240501" in url and "end=20240831" in url


def test_build_request_url_validates_the_range() -> None:
    with pytest.raises(ValueError, match="end date"):
        build_request_url(51.0, 70.0, date(2024, 8, 31), date(2024, 5, 1))


@pytest.mark.parametrize(("lat", "lon"), [(100.0, 0.0), (0.0, 200.0)])
def test_build_request_url_validates_the_point(lat: float, lon: float) -> None:
    with pytest.raises(ValueError):
        build_request_url(lat, lon, date(2024, 5, 1), date(2024, 5, 2))


def test_parse_power_payload_returns_sorted_records() -> None:
    records = parse_power_payload(PAYLOAD)
    assert [r.day for r in records] == [date(2024, 5, 1), date(2024, 5, 2)]
    assert records[1].precipitation == pytest.approx(4.2)


def test_parse_power_payload_keeps_the_missing_flag() -> None:
    payload = json.loads(json.dumps(PAYLOAD))
    payload["properties"]["parameter"]["RH2M"] = {"20240501": -999.0}
    records = parse_power_payload(payload)
    assert records[0].is_complete() is False


def test_parse_power_payload_rejects_a_foreign_document() -> None:
    with pytest.raises(PowerAPIError, match="unexpected POWER payload"):
        parse_power_payload({"hello": "world"})


def test_parse_power_payload_rejects_an_empty_series() -> None:
    with pytest.raises(PowerAPIError, match="no daily values"):
        parse_power_payload(
            {"properties": {"parameter": {"T2M": {}, "PRECTOTCORR": {}, "RH2M": {}}}}
        )


def test_parse_power_payload_rejects_a_bad_date_key() -> None:
    payload = {"properties": {"parameter": {"T2M": {"May1": 1.0}, "PRECTOTCORR": {}, "RH2M": {}}}}
    with pytest.raises(PowerAPIError, match="unexpected date key"):
        parse_power_payload(payload)


def test_fetch_daily_uses_the_injected_opener() -> None:
    seen: dict[str, object] = {}

    def opener(url: str, timeout: float) -> str:
        seen["url"] = url
        seen["timeout"] = timeout
        return json.dumps(PAYLOAD)

    records = fetch_daily(51.5864, 70.8406, date(2024, 5, 1), date(2024, 5, 2), opener=opener)
    assert len(records) == 2
    assert "latitude=51.5864" in str(seen["url"])


def test_fetch_daily_wraps_network_errors() -> None:
    def opener(url: str, timeout: float) -> str:
        raise OSError("name or service not known")

    with pytest.raises(PowerAPIError, match="cannot reach the POWER service"):
        fetch_daily(51.0, 70.0, date(2024, 5, 1), date(2024, 5, 2), opener=opener)


def test_fetch_daily_rejects_invalid_json() -> None:
    with pytest.raises(PowerAPIError, match="invalid JSON"):
        fetch_daily(
            51.0,
            70.0,
            date(2024, 5, 1),
            date(2024, 5, 2),
            opener=lambda _url, _timeout: "<html>maintenance</html>",
        )
