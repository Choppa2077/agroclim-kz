#!/usr/bin/env bash
# Store a Docker Hub access token for Jenkins and reload Configuration as Code,
# so the "dockerhub" credential picks it up without restarting Jenkins (running
# builds are not interrupted).
#
# Create the token at https://app.docker.com/settings/personal-access-tokens
# with "Read & Write" access. It is read without echo and written to
# secrets/dockerhub_token (git-ignored, readable only by you).
set -euo pipefail
cd "$(dirname "$0")"

read -r -s -p "Docker Hub access token for mukan2077: " token
echo
if [ -z "$token" ]; then
  echo "empty token, nothing changed" >&2
  exit 1
fi
umask 077
mkdir -p secrets
# Write in place: the file is bind-mounted into the container as a Docker secret.
printf '%s' "$token" >secrets/dockerhub_token
unset token
echo "saved to ci/jenkins/secrets/dockerhub_token"

set -a
. ./.env
set +a
auth="${JENKINS_ADMIN_ID}:${JENKINS_ADMIN_PASSWORD}"
jar="$(mktemp)"
trap 'rm -f "$jar"' EXIT
crumb="$(curl -fsS -c "$jar" -u "$auth" http://localhost:8080/crumbIssuer/api/json |
  python3 -c 'import json, sys; c = json.load(sys.stdin); print(c["crumbRequestField"] + ":" + c["crumb"])')"
curl -fsS -b "$jar" -u "$auth" -H "$crumb" -X POST \
  http://localhost:8080/configuration-as-code/reload >/dev/null
echo "Jenkins reloaded its configuration; the dockerhub credential now holds the token."
