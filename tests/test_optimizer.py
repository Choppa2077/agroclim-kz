"""Tests for the sowing-date optimizer."""

from __future__ import annotations

from datetime import date

import pytest

from agroclim.model import CROPS, FieldConditions
from agroclim.optimizer import (
    candidate_days,
    day_of_year_to_date,
    recommend_sowing_date,
)

AVERAGE = FieldConditions(precipitation=139.0, relative_humidity=55.0, previous_crop="pea")


def test_day_of_year_to_date_round_trip() -> None:
    assert day_of_year_to_date(135, 2027) == date(2027, 5, 15)
    assert day_of_year_to_date(1, 2027) == date(2027, 1, 1)


@pytest.mark.parametrize("value", [0, 367])
def test_day_of_year_to_date_rejects_out_of_range(value: int) -> None:
    with pytest.raises(ValueError, match="day_of_year"):
        day_of_year_to_date(value, 2027)


def test_candidate_days_widen_the_published_window() -> None:
    days = candidate_days(CROPS["wheat"], margin=10)
    assert days[0] == 120 and days[-1] == 160


def test_candidate_days_respect_the_step() -> None:
    assert candidate_days(CROPS["wheat"], margin=10, step=5)[:3] == [120, 125, 130]


def test_candidate_days_reject_a_zero_step() -> None:
    with pytest.raises(ValueError, match="step"):
        candidate_days(CROPS["wheat"], step=0)


def test_wheat_recommendation_matches_the_published_window() -> None:
    recommendation = recommend_sowing_date("wheat", AVERAGE, 2027, samples=200)
    assert recommendation.day_of_year == CROPS["wheat"].optimum_doy
    assert recommendation.sowing_date == date(2027, 5, 15)
    assert recommendation.inside_literature_window


@pytest.mark.parametrize("crop", sorted(CROPS))
def test_every_crop_gets_a_recommendation_in_its_search_range(crop: str) -> None:
    recommendation = recommend_sowing_date(crop, AVERAGE, 2027, samples=100)
    low, high = CROPS[crop].window
    assert low - 10 <= recommendation.day_of_year <= high + 10
    assert recommendation.expected_yield > 0.0


def test_interval_brackets_the_point_estimate() -> None:
    recommendation = recommend_sowing_date("wheat", AVERAGE, 2027, samples=500)
    low, high = recommendation.interval
    assert low < recommendation.expected_yield < high


def test_recommendation_is_reproducible_with_a_seed() -> None:
    first = recommend_sowing_date("barley", AVERAGE, 2027, samples=300, seed=7)
    second = recommend_sowing_date("barley", AVERAGE, 2027, samples=300, seed=7)
    assert first.interval == second.interval


def test_different_seeds_change_only_the_interval() -> None:
    first = recommend_sowing_date("barley", AVERAGE, 2027, samples=300, seed=1)
    second = recommend_sowing_date("barley", AVERAGE, 2027, samples=300, seed=2)
    assert first.day_of_year == second.day_of_year
    assert first.interval != second.interval


def test_a_dry_season_lowers_the_expected_yield() -> None:
    dry = FieldConditions(precipitation=90.0, relative_humidity=42.0, previous_crop="pea")
    wet = FieldConditions(precipitation=200.0, relative_humidity=60.0, previous_crop="pea")
    assert (
        recommend_sowing_date("wheat", dry, 2027, samples=100).expected_yield
        < recommend_sowing_date("wheat", wet, 2027, samples=100).expected_yield
    )


def test_too_few_samples_are_rejected() -> None:
    with pytest.raises(ValueError, match="samples"):
        recommend_sowing_date("wheat", AVERAGE, 2027, samples=5)


def test_as_dict_is_json_friendly() -> None:
    payload = recommend_sowing_date("wheat", AVERAGE, 2027, samples=100).as_dict()
    assert payload["crop"] == "wheat"
    assert payload["sowing_date"] == "2027-05-15"
    assert isinstance(payload["interval_t_ha"], list)


def test_summary_mentions_the_window() -> None:
    text = recommend_sowing_date("wheat", AVERAGE, 2027, samples=100).summary()
    assert "inside the published window" in text
