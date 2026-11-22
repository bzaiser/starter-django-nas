#!/bin/bash
# Einheitliches Baukasten FAST-Update (persistente Kits in /opt/ds-pkg, kein Rebuild)
# Optionen:
#   --no-kits     Ueberspringt Kit-Sync (nur App-Code + Migrationen + Restart)
#   --deps        Erzwingt Installation externer PyPI-Pakete aus requirements.txt
#   --force-kits  Installiert alle aktiven Baukasten-Kits neu nach /opt/ds-pkg
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

NO_KITS=0
FORCE_DEPS=0
FORCE_KITS=0
for arg in "$@"; do
    case "$arg" in
        --no-kits) NO_KITS=1 ;;
        --deps) FORCE_DEPS=1 ;;
        --force-kits) FORCE_KITS=1 ;;
    esac
done

ENV_ARG=""
[ -f ".env" ] && ENV_ARG="--env-file .env"

echo "⚡ Starte FAST Update..."

# 1. Git Pull (clean untracked .mo files that could block merge)
OLD_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "")
if [ -d "locale" ]; then
    find locale -name "*.mo" -type f -delete 2>/dev/null || true
fi
if [ -d ".git" ] && git rev-parse --verify HEAD >/dev/null 2>&1; then
    echo "⏬ Git pull..."
    git pull --ff-only origin "$(git rev-parse --abbrev-ref HEAD)"
fi

if [ -d ".git" ]; then
    git describe --tags --always > VERSION 2>/dev/null || git rev-parse --short HEAD > VERSION 2>/dev/null || true
    git log -1 --format="%cs" > VERSION_DATE 2>/dev/null || true
fi

# 2. Permissions & persistent directories
echo "🔐 Berechtigungen & Datenverzeichnis..."
chmod -R a+rX . 2>/dev/null || true
[ -f "manage.py" ] && chmod +x manage.py 2>/dev/null || true
mkdir -p "$ROOT_DIR/data" "$ROOT_DIR/data/backups"
chmod -R 777 "$ROOT_DIR/data" 2>/dev/null || true

