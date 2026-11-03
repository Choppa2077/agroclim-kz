#!/usr/bin/env bash
# Store a Docker Hub access token for Jenkins and restart Jenkins so that
# Configuration as Code loads it into the "dockerhub" credential.
#
# Create the token at https://app.docker.com/settings/personal-access-tokens
# (access: Read & Write). The token is read without echo and is written to
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
printf '%s' "$token" >secrets/dockerhub_token
unset token
echo "saved to ci/jenkins/secrets/dockerhub_token"

docker compose up -d --force-recreate jenkins
echo "Jenkins restarts with the new credential in about a minute: http://localhost:8080"
