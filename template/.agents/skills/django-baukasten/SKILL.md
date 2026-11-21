---
name: django-baukasten
description: >-
  Verbindliche Architektur-, Design- und Komponentenregeln für alle Django-Projekte
  aus dem App-Baukasten (starter-django-nas + design_studio + *_kit). Immer verwenden,
  wenn eine Baukasten-App erstellt, erweitert, um Seiten/Models/Views ergänzt oder
  gestylt wird.
---

# Django App-Baukasten: Verbindliche Regeln

## 1. Striktes Design- & Layout-Verbot ("Kein CSS-Gemurkse")
- **Keine freien HTML-Grundgerüste:** Jedes Template MUSS von einem `design_studio`-Layout erben:
  - `{% extends "design_studio/layouts/base.html" %}` (freie Seiten / Formulare / Detailseiten)
  - `{% extends "design_studio/layouts/dashboard.html" %}` (Dashboards mit `kpi_cards`, `dashboard_charts`, `dashboard_tables`)
  - `{% extends "design_studio/layouts/list_page.html" %}` (Tabellen-/Listenseiten mit `page_actions`, `table_filters`, `table_head`, `table_body`, `card_footer`)
- **Keine neue Seite ohne Menü-Eintrag:** Jede neue Haupt- oder Unterseite muss in `settings.py` unter `DESIGN_STUDIO_MENU_ITEMS` registriert werden. Niemals eine eigene `<nav>` bauen.
- **Keine lokalen Overrides:** Niemals Dateien unter `templates/design_studio/` oder `static/design_studio/` anlegen.
- **Kein eigenes CSS-Gemurkse:**
  - Keine `<style>`-Blöcke und keine eigenen CSS-Dateien für Layout, Farben, Abstände oder Karten-Design anlegen.
  - Keine externen CDN-Links (`cdn.jsdelivr.net`, `unpkg.com`, Google Fonts etc.) einbauen — Bootstrap 5, Bootstrap Icons (`bi-*`) und SortableJS kommen lokal aus `design_studio`.
  - Ausschließlich Bootstrap-5-Utility-Klassen, Standard-Klassen (`card`, `table`, `modal`, `badge`, `btn`) und Theme-Variablen (`--theme-state-1` bis `--theme-state-8`, `--app-primary`) nutzen.
- **KPI-Karten:** Immer `{% include "design_studio/components/kpi_card.html" with title=... value=... icon="bi-..." size="sm|md|lg" state=1..8 %}` nutzen.

## 2. Baukasten-Pakete nutzen (nicht neu erfinden)
Prüfe `INSTALLED_APPS` in `settings.py` und nutze vorhandene Kits statt eigener Implementierungen:
- **`domain_kit`**: Stammdaten (`Category` mit `purpose` & `color_state` 1..8, `Unit`, `Status` mit Sortier-`position`, `Role`), Personen, Assets, Dokumente, globale Suche (`/domain/`).
- **`auth_kit`**: Login/Logout/Passwort/UserProfile (`/accounts/`, `LOGIN_URL = "auth_kit:login"`).
- **`grid_kit`**: Für jede Listen-/Tabellenansicht `grid_kit.mixins.DataGridMixin` + Django `ListView` (`search_fields`, `allowed_sorts`, `export_fields`) für Suche, Sortierung, Paginierung und CSV/JSON-Export verwenden.
- **`notify_kit`**: In-App-Benachrichtigungen, HTML-Mails & Webhooks (`/notifications/`).
- **`cal_kit`**: Kalender, Monatsansicht, `.ics`-Feed & CalDAV (`/calendar/`).
- **`seed_kit`**: Realistische Demo-Daten pro App in `<app>/seeders.py` mit `register_seeder(name, fn, order=..., reset_fn=...)` und `fake_name`, `fake_email`, `fake_amount`, `fake_date_offset`.
- **`ops_kit`**: Healthcheck (`/healthz`), `AuditLog`, Backups (`manage.py ops_backup`, `/ops/`).

