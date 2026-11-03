# Container, pipeline and deployment

This page describes how `agroclim` is built, tested, packaged and deployed
automatically. Everything here is code in this repository: the image
(`Dockerfile`), the pipeline (`Jenkinsfile`), the Jenkins server itself
(`ci/jenkins/`) and the Kubernetes manifests (`deploy/`).

```
 git push ──► GitHub ──(scanned every minute)──► Jenkins (local, configured as code)
                                                    │
   every branch:  lint ─┬─ types ─ unit tests ─ package ─ image build ─ image smoke test
                        └─ (parallel)
   main only:     push to Docker Hub (amd64 + arm64) ─ deploy to Kubernetes ─ verify
                                                    │                   (rollback on failure)
                                   docker.io/mukan2077/agroclim-kz:sha-<commit>
                                                    │
                       minikube ─ namespace agroclim ─ Deployment agroclim-api (2 pods)
                                                     └ Service agroclim-api:80
```

GitHub Actions (`.github/workflows/ci.yml`) keeps running the public checks on
every push and pull request — lint, types, tests on three Python versions and
Windows, the package build — and also builds the image and runs the same smoke
test as Jenkins. Jenkins is the self-hosted pipeline that additionally pushes
and deploys.

## The container image

| Stage | Purpose |
|---|---|
| `build` | builds the wheel and installs it into `/opt/agroclim` (pure Python) |
| `ci` | the pinned toolchain from `requirements-dev.txt`; Jenkins runs lint, types and tests in it |
| `runtime` | the image that is pushed and deployed (default target) |

- The base image is pinned by digest (`python:3.12-slim-trixie@sha256:…`), and
  the development tools are pinned by exact version, so a rebuild months later
  gets the same environment. Dependabot proposes updates of both.
- The runtime image runs as UID 10001, not root, has a `HEALTHCHECK` on
  `/healthz` and carries OCI labels with the version and the Git commit.
- The runtime stage has no `RUN` instruction: nothing executes on the target
  platform, so the `linux/amd64` and `linux/arm64` variants build on an
  Apple Silicon laptop without emulation.

```bash
docker build -t agroclim-kz .
docker run --rm agroclim-kz recommend --crop wheat --precipitation 139 --humidity 55 --year 2027
docker run --rm -p 8000:8000 agroclim-kz            # JSON API
curl "http://localhost:8000/recommend?crop=wheat&precipitation=139&humidity=55&year=2027"
ci/scripts/smoke-test-image.sh agroclim-kz           # the checks the pipeline runs
```

## The HTTP API

`agroclim serve` exposes the recommender for the platform back end:

| Endpoint | Returns |
|---|---|
| `GET /healthz` | `{"status": "ok", "version": "…"}` — liveness and readiness probe |
| `GET /crops` | the six crops with their published sowing windows |
| `GET /recommend?crop=…&precipitation=…&humidity=…` | the same JSON as `agroclim recommend --json`; optional `year`, `nitrogen`, `ph`, `previous`, `seed`, `samples` |

Invalid input gets `400` with a readable message. The server is built on the
standard library to keep the package free of dependencies; it runs inside the
cluster behind a Service and is not meant to face the internet directly.

## Jenkins

Jenkins runs locally in Docker and is configured as code; nothing is clicked
together in the UI.

| File | What it defines |
|---|---|
| `ci/jenkins/Dockerfile` | Jenkins LTS 2.580.2 + plugins + Docker CLI + kubectl 1.37 |
| `ci/jenkins/plugins.txt` | Pipeline, Git, Docker Pipeline, JCasC, Job DSL, JUnit, Coverage, Stage View, Graph View |
| `ci/jenkins/casc.yaml` | admin user, no anonymous access, the two credentials, the multibranch job |
| `ci/jenkins/docker-compose.yml` | the controller and a `docker:dind` sidecar (the official Jenkins set-up) |
| `ci/jenkins/bootstrap.sh` | one-time set-up of the cluster account, local secrets and the containers |

```bash
brew install minikube && minikube start --driver=docker
ci/jenkins/bootstrap.sh                 # Jenkins on http://localhost:8080, login in ci/jenkins/.env
ci/jenkins/set-dockerhub-token.sh       # paste a Docker Hub access token (Read & Write)
```

Design decisions:

