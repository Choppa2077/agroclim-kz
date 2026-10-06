"""End-to-end tests of the command-line interface."""

from __future__ import annotations

import json

import pytest

from agroclim.cli import main

SAMPLE_CSV = """date,t_mean,precipitation,relative_humidity
2024-05-01,12.0,0.0,50.0
2024-05-02,14.0,5.0,60.0
2024-06-01,20.0,2.0,55.0
"""


@pytest.fixture()
def weather_csv(tmp_path):
    path = tmp_path / "weather.csv"
    path.write_text(SAMPLE_CSV, encoding="utf-8")
    return path


def test_features_prints_a_table(weather_csv, capsys) -> None:
    assert main(["features", str(weather_csv)]) == 0
    out = capsys.readouterr().out
    assert "total precipitation" in out
    assert "7.0 mm" in out


def test_features_json_output(weather_csv, capsys) -> None:
    assert main(["features", str(weather_csv), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["days"] == 3.0
    assert payload["precipitation_total"] == 7.0


def test_features_reports_a_missing_file(tmp_path, capsys) -> None:
    assert main(["features", str(tmp_path / "nope.csv")]) == 2
    assert "error" in capsys.readouterr().err


def test_recommend_prints_a_report(capsys) -> None:
    code = main(
        [
            "recommend",
            "--crop",
            "wheat",
            "--precipitation",
            "139",
            "--humidity",
            "55",
            "--previous",
            "pea",
            "--year",
            "2027",
            "--samples",
            "100",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "15 May 2027" in out
    assert "expected yield" in out


def test_recommend_json_with_factors(capsys) -> None:
    code = main(
        [
            "recommend",
            "--crop",
            "barley",
            "--precipitation",
            "139",
            "--humidity",
            "55",
            "--json",
            "--explain",
            "--samples",
            "100",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["crop"] == "barley"
    assert "factors" in payload
    assert payload["factors"]["precipitation"] == pytest.approx(1.0)


def test_recommend_rejects_an_unknown_crop(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["recommend", "--crop", "rice", "--precipitation", "139", "--humidity", "55"])


def test_recommend_validates_conditions(capsys) -> None:
    code = main(["recommend", "--crop", "wheat", "--precipitation", "139", "--humidity", "180"])
    assert code == 2
    assert "relative humidity" in capsys.readouterr().err


def test_recommend_writes_a_plot(tmp_path, capsys) -> None:
    matplotlib = pytest.importorskip("matplotlib")
    assert matplotlib is not None
    target = tmp_path / "curve.png"
    code = main(
        [
            "recommend",
            "--crop",
            "wheat",
            "--precipitation",
            "139",
            "--humidity",
            "55",
            "--samples",
            "50",
            "--plot",
            str(target),
        ]
    )
    assert code == 0
    assert target.exists() and target.stat().st_size > 1000


def test_fetch_writes_a_csv(tmp_path, monkeypatch, capsys) -> None:
    from datetime import date

    from agroclim import cli
    from agroclim.climate import DailyRecord

    def fake_fetch(lat, lon, start, end, **kwargs):
        return [DailyRecord(date(2024, 5, 1), 12.0, 1.0, 50.0)]

    monkeypatch.setattr(cli, "fetch_daily", fake_fetch)
    target = tmp_path / "out.csv"
    code = main(
        [
            "fetch",
            "--lat",
            "51.58",
            "--lon",
            "70.84",
            "--start",
            "2024-05-01",
            "--end",
            "2024-05-01",
            "--out",
            str(target),
        ]
    )
    assert code == 0
    assert "1 daily records" in capsys.readouterr().out
    assert target.read_text(encoding="utf-8").splitlines()[0].startswith("date,")


def test_fetch_rejects_a_bad_date() -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "fetch",
                "--lat",
                "51.0",
                "--lon",
                "70.0",
                "--start",
                "01.05.2024",
                "--end",
                "2024-05-02",
                "--out",
                "x.csv",
            ]
        )


def test_version_flag(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "agroclim" in capsys.readouterr().out