## 3. Code- & Django-Standards
- Alle User-Modelle über `settings.AUTH_USER_MODEL` referenzieren.
- Jede schreibende View mit `@login_required` / `LoginRequiredMixin` absichern (sofern `auth_kit` aktiv ist).
- CRUD-Formulare sauber als Bootstrap-5-Formulare/Modals oder Django-Generic-Views (`CreateView`, `UpdateView`, `DeleteView`) mit `messages.success(...)` umsetzen.
- Für jedes neue Model sofort `makemigrations` + `migrate` ausführen und im Django-Admin registrieren.

## 4. Pflicht-Verifikation vor Abschluss
Jede Änderung oder neue App gilt erst als fertig, wenn alle folgenden Befehle fehlerfrei durchlaufen:
1. `python manage.py check`
2. `python manage.py makemigrations --check --dry-run`
3. `python manage.py design_studio_doctor --strict`
4. `python manage.py seed_demo --dry-run --count 5` (sofern `seed_kit` aktiv)
5. `python manage.py test`

## 5. NAS-, Docker- & Persistenz-Regeln (VERBINDLICH)
- **VERBOT nicht-persistenter Terminal-Fixes:** Niemals Befehle anbieten, die Pakete oder Dateien nur flüchtig im laufenden Container verändern (z. B. `docker compose exec ... pip install` nach `site-packages` oder manuelle Edits im Container). Fixes gehören **immer** persistent ins Git-Repo (`commit` + `push` → `./docker/update-fast.sh`). Ist ausnahmsweise ein temporärer Notfall-Befehl im Terminal unvermeidbar, muss er unübersehbar mit `[NICHT PERSISTENT]` markiert werden — bevorzugt gar nicht erst anbieten.
- **Einziger persistenter Kit-Pfad (`/opt/ds-pkg`):**
  - Jede Baukasten-App MUSS in `docker-compose.yml` das Named Volume `ds_pkg:/opt/ds-pkg` sowie `.:/app` und `./data:/app/data` mounten und `PYTHONPATH=/opt/ds-pkg` + `DESIGN_STUDIO_TARGET=/opt/ds-pkg` setzen.
  - Jedes `Dockerfile` MUSS `ENV PYTHONPATH=/opt/ds-pkg` und `ENV DESIGN_STUDIO_TARGET=/opt/ds-pkg` setzen sowie `RUN mkdir -p /opt/ds-pkg && chmod 777 /opt/ds-pkg` ausführen (funktioniert für `root`, `app` und `appuser`).
  - Alle Baukasten-Kits (`django-design-studio`, `*-django-kit`) werden zur Laufzeit **ausschließlich** über `python manage.py ops_sync_kits` bzw. `ops_kit` nach `/opt/ds-pkg` installiert — niemals doppelt in `site-packages`!
- **Kein Laufzeit-Editieren von `settings.py` / `urls.py`:** Nachinstallierte und deaktivierte Kits werden ausschließlich in `data/installed_kits.json` (`kits`/`disabled`) gespeichert und über `ops_kit.runtime` (`apply_runtime_installed_apps`, `optional_kit_path`, `filter_runtime_context_processors`) geladen; Pflicht-Kits mit harten FK-Abhängigkeiten über `OPS_REQUIRED_KITS` schützen. Niemals `git checkout -- settings.py` in Update-Skripten verwenden.
- **Einheitliches `docker/update-fast.sh` & `docker/update.sh`:** Alle Baukasten-Apps nutzen das identische Standard-Skript (inkl. `ops_sync_kits`, automatischer Erkennung von `migrate_all` vs. `migrate`, `compilemessages` falls `locale/` existiert, `collectstatic` und `chmod -R a+rX .`). Keine app-spezifischen Sonder-Hacks (`DS_COMMIT_FILE` etc.).
- **Multi-Tenant & Migrations-Pflicht:**
  - Vor jedem Push in einem Kit oder einer App zwingend `python manage.py makemigrations --check --dry-run` ausführen.
  - In Multi-Tenant-Apps immer `migrate_all` statt `migrate` ausführen.
  - Container-weite Kit-Commit-Hashes liegen zentral in `/opt/ds-pkg/.kit_commits.json`; `ops_kit.UpdateSettings` nutzt immer `using("default")`.
