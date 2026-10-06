"""Growing-season aggregation of daily agro-meteorological records.

The module turns a series of daily observations (temperature, precipitation,
relative humidity) into the four season-level predictors used by the yield
model: mean temperature, total precipitation, mean relative humidity and
accumulated growing degree-days.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import fmean

#: Fill value used by the NASA POWER API for missing observations.
MISSING = -999.0

#: Default growing season for Northern Kazakhstan: 1 May – 31 August.
DEFAULT_SEASON: tuple[tuple[int, int], tuple[int, int]] = ((5, 1), (8, 31))

__all__ = [
    "DEFAULT_SEASON",
    "MISSING",
    "DailyRecord",
    "SeasonSummary",
    "growing_degree_days",
    "load_daily_csv",
    "season_records",
    "summarise_season",
    "write_daily_csv",
]


@dataclass(frozen=True, slots=True)
class DailyRecord:
    """One day of weather for a single point."""

    day: date
    t_mean: float
    precipitation: float
    relative_humidity: float

    def is_complete(self) -> bool:
        """Return ``True`` when no field carries the POWER missing-value flag."""
        return all(
            value > MISSING + 1.0
            for value in (self.t_mean, self.precipitation, self.relative_humidity)
        )


@dataclass(frozen=True, slots=True)
class SeasonSummary:
    """Season-level predictors derived from daily records."""

    days: int
    t_mean: float
    precipitation_total: float
    relative_humidity_mean: float
    gdd: float

    def as_dict(self) -> dict[str, float]:
        """Return the summary as a plain dictionary (JSON friendly)."""
        return {
            "days": float(self.days),
            "t_mean": round(self.t_mean, 2),
            "precipitation_total": round(self.precipitation_total, 1),
            "relative_humidity_mean": round(self.relative_humidity_mean, 1),
            "gdd": round(self.gdd, 1),
        }


def growing_degree_days(temperatures: Iterable[float], base: float = 0.0) -> float:
    """Accumulate growing degree-days above ``base``.

    Days colder than ``base`` contribute zero rather than a negative value,
    which is the standard agronomic convention.

    >>> growing_degree_days([10.0, -2.0, 5.0], base=5.0)
    5.0
    """
    return float(sum(max(t - base, 0.0) for t in temperatures))


def _within_season(day: date, season: tuple[tuple[int, int], tuple[int, int]]) -> bool:
    (start_month, start_day), (end_month, end_day) = season
    return (start_month, start_day) <= (day.month, day.day) <= (end_month, end_day)


def season_records(
    records: Iterable[DailyRecord],
    season: tuple[tuple[int, int], tuple[int, int]] = DEFAULT_SEASON,
) -> list[DailyRecord]:
    """Keep the complete records that fall inside the growing season."""
    return [r for r in records if r.is_complete() and _within_season(r.day, season)]


def summarise_season(
    records: Iterable[DailyRecord],
    season: tuple[tuple[int, int], tuple[int, int]] = DEFAULT_SEASON,
    base_temperature: float = 0.0,
) -> SeasonSummary:
    """Reduce daily records to the predictors used by :mod:`agroclim.model`.

    Raises:
        ValueError: if no complete record falls inside the season.
    """
    selected = season_records(records, season)
    if not selected:
        raise ValueError("no complete daily records inside the growing season")
    return SeasonSummary(
        days=len(selected),
        t_mean=fmean(r.t_mean for r in selected),
        precipitation_total=float(sum(r.precipitation for r in selected)),
        relative_humidity_mean=fmean(r.relative_humidity for r in selected),
        gdd=growing_degree_days((r.t_mean for r in selected), base_temperature),
    )


def _parse_day(raw: str) -> date:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date format: {raw!r}")


def load_daily_csv(path: str | Path) -> list[DailyRecord]:
    """Read daily records from a CSV file.

    The file must have a header with the columns ``date``, ``t_mean``,
    ``precipitation`` and ``relative_humidity``.
    """
    required = {"date", "t_mean", "precipitation", "relative_humidity"}
    out: list[DailyRecord] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"missing columns in {path}: {sorted(missing)}")
        for line, row in enumerate(reader, start=2):
            try:
                out.append(
                    DailyRecord(
                        day=_parse_day(row["date"]),
                        t_mean=float(row["t_mean"]),
                        precipitation=float(row["precipitation"]),
                        relative_humidity=float(row["relative_humidity"]),
                    )
                )
            except (TypeError, ValueError) as exc:  # pragma: no cover - message only
                raise ValueError(f"{path}: cannot parse line {line}: {exc}") from exc
    return out


def write_daily_csv(records: Sequence[DailyRecord], path: str | Path) -> Path:
    """Write daily records to CSV and return the path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "t_mean", "precipitation", "relative_humidity"])
        for record in records:
            writer.writerow(
                [
                    record.day.isoformat(),
                    f"{record.t_mean:.2f}",
                    f"{record.precipitation:.2f}",
                    f"{record.relative_humidity:.1f}",
                ]
            )
    return target
