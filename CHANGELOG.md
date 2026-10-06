# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned
- Calibration for the Kostanay, Pavlodar and North Kazakhstan oblasts (#2).
- Seasonal weather forecasts instead of climatological averages (#1).
- Publication of the package on PyPI (#3).

## [0.1.0] - 2026-10-06

### Added
- `agroclim.climate`: growing-season aggregation, growing degree-days, CSV import and export.
- `agroclim.model`: multiplicative yield model with documented agronomic modifiers
  for rotation, precipitation, humidity, nitrogen, soil pH and sowing date.
- `agroclim.optimizer`: sowing-date search with a seeded Monte-Carlo prediction interval.
- `agroclim.nasa_power`: client for the NASA POWER daily point API with an injectable opener.
- `agroclim.plotting`: optional yield-response curve (extra `plot`).
- `agroclim` command line interface with the `features`, `recommend` and `fetch` subcommands.
- Continuous integration: ruff, mypy, pytest on Python 3.10-3.12, coverage gate and package build.
- Continuous delivery: tagged releases publish the built artifacts to GitHub Releases.

[Unreleased]: https://github.com/Choppa2077/agroclim-kz/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Choppa2077/agroclim-kz/releases/tag/v0.1.0