- **Builds do not see the host's Docker.** The controller talks to a
  `docker:dind` sidecar over TLS instead of mounting `/var/run/docker.sock`, so
  a pipeline cannot stop or read the other containers on the machine.
- **No secret is in Git.** The admin password, the Docker Hub token and the
  kubeconfig are local files (`ci/jenkins/.env`, `ci/jenkins/secrets/`, both
  git-ignored), mounted as Docker secrets and resolved by JCasC at start-up.
  The push stage logs in with a throw-away Docker config that is deleted after
  the push.
- **Polling instead of webhooks.** Jenkins runs behind NAT, so GitHub cannot
  deliver webhooks to it. The multibranch job scans the repository every
  minute; a new commit on any branch starts a build. On a server with a public
  address a GitHub webhook would replace the scan.
- **Tests run in the pinned toolchain.** The quality-gate stages run inside the
  `ci` stage of the project Dockerfile, so Jenkins, a laptop and a reviewer use
  the same versions of Python, ruff, mypy and pytest.
- **The package builds offline.** The build backend (hatchling) is pinned in
  the CI image and Jenkins runs `python -m build --no-isolation`, so the stage
  needs no package index (it took 100 s on a slow connection before, 2 s now).
- **buildx talks to the sidecar through a Docker context.** buildx cannot create
  a builder from `DOCKER_HOST` and TLS variables, so `ci/scripts/push-image.sh`
  registers the `docker:dind` daemon as a context in a throw-away config first.

## Pipeline stages

| Stage | Branches | Fails the build when |
|---|---|---|
| Prepare | all | Git metadata or the Docker daemon is unavailable |
| Lint (ruff) ∥ Types (mypy --strict) | all | a lint rule, the formatting or a type check fails |
| Unit tests (pytest) | all | a test fails or coverage drops below 85 %; JUnit and coverage reports are published |
| Package (wheel + sdist) | all | the build or `twine check --strict` fails; the files are archived |
| Build image | all | the Dockerfile does not build |
| Smoke test image | all | the CLI, the non-root user, the health check or the API misbehaves |
| Push to Docker Hub | `main` | the multi-arch build or the push fails |
| Deploy to Kubernetes | `main` | the rollout does not complete in 3 minutes → rollback |
| Verify deployment | `main` | the live service is unhealthy, has the wrong version or a wrong answer → rollback |

Image tags: every `main` build pushes `sha-<12-char commit>` (immutable) and
`latest`; a commit tagged `vX.Y.Z` also gets `X.Y.Z`. The images are public at
[hub.docker.com/r/mukan2077/agroclim-kz](https://hub.docker.com/r/mukan2077/agroclim-kz/tags). The cluster always runs
an immutable `sha-` tag, so `kubectl rollout history` maps every revision to a
commit and a Jenkins build.

## Kubernetes

- `deploy/cluster/jenkins-deployer.yaml` is applied once by a cluster
  administrator. It creates the `agroclim` namespace with the **restricted** Pod
  Security Standard and a service account that may only manage Deployments,
  Services and pods in that namespace: it cannot read secrets or touch anything
  else in the cluster.
- `deploy/k8s/` is what Jenkins applies: a Deployment with two replicas,
  readiness and liveness probes on `/healthz`, CPU and memory limits, a
  read-only root filesystem, no privilege escalation and all capabilities
  dropped, plus a ClusterIP Service.
- Updates are rolling with `maxUnavailable: 0`, so the service stays up while
  a new version starts.

```bash
kubectl -n agroclim get deploy,pods,svc
kubectl -n agroclim rollout history deployment/agroclim-api
kubectl -n agroclim port-forward svc/agroclim-api 8000:80
curl "http://localhost:8000/recommend?crop=barley&precipitation=120&humidity=50"
```

## Known limitations

- The image tested by the smoke stage and the multi-arch image pushed from
  `main` are two builds of the same commit and the same pinned inputs, not one
  artifact. The deployed image is checked again in the cluster before the build
  passes. Building once with buildx, testing the pushed digest and then
  promoting it would close this gap.
- Jenkins and the cluster run on one laptop: this is a reproducible test bench,
  not a production installation.
- The recommended sowing date does not react to the weather inputs (only the
  yield and the interval do; see [methodology](methodology.md)). The pipeline
  guards the code against regressions; it cannot make the agronomic model
  better.
