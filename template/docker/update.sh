#!/bin/bash
# Einheitliches Baukasten FULL-Update (Docker Image Rebuild + persistentes /opt/ds-pkg Sync)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

ENV_ARG=""
[ -f ".env" ] && ENV_ARG="--env-file .env"

echo "🏗️ Starte FULL Update (Docker Rebuild)..."
if [ -d "locale" ]; then
    find locale -name "*.mo" -type f -delete 2>/dev/null || true
fi
if [ -d ".git" ] && git rev-parse --verify HEAD >/dev/null 2>&1; then
    git pull --ff-only origin "$(git rev-parse --abbrev-ref HEAD)"
fi

chmod -R a+rX . 2>/dev/null || true
mkdir -p "$ROOT_DIR/data" "$ROOT_DIR/data/backups"
chmod -R 777 "$ROOT_DIR/data" 2>/dev/null || true

IMG_NAME=$(grep -E '^\s*image:\s*' docker-compose.yml 2>/dev/null | head -n1 | awk '{print $2}' | tr -d '\r"' || echo "")
if [ -n "$IMG_NAME" ]; then
    docker build --pull -t "$IMG_NAME" .
else
    docker compose $ENV_ARG build --pull
fi
docker compose $ENV_ARG up -d

# Sync /opt/ds-pkg so persistent volume never shadows newer image code
"$SCRIPT_DIR/update-fast.sh" --force-kits
