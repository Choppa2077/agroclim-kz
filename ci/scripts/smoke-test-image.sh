#!/usr/bin/env bash
# Smoke-test a freshly built agroclim image before anyone else gets it:
#   1. the command line answers;
#   2. the container does not run as root;
#   3. the CLI gives the published recommendation offline;
#   4. the HTTP API becomes healthy (Docker HEALTHCHECK) and returns exactly the
#      same recommendation as the CLI.
#
# Usage: ci/scripts/smoke-test-image.sh IMAGE
# Needs only the docker CLI, so Jenkins and GitHub Actions run it the same way.
set -euo pipefail

image="${1:?usage: $0 IMAGE}"
name="agroclim-smoke-$$-${RANDOM}"
query='crop=wheat&previous=pea&precipitation=139&humidity=55&year=2027'

cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT

step() { printf '\n==> %s\n' "$*"; }

step "the command line answers"
docker run --rm "$image" --version

step "the container does not run as root"
uid="$(docker run --rm --entrypoint id "$image" -u)"
echo "uid=${uid}"
if [ "$uid" = "0" ]; then
  echo "the image runs as root" >&2
  exit 1
fi

step "the CLI recommends the published sowing date offline"
cli_json="$(docker run --rm "$image" recommend --crop wheat --previous pea \
  --precipitation 139 --humidity 55 --year 2027 --json)"
echo "$cli_json"
grep -q '"sowing_date": "2027-05-15"' <<<"$cli_json"

step "the HTTP API becomes healthy"
docker run -d --name "$name" --health-interval=2s --health-start-period=2s "$image" >/dev/null
status="starting"
for _ in $(seq 1 30); do
  status="$(docker inspect --format '{{.State.Health.Status}}' "$name")"
  [ "$status" = "healthy" ] && break
  sleep 1
done
echo "health status: ${status}"
if [ "$status" != "healthy" ]; then
  docker logs "$name" >&2
  exit 1
fi

step "the HTTP API returns the same recommendation as the CLI"
api_json="$(docker exec "$name" python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/recommend?${query}', timeout=5).read().decode())")"
echo "$api_json"
docker run --rm --entrypoint python "$image" -c \
  'import json, sys; assert json.loads(sys.argv[1]) == json.loads(sys.argv[2]), "CLI and API differ"' \
  "$cli_json" "$api_json"

step "smoke test passed for ${image}"
