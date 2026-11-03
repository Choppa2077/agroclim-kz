# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned
- Calibration for the Kostanay, Pavlodar and North Kazakhstan oblasts (#2).
- Seasonal weather forecasts instead of climatological averages (#1).
- Publication of the package on PyPI (#3).

## [0.2.1] - 2026-11-03

### Fixed
- Jenkins: the multi-arch push reaches the `docker:dind` daemon through a Docker context.
  `buildx` cannot create a builder from `DOCKER_HOST` and TLS variables, which stopped
  the first `main` build of 0.2.0 before the image was pushed.

### Changed
- Jenkins builds the wheel and the sdist without network access: the build backend
  (`hatchling`) is pinned in the CI image.

## [0.2.0] - 2026-11-03

### Added
- `agroclim serve` and `agroclim.service`: a JSON HTTP API (`/healthz`, `/crops`,
  `/recommend`) built on the standard library, so the back end of the platform can call
  the recommender over the network. Responses are identical to `agroclim recommend --json`.
- `Dockerfile`: multi-stage build — wheel, pinned CI toolchain, non-root runtime image
  with a health check; the base image is pinned by digest.
- `requirements-dev.txt`: the pinned development toolchain used by the CI image.
- `Jenkinsfile` and `ci/jenkins/`: a Jenkins server configured as code (JCasC and Job DSL)
  with a multibranch pipeline — lint, types, tests, package, image build, smoke test,
  push to Docker Hub and deployment to Kubernetes with an automatic rollback.
- `deploy/k8s/`: Kubernetes manifests (Deployment with probes, resource limits and a
  restricted security context; Service) and a least-privilege account for the deployer.

### Changed
- GitHub Actions also builds the container image and runs the same smoke test as Jenkins.
- Dependabot also proposes updates of the Docker base images.

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

[Unreleased]: https://github.com/Choppa2077/agroclim-kz/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/Choppa2077/agroclim-kz/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Choppa2077/agroclim-kz/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Choppa2077/agroclim-kz/releases/tag/v0.1.0
