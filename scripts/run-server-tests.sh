#!/bin/sh
# Runs the server suite in a throwaway container from the built API image.
# Nothing touches the running containers, database or uploads volume.
# Build first if the image is stale: docker compose build api
set -e
cd "$(dirname "$0")/.."
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$PWD/server:/app" \
  -v "$PWD/android/app/src/main/assets/katex:/app/katex:ro" \
  -w /app -e PYTHONDONTWRITEBYTECODE=1 studylarper-api sh -c \
  'pip install -q --target /tmp/pt pytest httpx >/dev/null 2>&1; PYTHONPATH=/tmp/pt python -m pytest tests -q -p no:cacheprovider "$@"' sh "$@"
