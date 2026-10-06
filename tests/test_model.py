"""Tests for the agronomic yield model."""

from __future__ import annotations

import pytest

from agroclim.model import (
    CROPS,
    REFERENCE_PRECIPITATION,
    YIELD_LIMITS,
    FieldConditions,
    explain_yield,
    humidity_modifier,
    nitrogen_modifier,
    ph_modifier,
    precipitation_modifier,
    predict_yield,
    rotation_modifier,
    sowing_date_modifier,
)

AVERAGE = FieldConditions(precipitation=REFERENCE_PRECIPITATION, relative_humidity=55.0)


def test_six_crops_are_defined() -> None:
    assert sorted(CROPS) == ["barley", "canola", "flax", "lentil", "pea", "wheat"]


@pytest.mark.parametrize(
    ("previous", "expected"),
    [
        ("fallow", 0.35),
        ("pea", 0.11),
        ("lentil", 0.11),
        ("wheat", -0.15),
        ("barley", -0.05),
        ("canola", 0.0),
        ("none", 0.0),
    ],
)
def test_rotation_modifier_matches_the_published_values(previous: str, expected: float) -> None:
    assert rotation_modifier(CROPS["wheat"], previous) == pytest.approx(expected)


def test_rotation_modifier_rejects_unknown_crop() -> None:
    with pytest.raises(KeyError):
        rotation_modifier(CROPS["wheat"], "rice")


def test_precipitation_modifier_is_calibrated_on_the_district_median() -> None:
    assert precipitation_modifier(REFERENCE_PRECIPITATION) == pytest.approx(1.0)


@pytest.mark.parametrize("value", [40.0, 90.0, 120.0, 160.0, 220.0, 400.0])
def test_precipitation_modifier_is_monotone(value: float) -> None:
    assert precipitation_modifier(value) <= precipitation_modifier(value + 10.0) + 1e-12


def test_precipitation_modifier_is_clamped_at_both_ends() -> None:
    assert precipitation_modifier(0.0) == pytest.approx(0.40)
    assert precipitation_modifier(900.0) == pytest.approx(1.30)


def test_humidity_modifier_penalises_dry_seasons() -> None:
    assert humidity_modifier(40.0) < 1.0 < humidity_modifier(60.0)


def test_nitrogen_modifier_saturates() -> None:
    assert nitrogen_modifier(60.0) == pytest.approx(0.80)
    assert nitrogen_modifier(200.0) == pytest.approx(1.05)


def test_ph_modifier_is_flat_in_the_optimum_band() -> None:
    assert ph_modifier(6.5) == 1.0
    assert ph_modifier(7.5) == 1.0
    assert ph_modifier(5.0) < 1.0
    assert ph_modifier(9.0) < 1.0
    assert ph_modifier(3.0) >= 0.70


def test_sowing_date_modifier_peaks_at_the_optimum() -> None:
    wheat = CROPS["wheat"]
    assert sowing_date_modifier(wheat, wheat.optimum_doy) == pytest.approx(1.0)
    assert sowing_date_modifier(wheat, wheat.optimum_doy - 20) < 1.0
    assert sowing_date_modifier(wheat, wheat.optimum_doy + 20) < 1.0


def test_sowing_date_effect_is_shallow() -> None:
    """Across the window the sowing date must move yield far less than rainfall."""
    wheat = CROPS["wheat"]
    low = predict_yield(wheat, AVERAGE, wheat.window[0])
    high = predict_yield(wheat, AVERAGE, wheat.optimum_doy)
    assert 0.0 < high - low < 0.15


def test_predicted_yield_is_in_the_physical_range() -> None:
    wet = FieldConditions(precipitation=400.0, relative_humidity=70.0, nitrogen=200.0)
    dry = FieldConditions(precipitation=10.0, relative_humidity=20.0, nitrogen=10.0)
    for crop in CROPS.values():
        assert YIELD_LIMITS[0] <= predict_yield(crop, wet, crop.optimum_doy) <= YIELD_LIMITS[1]
        assert YIELD_LIMITS[0] <= predict_yield(crop, dry, crop.optimum_doy) <= YIELD_LIMITS[1]


def test_fallow_beats_continuous_wheat() -> None:
    wheat = CROPS["wheat"]
    after_fallow = predict_yield(wheat, FieldConditions(139.0, 55.0, previous_crop="fallow"), 135)
    after_wheat = predict_yield(wheat, FieldConditions(139.0, 55.0, previous_crop="wheat"), 135)
    assert after_fallow / after_wheat == pytest.approx(1.35 / 0.85, rel=1e-6)


def test_explain_yield_lists_every_factor() -> None:
    factors = explain_yield("wheat", AVERAGE, 135)
    assert set(factors) == {
        "base_yield",
        "rotation",
        "precipitation",
        "humidity",
        "nitrogen",
        "soil_ph",
        "sowing_date",
        "predicted_yield",
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"precipitation": -1.0, "relative_humidity": 50.0},
        {"precipitation": 100.0, "relative_humidity": 150.0},
        {"precipitation": 100.0, "relative_humidity": 50.0, "nitrogen": -5.0},
        {"precipitation": 100.0, "relative_humidity": 50.0, "soil_ph": 1.0},
    ],
)
def test_field_conditions_validate_their_inputs(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        FieldConditions(**kwargs)
