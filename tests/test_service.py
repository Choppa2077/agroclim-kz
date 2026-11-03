"""Tests of the JSON HTTP service behind ``agroclim serve``."""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest

from agroclim import __version__, service
from agroclim.model import CROPS, FieldConditions
from agroclim.optimizer import recommend_sowing_date

WHEAT_QUERY = "crop=wheat&precipitation=139&humidity=55&previous=pea&year=2027&samples=200"


@pytest.fixture()
def base_url() -> Iterator[str]:
    server = service.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get(url: str) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        with exc:
            return exc.code, json.load(exc)


def test_healthz_reports_the_version(base_url) -> None:
    assert _get(f"{base_url}/healthz") == (200, {"status": "ok", "version": __version__})


def test_index_lists_the_endpoints(base_url) -> None:
    status, payload = _get(f"{base_url}/")
    assert status == 200
    assert payload["endpoints"] == ["/healthz", "/crops", "/recommend"]


def test_crops_lists_every_crop_with_its_window(base_url) -> None:
    status, payload = _get(f"{base_url}/crops")
    assert status == 200
    assert [crop["key"] for crop in payload["crops"]] == list(CROPS)
    wheat = payload["crops"][0]
    assert wheat["window_doy"] == [130, 150]


def test_recommend_matches_the_library_and_the_cli(base_url) -> None:
    status, payload = _get(f"{base_url}/recommend?{WHEAT_QUERY}")
    expected = recommend_sowing_date(
        "wheat", FieldConditions(139.0, 55.0, previous_crop="pea"), 2027, samples=200
    ).as_dict()
    assert status == 200
    assert payload == expected
    assert payload["sowing_date"] == "2027-05-15"


def test_recommend_is_reproducible(base_url) -> None:
    first = _get(f"{base_url}/recommend?{WHEAT_QUERY}&seed=7")
    second = _get(f"{base_url}/recommend?{WHEAT_QUERY}&seed=7")
    assert first == second


def test_recommend_defaults_to_the_current_year(base_url) -> None:
    status, payload = _get(f"{base_url}/recommend?crop=flax&precipitation=120&humidity=50")
    assert status == 200
    assert payload["crop"] == "flax"
    assert payload["year"] >= 2026


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("precipitation=139&humidity=55", "missing query parameter 'crop'"),
        ("crop=rice&precipitation=139&humidity=55", "unknown crop 'rice'"),
        ("crop=wheat&humidity=55", "missing query parameter 'precipitation'"),
        ("crop=wheat&precipitation=lots&humidity=55", "precipitation must be a number"),
        ("crop=wheat&precipitation=nan&humidity=55", "must be a finite number"),
        ("crop=wheat&precipitation=139&humidity=180", "relative humidity"),
        ("crop=wheat&precipitation=139&humidity=55&previous=rice", "unknown previous crop"),
        ("crop=wheat&precipitation=139&humidity=55&samples=5", "samples must be in 20-"),
        ("crop=wheat&precipitation=139&humidity=55&year=soon", "year must be an integer"),
        ("crop=wheat&precipitation=139&humidity=55&year=0", "year 0 is out of range"),
    ],
)
def test_recommend_rejects_bad_queries(base_url, query: str, message: str) -> None:
    status, payload = _get(f"{base_url}/recommend?{query}")
    assert status == 400
    assert message in payload["error"]


def test_unknown_path_is_404(base_url) -> None:
    status, payload = _get(f"{base_url}/predict")
    assert status == 404
    assert "/predict" in payload["error"]


def test_only_get_is_supported(base_url) -> None:
    request = urllib.request.Request(f"{base_url}/recommend", data=b"{}", method="POST")
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(request, timeout=5)
    excinfo.value.close()
    assert excinfo.value.code == 501


def test_access_log_goes_through_logging(base_url, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="agroclim.service"):
        _get(f"{base_url}/healthz")
    assert any("GET /healthz" in record.getMessage() for record in caplog.records)


@pytest.mark.skipif(sys.platform == "win32", reason="relies on POSIX signal delivery")
def test_serve_stops_cleanly_on_sigterm(monkeypatch, caplog) -> None:
    created: list[Any] = []
    original_make_server = service.make_server

    def recording_make_server(host: str, port: int) -> Any:
        server = original_make_server(host, port)
        created.append(server)
        return server

    def terminate_when_ready() -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if created:
                url = f"http://127.0.0.1:{created[0].server_port}/healthz"
                try:
                    urllib.request.urlopen(url, timeout=1).close()
                except OSError:
                    pass
                else:
                    # serve() answers only after its signal handlers are in place
                    os.kill(os.getpid(), signal.SIGTERM)
                    return
            time.sleep(0.05)

    monkeypatch.setattr(service, "make_server", recording_make_server)
    handler_before = signal.getsignal(signal.SIGTERM)
    helper = threading.Thread(target=terminate_when_ready, daemon=True)
    helper.start()
    with caplog.at_level(logging.INFO, logger="agroclim.service"):
        assert service.serve("127.0.0.1", 0) == 0
    helper.join(timeout=5)
    assert signal.getsignal(signal.SIGTERM) == handler_before
    messages = [record.getMessage() for record in caplog.records]
    assert any("listening on http://127.0.0.1:" in message for message in messages)
    assert any("shutting down" in message for message in messages)
