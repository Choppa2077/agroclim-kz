"""Tests for growing-season aggregation."""

from __future__ import annotations

from datetime import date

import pytest

from agroclim.climate import (
    DailyRecord,
    growing_degree_days,
    load_daily_csv,
    season_records,
    summarise_season,
    write_daily_csv,
)


def make_record(day: date, t: float = 18.0, p: float = 1.0, rh: float = 55.0) -> DailyRecord:
    return DailyRecord(day=day, t_mean=t, precipitation=p, relative_humidity=rh)


def test_growing_degree_days_ignores_cold_days() -> None:
    assert growing_degree_days([10.0, -2.0, 5.0], base=5.0) == pytest.approx(5.0)


def test_growing_degree_days_base_zero() -> None:
    assert growing_degree_days([10.0, 0.0, 5.0]) == pytest.approx(15.0)


def test_season_records_keeps_only_the_season() -> None:
    records = [
        make_record(date(2024, 4, 30)),
        make_record(date(2024, 5, 1)),
        make_record(date(2024, 8, 31)),
        make_record(date(2024, 9, 1)),
    ]
    kept = season_records(records)
    assert [r.day for r in kept] == [date(2024, 5, 1), date(2024, 8, 31)]


def test_season_records_drops_missing_values() -> None:
    records = [
        make_record(date(2024, 6, 1)),
        make_record(date(2024, 6, 2), t=-999.0),
        make_record(date(2024, 6, 3), p=-999.0),
    ]
    assert [r.day for r in season_records(records)] == [date(2024, 6, 1)]


def test_summarise_season_aggregates_each_predictor() -> None:
    records = [
        make_record(date(2024, 5, 1), t=10.0, p=2.0, rh=50.0),
        make_record(date(2024, 5, 2), t=20.0, p=3.0, rh=60.0),
    ]
    summary = summarise_season(records)
    assert summary.days == 2
    assert summary.t_mean == pytest.approx(15.0)
    assert summary.precipitation_total == pytest.approx(5.0)
    assert summary.relative_humidity_mean == pytest.approx(55.0)
    assert summary.gdd == pytest.approx(30.0)


def test_summarise_season_without_records_raises() -> None:
    with pytest.raises(ValueError, match="no complete daily records"):
        summarise_season([make_record(date(2024, 1, 15))])


def test_summary_as_dict_is_rounded() -> None:
    summary = summarise_season([make_record(date(2024, 6, 1), t=18.456, p=1.234, rh=54.56)])
    assert summary.as_dict()["t_mean"] == 18.46
    assert summary.as_dict()["precipitation_total"] == 1.2


def test_csv_round_trip(tmp_path) -> None:
    records = [
        make_record(date(2024, 5, 1), t=12.5, p=0.0, rh=48.2),
        make_record(date(2024, 5, 2), t=14.0, p=3.4, rh=52.0),
    ]
    path = write_daily_csv(records, tmp_path / "weather.csv")
    loaded = load_daily_csv(path)
    assert [r.day for r in loaded] == [r.day for r in records]
    assert loaded[1].precipitation == pytest.approx(3.4)


def test_load_daily_csv_reports_missing_columns(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("date,t_mean\n2024-05-01,12.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_daily_csv(path)


@pytest.mark.parametrize("stamp", ["2024-05-01", "20240501", "01.05.2024"])
def test_load_daily_csv_accepts_several_date_formats(tmp_path, stamp: str) -> None:
    path = tmp_path / "weather.csv"
    path.write_text(
        f"date,t_mean,precipitation,relative_humidity\n{stamp},12.0,1.0,50.0\n",
        encoding="utf-8",
    )
    assert load_daily_csv(path)[0].day == date(2024, 5, 1)


def test_load_daily_csv_rejects_unknown_date_format(tmp_path) -> None:
    path = tmp_path / "weather.csv"
    path.write_text(
        "date,t_mean,precipitation,relative_humidity\nMay 1 2024,12.0,1.0,50.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cannot parse line 2"):
        load_daily_csv(path)
