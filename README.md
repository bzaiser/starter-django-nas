# starter-django-nas

Tool- und KI-unabhängiges Django + Docker + Gunicorn/WhiteNoise Starter-Template für den App-Baukasten.

## 1. Neue App am PC erstellen

```powershell
cd d:\Daten\Dev\starter-django-nas
python create_app.py          # Öffnet Checkbox-GUI (Desktop)
python create_app.py --cli    # Terminal-Modus (z. B. direkt per SSH)
```
In der GUI wählst du:
- **App-Name** (z. B. `Rezeptverwaltung`) & **Projekt-Slug** (z. B. `rezepte_app`)
- **Zielordner** (z. B. `D:\Daten\Dev\rezepte_app`) & **Docker-Port** (z. B. `8015`)
- **GitHub-Repo (optional)** (z. B. `bzaiser/rezepte_app` — damit die In-App-Update-Funktion das App-Repo sofort kennt)
- **Module zum Anhaken** (`domain_kit`, `auth_kit`, `notify_kit`, `cal_kit`, `grid_kit`, `seed_kit`, `ops_kit`)
- Optional: **„Docker-Image direkt am PC bauen & als .tar für NAS exportieren“**

---

## 2. Docker-Image am PC bauen & aufs Synology-NAS kopieren (ohne Build auf dem NAS)

Falls du den Haken beim Erstellen nicht gesetzt hast oder später das Basis-Image neu bauen möchtest, führe im neuen App-Ordner am Windows-PC aus:
```powershell
.\docker\build-pc-image.ps1
```
Das Skript baut `<slug>:latest` (`linux/amd64`) und speichert **`dist\<slug>-image.tar`**.

### Auf dem Synology-NAS (Erstinstallation):
1. App-Code aufs NAS bringen (empfohlen per `git clone https://github.com/bzaiser/<repo>.git`, damit spätere In-App-Updates per `git pull` funktionieren) und `.env` anlegen/kopieren.
2. `dist\<slug>-image.tar` in den App-Ordner auf dem NAS kopieren.
3. Auf dem NAS ausführen:
   ```bash
   ./docker/load-nas-image.sh
   ```
   *(Lädt das PC-Image per `docker load` und startet automatisch `./docker/update-fast.sh` inkl. `/opt/ds-pkg` Kit-Sync, Migrationen & Staticfiles.)*

---

## 3. Spätere Updates im laufenden Betrieb (wie bei allen bestehenden Apps)

- **In-App Updates im Browser (`Einstellungen → Updates` / `/ops/updates/`):**
  - Aktualisiert Baukasten-Kits direkt nach `/opt/ds-pkg`, installiert/deaktiviert optionale Kits über `data/installed_kits.json` und zieht App-Commits per `git pull`.
- **Oder per SSH auf dem NAS (ohne Image-Rebuild):**
  ```bash
  ./docker/update-fast.sh
  ```

---

## Enthält (Persistenter Baukasten-Standard)
- `django-design-studio` (inkl. Offline-Vendor-Assets & PWA)
- Optional: `domain-django-kit`, `auth-django-kit`, `notify-django-kit`, `cal-django-kit`, `grid-django-kit`, `seed-django-kit`, `ops-django-kit`
- **`Dockerfile` & `docker-compose.yml`**:
  - Festes Image-Tag `image: <slug>:latest` + `build: .`
  - Non-Root-User (`appuser`) + `git config --system --add safe.directory '*'` für In-App `git pull`
  - Persistentes Named Volume `ds_pkg:/opt/ds-pkg` (`PYTHONPATH=/opt/ds-pkg`, `DESIGN_STUDIO_TARGET=/opt/ds-pkg`)
  - Bind-Mounts `.:/app` (App-Code) und `./data:/app/data` (DB, Backups, `installed_kits.json`)
- **`ops_kit.runtime`-Integration**: Nachinstallieren und Entfernen optionaler Kits über `data/installed_kits.json` ohne Änderungen an `settings.py` / `urls.py`.
- **Einheitliche Skripte**:
  - `./docker/update-fast.sh` (`--no-kits`, `--deps`, `--force-kits`)
  - `./docker/update.sh` (lokaler Image-Rebuild + `update-fast.sh`)
  - `.\docker\build-pc-image.ps1` (PC-Build → `dist/<slug>-image.tar`)
  - `./docker/load-nas-image.sh` (NAS `docker load` + `update-fast.sh`)
- **`AGENTS.md` & `.agents/skills/django-baukasten/SKILL.md`**: Verbindliche Design-, Migrations- und Persistenz-Regeln.
