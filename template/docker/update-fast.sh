#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

if [ -d .git ] && git rev-parse --verify HEAD >/dev/null 2>&1; then
    git pull origin "$(git rev-parse --abbrev-ref HEAD)" 2>/dev/null || true
fi

docker compose --env-file .env exec web python manage.py design_studio_update --all-kits
docker compose --env-file .env exec web python manage.py migrate --noinput
docker compose --env-file .env exec web python manage.py collectstatic --clear --noinput
docker compose --env-file .env restart web
