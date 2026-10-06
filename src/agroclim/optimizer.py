"""Search for the sowing date that maximises predicted yield.

At sowing time the weather of the coming season is unknown, so the optimizer
reports a prediction interval obtained by resampling the two dominant inputs -
growing-season precipitation and relative humidity - around the values given
by the user. The sampler is seeded, so a recommendation is reproducible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from agroclim.model import CROPS, Crop, FieldConditions, predict_yield

__all__ = [
    "Recommendation",
    "candidate_days",
    "day_of_year_to_date",
    "recommend_sowing_date",
]

#: Relative standard deviation of growing-season precipitation (Shortandy, 1991-2025).
PRECIPITATION_CV = 0.25
#: Standard deviation of mean relative humidity, in percentage points.
HUMIDITY_SD = 3.0


def day_of_year_to_date(day_of_year: int, year: int) -> date:
    """Convert a day of the year into a calendar date."""
    if not 1 <= day_of_year <= 366:
        raise ValueError("day_of_year must be in 1-366")
    return date(year, 1, 1) + timedelta(days=day_of_year - 1)


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Result of a sowing-date search."""

    crop: str
    year: int
    day_of_year: int
    sowing_date: date
    expected_yield: float
    interval: tuple[float, float]
    literature_window: tuple[int, int]
    curve: list[tuple[int, float]] = field(default_factory=list)

    @property
    def inside_literature_window(self) -> bool:
        """Whether the recommendation falls inside the published window."""
        low, high = self.literature_window
        return low <= self.day_of_year <= high

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary."""
        return {
            "crop": self.crop,
            "year": self.year,
            "sowing_date": self.sowing_date.isoformat(),
            "day_of_year": self.day_of_year,
            "expected_yield_t_ha": round(self.expected_yield, 3),
            "interval_t_ha": [round(self.interval[0], 3), round(self.interval[1], 3)],
            "literature_window_doy": list(self.literature_window),
            "inside_literature_window": self.inside_literature_window,
        }

    def summary(self) -> str:
        """Return a short human-readable report."""
        low, high = self.interval
        match = "inside" if self.inside_literature_window else "outside"
        return (
            f"{self.crop}: sow on {self.sowing_date:%d %B %Y} (day {self.day_of_year})\n"
            f"  expected yield {self.expected_yield:.2f} t/ha "
            f"(90 % interval {low:.2f}-{high:.2f})\n"
            f"  {match} the published window "
            f"(DOY {self.literature_window[0]}-{self.literature_window[1]})"
        )


def candidate_days(crop: Crop, margin: int = 10, step: int = 1) -> list[int]:
    """Days of the year to evaluate: the published window widened by ``margin``."""
    if step < 1:
        raise ValueError("step must be at least 1 day")
    low, high = crop.window
    return list(range(low - margin, high + margin + 1, step))


def _interval(
    crop: Crop,
    conditions: FieldConditions,
    day_of_year: int,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(samples):
        precipitation = max(
            20.0, rng.gauss(conditions.precipitation, conditions.precipitation * PRECIPITATION_CV)
        )
        humidity = min(100.0, max(0.0, rng.gauss(conditions.relative_humidity, HUMIDITY_SD)))
        sampled = FieldConditions(
            precipitation=precipitation,
            relative_humidity=humidity,
            nitrogen=conditions.nitrogen,
            soil_ph=conditions.soil_ph,
            previous_crop=conditions.previous_crop,
        )
        draws.append(predict_yield(crop, sampled, day_of_year))
    draws.sort()
    low = draws[int(0.05 * (samples - 1))]
    high = draws[int(0.95 * (samples - 1))]
    return low, high


def recommend_sowing_date(
    crop: Crop | str,
    conditions: FieldConditions,
    year: int,
    *,
    margin: int = 10,
    step: int = 1,
    samples: int = 2000,
    seed: int = 42,
) -> Recommendation:
    """Return the sowing date with the highest predicted yield.

    Args:
        crop: crop key (``"wheat"``) or a :class:`~agroclim.model.Crop`.
        conditions: season and soil conditions of the field.
        year: calendar year the recommendation is made for.
        margin: days added on both sides of the published window.
        step: spacing of the candidate dates, in days.
        samples: Monte-Carlo draws used for the prediction interval.
        seed: seed of the sampler, so the result is reproducible.
    """
    resolved = CROPS[crop] if isinstance(crop, str) else crop
    if samples < 20:
        raise ValueError("samples must be at least 20 for a 90 % interval")
    curve = [
        (doy, predict_yield(resolved, conditions, doy))
        for doy in candidate_days(resolved, margin=margin, step=step)
    ]
    best_doy, best_yield = max(curve, key=lambda item: (item[1], -item[0]))
    return Recommendation(
        crop=resolved.key,
        year=year,
        day_of_year=best_doy,
        sowing_date=day_of_year_to_date(best_doy, year),
        expected_yield=best_yield,
        interval=_interval(resolved, conditions, best_doy, samples, seed),
        literature_window=resolved.window,
        curve=curve,
    )
