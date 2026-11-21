# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/ds-pkg \
    DESIGN_STUDIO_TARGET=/opt/ds-pkg \
    PIP_CACHE_DIR=/tmp/pip-cache

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY --chown=appuser:appuser . .
RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh \
    && mkdir -p /app/staticfiles /app/data /opt/ds-pkg \
    && chown -R appuser:appuser /app /opt/ds-pkg \
    && chmod 777 /opt/ds-pkg

USER appuser
EXPOSE 8000

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
