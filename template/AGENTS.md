# Architektur- & Baukasten-Regeln (Tool- & KI-unabhängig)

1. **Templates & UI:**
   - Erbe immer von `design_studio/layouts/base.html`, `design_studio/layouts/dashboard.html` oder `design_studio/layouts/list_page.html`.
   - Lege **niemals** lokale Kopien unter `templates/design_studio/` oder `static/design_studio/` an.
   - Nutze `design_studio/components/kpi_card.html` für KPI-Karten.
   - Keine externen CDN-Links einbauen (Bootstrap, Icons und SortableJS kommen lokal aus `design_studio`).
2. **Baukasten-Pakete nutzen (nicht neu erfinden):**
   - Auth/Profil: `auth_kit` (`auth-django-kit`)
   - Benachrichtigungen/Mails/Webhooks: `notify_kit` (`notify-django-kit`)
   - Tabellen/Suche/Export: `grid_kit.mixins.DataGridMixin` (`grid-django-kit`)
   - Kalender/.ics: `cal_kit` (`cal-django-kit`)
   - Demo-Daten: `<app>/seeders.py` + `seed_kit` (`seed-django-kit`)
   - Healthcheck/Audit/Backup: `ops_kit` (`ops-django-kit`)
3. **Verifikation vor Commit:**
   - `python manage.py makemigrations --check --dry-run`
   - `python manage.py design_studio_doctor --strict`
   - `python manage.py test`
4. **Docker- & Update-Persistenz (VERBINDLICH):**
   - Niemals nicht-persistente Terminal-Fixes (`docker compose exec ... pip install` nach `site-packages`) anbieten — Fixes gehören immer ins Git-Repo + `./docker/update-fast.sh`.
   - Alle Baukasten-Kits liegen persistent im Named Volume `ds_pkg:/opt/ds-pkg` (`PYTHONPATH=/opt/ds-pkg`, `DESIGN_STUDIO_TARGET=/opt/ds-pkg`) und werden ausschließlich via `ops_sync_kits` synchronisiert.
   - Dynamisch nachinstallierte Kits stehen in `data/installed_kits.json` (geladen über `ops_kit.runtime`), niemals `settings.py` oder `urls.py` zur Laufzeit editieren.
