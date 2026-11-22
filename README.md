# starter-django-nas

Tool- und KI-unabhängiges Django + Docker + Gunicorn/WhiteNoise Starter-Template für den App-Baukasten (**ohne Docker/Podman/WSL am Windows-PC!**).

## 1. Neue App am PC erstellen (kein Docker/WSL am PC nötig)

```powershell
cd d:\Daten\Dev\starter-django-nas
python create_app.py          # Öffnet Checkbox-GUI (Desktop)
python create_app.py --cli    # Terminal-Modus (z. B. direkt per SSH auf dem NAS)
```
In der GUI wählst du:
- **App-Name** (z. B. `Rezeptverwaltung`) & **Projekt-Slug** (z. B. `rezepte_app`)
- **Zielordner** (z. B. `D:\Daten\Dev\rezepte_app`) & **Docker-Port** (z. B. `8015`)
- **GitHub-Repo (optional)** (z. B. `bzaiser/rezepte_app` — für spätere In-App Updates)
- **Module zum Anhaken** (`domain_kit`, `auth_kit`, `notify_kit`, `cal_kit`, `grid_kit`, `seed_kit`, `ops_kit`)

---

## 2. Auf dem Synology-NAS starten (ohne Image-Build!)

1. Erstellten App-Ordner aufs NAS bringen (entweder per `git push` + `git clone` auf dem NAS oder Ordner direkt aufs NAS kopieren).
2. Auf dem NAS im App-Ordner einfach ausführen:
   ```bash
   ./docker/update-fast.sh
   ```
   **Was passiert beim ersten Start automatisch?**
   - `update-fast.sh` erkennt, dass `<slug>:latest` noch nicht existiert, und **übernimmt in 0,1 Sekunden dein bereits auf dem NAS vorhandenes Baukasten-Basis-Image** (`sammlungsverwaltung-web:latest`, `finanzplan-web:latest` oder `gewicht-web:latest`) per `docker tag` – **kein `docker build` auf PC oder NAS nötig!**
   - Alle angehakten Baukasten-Kits werden nach `/opt/ds-pkg` synchronisiert, Migrationen & `collectstatic` ausgeführt und der Container gestartet.

---

## 3. Spätere Updates im laufenden Betrieb

- **In-App Updates im Browser (`Einstellungen → Updates` / `/ops/updates/`):**
  - Aktualisiert Baukasten-Kits nach `/opt/ds-pkg`, installiert/deaktiviert optionale Kits über `data/installed_kits.json` und zieht App-Commits per `git pull`.
- **Oder per SSH auf dem NAS:**
  ```bash
  ./docker/update-fast.sh
  ```
