# starter-django-nas

Tool- und KI-unabhängiges Django + Docker + Gunicorn/WhiteNoise Starter-Template für den App-Baukasten.

## Neue App erstellen
```bash
pip install copier
copier copy gh:bzaiser/starter-django-nas ./meine-neue-app
```

## Enthält
- `django-design-studio` (inkl. Offline-Vendor-Assets & PWA)
- Optional: `auth-django-kit`, `notify-django-kit`, `cal-django-kit`, `grid-django-kit`, `seed-django-kit`, `ops-django-kit`
- `Dockerfile` (Non-Root-User), `docker-compose.yml` (mit `PYTHONPATH=/opt/ds-pkg` für Live-Updates ohne Rebuild), `entrypoint.sh`
- `AGENTS.md` mit klaren Architektur-Regeln für jede KI und jeden Editor
