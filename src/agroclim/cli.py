"""Command-line interface of agroclim."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date, datetime

from agroclim import __version__
from agroclim.climate import load_daily_csv, summarise_season, write_daily_csv
from agroclim.model import CROPS, FieldConditions, explain_yield
from agroclim.nasa_power import PowerAPIError, fetch_daily
from agroclim.optimizer import recommend_sowing_date

__all__ = ["build_parser", "main"]


def _iso_date(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {raw!r}") from exc


def _add_condition_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--precipitation", type=float, required=True, help="growing-season precipitation, mm"
    )
    parser.add_argument("--humidity", type=float, required=True, help="mean relative humidity, %%")
    parser.add_argument(
        "--nitrogen",
        type=float,
        default=100.0,
        help="plant-available soil nitrogen, ppm (default: 100)",
    )
    parser.add_argument(
        "--ph", type=float, default=6.9, dest="soil_ph", help="soil pH (default: 6.9)"
    )
    parser.add_argument(
        "--previous",
        default="fallow",
        dest="previous_crop",
        help="preceding crop: fallow or a crop key (default: fallow)",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser of the ``agroclim`` command."""
    parser = argparse.ArgumentParser(
        prog="agroclim",
        description="Planting-date decision support for rainfed crops in Northern Kazakhstan.",
    )
    parser.add_argument("--version", action="version", version=f"agroclim {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    features = sub.add_parser("features", help="summarise a season from a daily CSV file")
    features.add_argument("csv", help="CSV with date,t_mean,precipitation,relative_humidity")
    features.add_argument(
        "--base-temperature",
        type=float,
        default=0.0,
        help="base temperature for growing degree-days (default: 0)",
    )
    features.add_argument("--json", action="store_true", help="print JSON instead of a table")

    recommend = sub.add_parser("recommend", help="recommend a sowing date for one crop")
    recommend.add_argument("--crop", choices=sorted(CROPS), required=True)
    recommend.add_argument("--year", type=int, default=date.today().year)
    _add_condition_arguments(recommend)
    recommend.add_argument("--seed", type=int, default=42, help="seed of the interval sampler")
    recommend.add_argument("--samples", type=int, default=2000)
    recommend.add_argument(
        "--explain", action="store_true", help="show every factor of the formula"
    )
    recommend.add_argument("--plot", metavar="PATH", help="save the response curve as PNG")
    recommend.add_argument("--json", action="store_true", help="print JSON instead of a report")

    fetch = sub.add_parser("fetch", help="download daily weather from NASA POWER")
    fetch.add_argument("--lat", type=float, required=True)
    fetch.add_argument("--lon", type=float, required=True)
    fetch.add_argument("--start", type=_iso_date, required=True)
    fetch.add_argument("--end", type=_iso_date, required=True)
    fetch.add_argument("--out", required=True, help="CSV file to write")
    return parser


def _run_features(args: argparse.Namespace) -> int:
    records = load_daily_csv(args.csv)
    summary = summarise_season(records, base_temperature=args.base_temperature)
    if args.json:
        print(json.dumps(summary.as_dict(), indent=2))
    else:
        print(f"days in season          {summary.days}")
        print(f"mean temperature        {summary.t_mean:.2f} C")
        print(f"total precipitation     {summary.precipitation_total:.1f} mm")
        print(f"mean relative humidity  {summary.relative_humidity_mean:.1f} %")
        print(f"growing degree-days     {summary.gdd:.0f}")
    return 0


def _run_recommend(args: argparse.Namespace) -> int:
    conditions = FieldConditions(
        precipitation=args.precipitation,
        relative_humidity=args.humidity,
        nitrogen=args.nitrogen,
        soil_ph=args.soil_ph,
        previous_crop=args.previous_crop,
    )
    recommendation = recommend_sowing_date(
        args.crop, conditions, args.year, samples=args.samples, seed=args.seed
    )
    if args.json:
        payload = recommendation.as_dict()
        if args.explain:
            payload["factors"] = {
                key: round(value, 4)
                for key, value in explain_yield(
                    args.crop, conditions, recommendation.day_of_year
                ).items()
            }
        print(json.dumps(payload, indent=2))
    else:
        print(recommendation.summary())
        if args.explain:
            print("\n  factors of the formula")
            for key, value in explain_yield(
                args.crop, conditions, recommendation.day_of_year
            ).items():
                print(f"    {key:<18} {value:.3f}")
    if args.plot:
        from agroclim.plotting import save_response_curve

        path = save_response_curve(recommendation, args.plot)
        print(f"\nresponse curve written to {path}")
    return 0


def _run_fetch(args: argparse.Namespace) -> int:
    records = fetch_daily(args.lat, args.lon, args.start, args.end)
    path = write_daily_csv(records, args.out)
    print(f"{len(records)} daily records written to {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the ``agroclim`` command. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "features": _run_features,
        "recommend": _run_recommend,
        "fetch": _run_fetch,
    }
    try:
        return handlers[args.command](args)
    except (ValueError, KeyError, OSError, PowerAPIError) as exc:
        print(f"agroclim: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
