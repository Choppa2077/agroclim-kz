"""Transparent agronomic yield model for rainfed crops of Northern Kazakhstan.

The model is the multiplicative formula published in Idrissov, Kashkimbayeva
and Kaibassova, *Determining the Optimal Planting Time for Agricultural Crops
in Northern Kazakhstan* (IEEE SIST 2026)::

    yield = base × (1 + rotation) × precipitation × humidity × nitrogen × pH × sowing-date

Every factor is a small, documented function of one input, so a recommendation
can always be explained to an agronomist - which a black-box regressor cannot
do. Thresholds are calibrated to the Shortandy district, whose median
growing-season precipitation is 139 mm.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

__all__ = [
    "CROPS",
    "YIELD_LIMITS",
    "Crop",
    "FieldConditions",
    "explain_yield",
    "humidity_modifier",
    "nitrogen_modifier",
    "ph_modifier",
    "precipitation_modifier",
    "predict_yield",
    "rotation_modifier",
    "sowing_date_modifier",
]

#: Physically plausible yield range for the region, in t/ha.
YIELD_LIMITS: tuple[float, float] = (0.05, 2.2)

#: Median growing-season precipitation of the Shortandy district, in mm.
REFERENCE_PRECIPITATION = 139.0


@dataclass(frozen=True, slots=True)
class Crop:
    """A crop with its base yield and agronomic sowing window."""

    key: str
    name: str
    base_yield: float
    optimum_doy: int
    window: tuple[int, int]
    group: str

    def window_dates(self) -> str:
        """Human-readable sowing window, e.g. ``"DOY 130-150"``."""
        return f"DOY {self.window[0]}-{self.window[1]}"


CROPS: Mapping[str, Crop] = {
    "wheat": Crop("wheat", "Spring wheat", 1.020, 135, (130, 150), "cereal"),
    "barley": Crop("barley", "Barley", 0.935, 120, (115, 135), "cereal"),
    "pea": Crop("pea", "Field pea", 0.765, 120, (110, 130), "legume"),
    "lentil": Crop("lentil", "Lentil", 0.680, 135, (120, 150), "legume"),
    "canola": Crop("canola", "Canola", 0.595, 128, (128, 148), "oilseed"),
    "flax": Crop("flax", "Flax", 0.510, 135, (135, 155), "oilseed"),
}

#: Yield effect of the preceding crop, relative to a neutral predecessor.
ROTATION_EFFECT: Mapping[str, float] = {
    "fallow": 0.35,
    "legume": 0.11,
    "oilseed": 0.00,
    "cereal": -0.05,
    "same": -0.15,
}


@dataclass(frozen=True, slots=True)
class FieldConditions:
    """Season and soil conditions of one field."""

    precipitation: float
    relative_humidity: float
    nitrogen: float = 100.0
    soil_ph: float = 6.9
    previous_crop: str = "fallow"

    def __post_init__(self) -> None:
        if self.precipitation < 0:
            raise ValueError("precipitation cannot be negative")
        if not 0 <= self.relative_humidity <= 100:
            raise ValueError("relative humidity must be a percentage in 0-100")
        if self.nitrogen < 0:
            raise ValueError("nitrogen cannot be negative")
        if not 3.0 <= self.soil_ph <= 10.0:
            raise ValueError("soil pH must be in 3.0-10.0")


def _interpolate(x: float, points: Sequence[tuple[float, float]]) -> float:
    """Piecewise-linear interpolation over sorted ``(x, y)`` points, clamped."""
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in pairwise(points):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    raise AssertionError("unreachable")  # pragma: no cover


def rotation_modifier(crop: Crop, previous_crop: str) -> float:
    """Relative yield effect of the preceding crop.

    Fallow adds 35 % and a legume predecessor 11 %, while repeating the same
    crop costs 15 %; the values follow the rotation literature summarised in
    the source paper.
    """
    previous = previous_crop.strip().lower()
    if previous in {"", "none", "unknown"}:
        return 0.0
    if previous == "fallow":
        return ROTATION_EFFECT["fallow"]
    if previous == crop.key:
        return ROTATION_EFFECT["same"]
    other = CROPS.get(previous)
    if other is None:
        raise KeyError(f"unknown previous crop: {previous_crop!r}")
    return ROTATION_EFFECT[other.group]


def precipitation_modifier(precipitation_mm: float) -> float:
    """Yield factor for growing-season precipitation.

    Calibrated on the district median of 139 mm, which is well below the
    200-300 mm assumed by most published thresholds.
    """
    return _interpolate(
        precipitation_mm,
        [
            (60.0, 0.40),
            (100.0, 0.45),
            (REFERENCE_PRECIPITATION, 1.00),
            (170.0, 1.10),
            (250.0, 1.30),
        ],
    )


def humidity_modifier(relative_humidity_pct: float) -> float:
    """Yield factor for mean relative humidity."""
    return _interpolate(
        relative_humidity_pct,
        [(35.0, 0.80), (45.0, 0.90), (55.0, 1.00), (65.0, 1.15)],
    )


def nitrogen_modifier(nitrogen_ppm: float) -> float:
    """Yield factor for plant-available soil nitrogen."""
    return _interpolate(nitrogen_ppm, [(80.0, 0.80), (120.0, 1.00), (160.0, 1.05)])


def ph_modifier(soil_ph: float) -> float:
    """Yield factor for soil pH; 6.5-7.5 is optimal for these crops."""
    if 6.5 <= soil_ph <= 7.5:
        return 1.0
    distance = 6.5 - soil_ph if soil_ph < 6.5 else soil_ph - 7.5
    return max(0.70, 1.0 - 0.10 * distance)


def sowing_date_modifier(crop: Crop, day_of_year: int) -> float:
    """Yield factor for the sowing date, peaking at the crop optimum.

    The response is deliberately shallow: in the source study the planting
    day-of-year moves yield by about 0.07 t/ha across the whole window, far
    less than rainfall, but it is the variable a farmer actually controls.
    """
    offset = (day_of_year - crop.optimum_doy) / 30.0
    return max(0.60, 1.0 - 0.12 * offset * offset)


def predict_yield(crop: Crop | str, conditions: FieldConditions, day_of_year: int) -> float:
    """Predict the yield of ``crop`` in t/ha for a sowing day of the year."""
    resolved = CROPS[crop] if isinstance(crop, str) else crop
    value = (
        resolved.base_yield
        * (1.0 + rotation_modifier(resolved, conditions.previous_crop))
        * precipitation_modifier(conditions.precipitation)
        * humidity_modifier(conditions.relative_humidity)
        * nitrogen_modifier(conditions.nitrogen)
        * ph_modifier(conditions.soil_ph)
        * sowing_date_modifier(resolved, day_of_year)
    )
    low, high = YIELD_LIMITS
    return min(max(value, low), high)


def explain_yield(
    crop: Crop | str, conditions: FieldConditions, day_of_year: int
) -> dict[str, float]:
    """Return every factor of the formula, for reporting and debugging."""
    resolved = CROPS[crop] if isinstance(crop, str) else crop
    return {
        "base_yield": resolved.base_yield,
        "rotation": 1.0 + rotation_modifier(resolved, conditions.previous_crop),
        "precipitation": precipitation_modifier(conditions.precipitation),
        "humidity": humidity_modifier(conditions.relative_humidity),
        "nitrogen": nitrogen_modifier(conditions.nitrogen),
        "soil_ph": ph_modifier(conditions.soil_ph),
        "sowing_date": sowing_date_modifier(resolved, day_of_year),
        "predicted_yield": predict_yield(resolved, conditions, day_of_year),
    }
