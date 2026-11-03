"""HTTP interface of agroclim for the platform back end and for Kubernetes.

``agroclim serve`` exposes the computation behind ``agroclim recommend`` as a
small JSON API, so the web back end of the platform (or any other client) can
ask for a recommendation over the network:

* ``GET /healthz`` - liveness and readiness probe, returns the package version;
* ``GET /crops`` - the supported crops and their published sowing windows;
* ``GET /recommend?crop=wheat&precipitation=139&humidity=55`` - a recommendation.
  The optional parameters mirror the command line: ``year``, ``nitrogen``,
  ``ph``, ``previous``, ``seed`` and ``samples``.

The server is built on :mod:`http.server`, so the package keeps its promise of
no third-party dependencies. It is meant to run inside a cluster behind a
Service or an ingress, not to face the internet directly.
"""

from __future__ import annotations

import json
import logging
import math
import signal
import threading
from collections.abc import Mapping
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from agroclim import __version__
from agroclim.model import CROPS, FieldConditions
from agroclim.optimizer import recommend_sowing_date

__all__ = ["MAX_SAMPLES", "QueryError", "make_server", "recommend_from_query", "serve"]

LOGGER = logging.getLogger(__name__)

#: Upper bound of Monte-Carlo draws per request, so one call cannot hog a worker.
MAX_SAMPLES = 20_000

ENDPOINTS = ("/healthz", "/crops", "/recommend")


class QueryError(ValueError):
    """A query string that cannot be turned into a recommendation."""


def _param(query: Mapping[str, list[str]], name: str, default: str | None = None) -> str:
    values = query.get(name)
    if values:
        return values[-1]
    if default is None:
        raise QueryError(f"missing query parameter {name!r}")
    return default


def _float(query: Mapping[str, list[str]], name: str, default: str | None = None) -> float:
    raw = _param(query, name, default)
    try:
        value = float(raw)
    except ValueError:
        raise QueryError(f"{name} must be a number, got {raw!r}") from None
    if not math.isfinite(value):
        raise QueryError(f"{name} must be a finite number, got {raw!r}")
    return value


def _int(query: Mapping[str, list[str]], name: str, default: str) -> int:
    raw = _param(query, name, default)
    try:
        return int(raw)
    except ValueError:
        raise QueryError(f"{name} must be an integer, got {raw!r}") from None


def recommend_from_query(
    query: Mapping[str, list[str]], *, default_year: int | None = None
) -> dict[str, object]:
    """Compute a recommendation from parsed query-string parameters.

    ``query`` has the shape returned by :func:`urllib.parse.parse_qs`. The
    result is the same dictionary that ``agroclim recommend --json`` prints.

    Raises:
        QueryError: a parameter is missing, malformed or out of range.

    >>> payload = recommend_from_query(
    ...     {"crop": ["wheat"], "precipitation": ["139"], "humidity": ["55"], "year": ["2027"]}
    ... )
    >>> payload["sowing_date"], payload["inside_literature_window"]
    ('2027-05-15', True)
    """
    crop = _param(query, "crop").strip().lower()
    if crop not in CROPS:
        raise QueryError(f"unknown crop {crop!r}; expected one of {', '.join(sorted(CROPS))}")
    year = _int(query, "year", str(default_year or date.today().year))
    samples = _int(query, "samples", "2000")
    if not 20 <= samples <= MAX_SAMPLES:
        raise QueryError(f"samples must be in 20-{MAX_SAMPLES}, got {samples}")
    seed = _int(query, "seed", "42")
    try:
        conditions = FieldConditions(
            precipitation=_float(query, "precipitation"),
            relative_humidity=_float(query, "humidity"),
            nitrogen=_float(query, "nitrogen", "100"),
            soil_ph=_float(query, "ph", "6.9"),
            previous_crop=_param(query, "previous", "fallow"),
        )
        recommendation = recommend_sowing_date(crop, conditions, year, samples=samples, seed=seed)
    except QueryError:
        raise
    except (ValueError, KeyError) as exc:
        # FieldConditions validates its ranges with ValueError, the rotation
        # table rejects an unknown predecessor with KeyError, and date() rejects
        # an impossible year with ValueError: all of them are the client's fault.
        message = exc.args[0] if exc.args else exc
        raise QueryError(str(message)) from exc
    return recommendation.as_dict()


def _crops_payload() -> dict[str, object]:
    return {
        "crops": [
            {
                "key": crop.key,
                "name": crop.name,
                "optimum_doy": crop.optimum_doy,
                "window_doy": list(crop.window),
            }
            for crop in CROPS.values()
        ]
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = f"agroclim/{__version__}"
    sys_version = ""  # do not advertise the Python version in the Server header

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/healthz":
            self._reply(HTTPStatus.OK, {"status": "ok", "version": __version__})
        elif url.path == "/":
            self._reply(
                HTTPStatus.OK,
                {"service": "agroclim", "version": __version__, "endpoints": list(ENDPOINTS)},
            )
        elif url.path == "/crops":
            self._reply(HTTPStatus.OK, _crops_payload())
        elif url.path == "/recommend":
            try:
                payload = recommend_from_query(parse_qs(url.query))
            except QueryError as exc:
                self._reply(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            else:
                self._reply(HTTPStatus.OK, payload)
        else:
            self._reply(HTTPStatus.NOT_FOUND, {"error": f"unknown path {url.path!r}"})

    def _reply(self, status: HTTPStatus, payload: Mapping[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info("%s %s", self.address_string(), format % args)


def make_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    """Create and bind the HTTP server without starting it; ``port=0`` picks a free port."""
    return ThreadingHTTPServer((host, port), _Handler)


def serve(host: str = "127.0.0.1", port: int = 8000) -> int:
    """Serve requests until SIGTERM or SIGINT and return the process exit code.

    Kubernetes stops a pod with SIGTERM, so the signal shuts the server down
    cleanly instead of killing it in the middle of a request.
    """
    server = make_server(host, port)

    def _stop(signum: int, _frame: object) -> None:
        LOGGER.info("received signal %d, shutting down", signum)
        threading.Thread(target=server.shutdown, daemon=True).start()

    previous = {sig: signal.signal(sig, _stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    LOGGER.info("agroclim %s listening on http://%s:%d", __version__, host, server.server_port)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        for sig, handler in previous.items():
            if handler is not None:
                signal.signal(sig, handler)
    LOGGER.info("agroclim stopped")
    return 0