# Helper: portable container status check (works on Synology & all Docker Compose versions)
get_web_state() {
    local cid
    cid=$(docker compose $ENV_ARG ps -q web 2>/dev/null | head -n1 || true)
    if [ -n "$cid" ]; then
        docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

# 2b. First-run image bootstrap on NAS: reuse existing Baukasten image in 0.1s (NEVER build in update-fast.sh!)
IMG_NAME=$(grep -E '^\s*image:\s*' docker-compose.yml 2>/dev/null | head -n1 | awk '{print $2}' | tr -d '\r"' || echo "")
if [ -n "$IMG_NAME" ] && ! docker image inspect "$IMG_NAME" >/dev/null 2>&1; then
    REUSED=""
    for base_img in \
        "sammlungsverwaltung-image:latest" "sammlungsverwaltung-image" \
        "finanzplan-image:latest" "finanzplan-image" \
        "finanzplan-broker-image:latest" "finanzplan-broker-image" \
        "buckezz_image:latest" "buckezz_image" \
        "gewicht-web:latest" "vitalog-web:latest" \
        "sammlungsverwaltung-web:latest" "finanzplan-web:latest"; do
        if docker image inspect "$base_img" >/dev/null 2>&1; then
            echo "♻️  Nutze vorhandenes Baukasten-Basis-Image ($base_img -> $IMG_NAME) — kein Build!"
            docker tag "$base_img" "$IMG_NAME"
            REUSED="$base_img"
            break
        fi
    done
    # Fallback: auto-detect image from any running Baukasten container on the NAS
    if [ -z "$REUSED" ]; then
        for cand_img in $(docker ps --format '{{.Image}}' 2>/dev/null || true); do
            if docker image inspect "$cand_img" 2>/dev/null | grep -q "/opt/ds-pkg"; then
                echo "♻️  Nutze laufendes Baukasten-Image ($cand_img -> $IMG_NAME) — kein Build!"
                docker tag "$cand_img" "$IMG_NAME"
                REUSED="$cand_img"
                break
            fi
        done
    fi
    if [ -z "$REUSED" ]; then
        echo "❌ Kein vorhandenes Baukasten-Image ($IMG_NAME) auf dem NAS gefunden."
        echo "   Bitte entweder ./docker/load-nas-image.sh nutzen oder einmalig ./docker/update.sh ausführen."
        exit 1
    fi
fi

# 3. Ensure persistent /opt/ds-pkg volume is writable & bootstrapped BEFORE starting web
# (Prevents restart-loops when attaching a fresh empty ds_pkg volume to an older image!)
STATE=$(get_web_state)
if [ "$NO_KITS" = "0" ]; then
    NEED_BOOT=0
    if [ "$STATE" != "running" ]; then
        NEED_BOOT=1
    elif ! docker compose $ENV_ARG exec web test -f /opt/ds-pkg/.kit_commits.json >/dev/null 2>&1; then
        NEED_BOOT=1
    fi
    if [ "$NEED_BOOT" = "1" ]; then
        echo "  → Initial-Bootstrap der Baukasten-Kits nach /opt/ds-pkg..."
        # Fast-path: merge pre-installed kits + .kit_commits.json from existing *_ds_pkg volumes on the NAS
        TARGET_VOL=$(docker volume ls --format '{{.Name}}' 2>/dev/null | grep -E "^$(basename "$ROOT_DIR")_ds_pkg$" | head -n1 || true)
        if [ -z "$TARGET_VOL" ]; then
            docker compose $ENV_ARG up --no-start --no-build 2>/dev/null || true
            TARGET_VOL=$(docker volume ls --format '{{.Name}}' 2>/dev/null | grep -E "^$(basename "$ROOT_DIR")_ds_pkg$" | head -n1 || true)
        fi
        if [ -n "$TARGET_VOL" ] && [ -n "$IMG_NAME" ]; then
            for DONOR_VOL in $(docker volume ls --format '{{.Name}}' 2>/dev/null | grep -E '_ds_pkg$' | grep -v "^${TARGET_VOL}$" || true); do
                echo "  ⚡ Übernehme gecachte Kits aus Volume '$DONOR_VOL'..."
                docker run --rm -u 0 -v "${DONOR_VOL}:/src:ro" -v "${TARGET_VOL}:/dst" --entrypoint "" "$IMG_NAME" python -c "
import json, os, shutil
from pathlib import Path
src, dst = Path('/src'), Path('/dst')
dst.mkdir(parents=True, exist_ok=True)
for item in src.iterdir():
    if item.name == '.kit_commits.json':
        continue
    target = dst / item.name
    if not target.exists():
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
sc, dc = src / '.kit_commits.json', dst / '.kit_commits.json'
if sc.exists():
    sdata = json.loads(sc.read_text('utf-8')) if sc.exists() else {}
    ddata = json.loads(dc.read_text('utf-8')) if dc.exists() else {}
    for k, v in sdata.items():
        ddata.setdefault(k, v)
    dc.write_text(json.dumps(ddata, indent=2), 'utf-8')
" 2>/dev/null || true
            done
        fi
        docker compose $ENV_ARG run --rm --no-deps -u 0 --entrypoint "" web sh -c '
            mkdir -p /opt/ds-pkg /app/staticfiles
            for url in $(grep -E "(django-design-studio|-django-kit)" /app/requirements.txt || true); do
                repo_slug=$(echo "$url" | sed -E "s|.*/([^/]+)/archive/.*|\1|")
                mod_name=$(echo "$repo_slug" | sed -e "s/django-design-studio/design_studio/" -e "s/-django-kit/_kit/")
                if [ ! -d "/opt/ds-pkg/$mod_name" ]; then
                    echo "  📦 Lade fehlendes Kit $repo_slug ..."
                    pip install --upgrade --no-deps --no-cache-dir --root-user-action=ignore --target /opt/ds-pkg "$url" >/dev/null
                fi
            done
            chmod -R a+rwX /opt/ds-pkg /app/staticfiles 2>/dev/null || true
        '
    fi
fi

# 4. Start/update container & wait until running (not restarting) — --no-build guarantees zero image build!
docker compose $ENV_ARG up -d --no-build
for i in 1 2 3 4 5 6 7 8 9 10; do
    STATE=$(get_web_state)
    [ "$STATE" = "running" ] && break
    sleep 2
done
STATE=$(get_web_state)
if [ "$STATE" != "running" ]; then
    echo "❌ Container web startet nicht (Status: ${STATE:-unbekannt}). Diagnose:"
    docker compose $ENV_ARG run --rm --no-deps --entrypoint "" web python manage.py check || true
    docker compose $ENV_ARG logs --tail 40 web
    exit 1
fi

# 5. External PyPI deps ONLY when requirements.txt changed (exclude Baukasten kit URLs so kits never duplicate into site-packages)
if [ "$FORCE_DEPS" = "1" ] || { [ -n "$OLD_HEAD" ] && git diff --name-only "$OLD_HEAD" HEAD 2>/dev/null | grep -q "^requirements\.txt$"; }; then
    echo "📦 Aktualisiere externe Python-Pakete (ohne Baukasten-Kits)..."
    docker compose $ENV_ARG exec -u 0 web sh -c 'grep -Ev "(django-design-studio|-django-kit)" requirements.txt > /tmp/req_ext.txt || true; [ -s /tmp/req_ext.txt ] && pip install -q --no-cache-dir --root-user-action=ignore -r /tmp/req_ext.txt || true'
fi

# 6. Sync Baukasten kits persistently into /opt/ds-pkg (only changed commits!)
if [ "$NO_KITS" = "0" ]; then
    echo "🧩 Synchronisiere Baukasten-Kits nach /opt/ds-pkg..."
    SYNC_FLAG=""
    [ "$FORCE_KITS" = "1" ] && SYNC_FLAG="--force"
    docker compose $ENV_ARG exec web python manage.py ops_sync_kits $SYNC_FLAG
fi

# 7. Database migrations (auto-detect multi-tenant migrate_all vs standard migrate)
echo "⚙️ Datenbank-Migrationen..."
if [ -f "core/management/commands/migrate_all.py" ]; then
    docker compose $ENV_ARG exec web python manage.py migrate_all
else
    docker compose $ENV_ARG exec web python manage.py migrate --noinput
fi
if grep -q "DatabaseCache" config/settings.py 2>/dev/null; then
    docker compose $ENV_ARG exec web python manage.py createcachetable 2>/dev/null || true
fi

# 8. Translations (if locale/ exists) & static files (fix ownership so WhiteNoise os.utime never hits EPERM)
WEB_UID=$(docker compose $ENV_ARG exec web id -u 2>/dev/null | tr -d '
' || echo "0")
WEB_GID=$(docker compose $ENV_ARG exec web id -g 2>/dev/null | tr -d '
' || echo "0")
docker compose $ENV_ARG exec -u 0 web sh -c "mkdir -p /app/staticfiles /opt/ds-pkg && chown -R ${WEB_UID}:${WEB_GID} /app/staticfiles /opt/ds-pkg" 2>/dev/null || true

if [ -d "locale" ]; then
    echo "🌍 Kompiliere Uebersetzungen..."
    docker compose $ENV_ARG exec web python manage.py compilemessages 2>/dev/null || true
fi
echo "🎨 Sammle statische Dateien..."
docker compose $ENV_ARG exec web python manage.py collectstatic --noinput

# 9. Restart web container
echo "🔄 Starte Container neu..."
docker compose $ENV_ARG restart web

echo "-----------------------------------"
echo "✅ FAST Update abgeschlossen!"
