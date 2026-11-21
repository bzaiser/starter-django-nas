# starter-django-nas

Tool- und KI-unabhängiges Django + Docker + Gunicorn/WhiteNoise Starter-Template für den App-Baukasten.

## Neue App erstellen

### Option 1: Interaktiver App-Baukasten (GUI mit Checkboxen + `.env`-Generator, ohne Zusatzpakete)
```bash
python create_app.py          # Öffnet Checkbox-GUI (Desktop)
python create_app.py --cli    # Terminal-Modus (z. B. direkt per SSH auf dem NAS)
```

### Option 2: Per `copier`
```bash
pip install copier
copier copy gh:bzaiser/starter-django-nas ./meine-neue-app
```

## Enthält (Persistenter Baukasten-Standard)
- `django-design-studio` (inkl. Offline-Vendor-Assets & PWA)
- Optional: `domain-django-kit`, `auth-django-kit`, `notify-django-kit`, `cal-django-kit`, `grid-django-kit`, `seed-django-kit`, `ops-django-kit`
- **`Dockerfile` & `docker-compose.yml`**:
  - Non-Root-User (`appuser`)
  - Persistentes Named Volume `ds_pkg:/opt/ds-pkg` (`PYTHONPATH=/opt/ds-pkg`, `DESIGN_STUDIO_TARGET=/opt/ds-pkg`)
  - Bind-Mounts `.:/app` (App-Code) und `./data:/app/data` (DB, Backups, `installed_kits.json`)
- **`ops_kit.runtime`-Integration**: Nachinstallieren und Entfernen optionaler Kits über `data/installed_kits.json` ohne Änderungen an `settings.py` / `urls.py` (`apply_runtime_installed_apps`, `optional_kit_path`, `filter_runtime_context_processors`).
- **Einheitliche Update-Skripte**:
  - `./docker/update-fast.sh` (`--no-kits`, `--deps`, `--force-kits`) — synct nur geänderte Kits nach `/opt/ds-pkg`, migriert (`migrate_all` / `migrate`), sammelt Staticfiles, startet Container neu.
  - `./docker/update.sh` — Docker-Image-Rebuild inkl. anschließendem `/opt/ds-pkg`-Sync.
- **`AGENTS.md` & `.agents/skills/django-baukasten/SKILL.md`**: Verbindliche Design-, Migrations- und Persistenz-Regeln für jede KI und jeden Editor.
