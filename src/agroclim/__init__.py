"""agroclim - planting-date decision support for rainfed crops in Northern Kazakhstan.

The package turns open weather and soil data into an explainable sowing-date
recommendation for six crops: wheat, barley, pea, lentil, canola and flax.
"""

from __future__ import annotations

__version__ = "0.1.0"

from agroclim.climate import (
    DailyRecord,
    SeasonSummary,
    growing_degree_days,
    load_daily_csv,
    summarise_season,
)
from agroclim.model import CROPS, Crop, FieldConditions, explain_yield, predict_yield
from agroclim.optimizer import Recommendation, recommend_sowing_date

__all__ = [
    "CROPS",
    "Crop",
    "DailyRecord",
    "FieldConditions",
    "Recommendation",
    "SeasonSummary",
    "__version__",
    "explain_yield",
    "growing_degree_days",
    "load_daily_csv",
    "predict_yield",
    "recommend_sowing_date",
    "summarise_season",
]
