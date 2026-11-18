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
   - `python manage.py design_studio_doctor --strict`
   - `python manage.py test`
