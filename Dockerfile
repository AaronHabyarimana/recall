# Zwei Stufen, damit uv und die Build-Artefakte nicht im ausgelieferten Image landen.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Erst nur die Abhaengigkeiten aufloesen. Diese Schicht wird neu gebaut, wenn sich
# pyproject.toml oder uv.lock aendern, aber nicht bei jeder Codeaenderung.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --group ui --group api

# PyMuPDF, pandas und pyarrow liefern manylinux-Wheels. Es wird kein Compiler und
# kein System-Header gebraucht, deshalb bleibt das Image ohne build-essential.
#
# --no-editable ist wichtig: uv installiert das Projekt sonst als .pth-Verweis auf
# /app/src, und dann muesste die Runtime-Stufe den Quellbaum mitschleppen.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --group ui --group api


FROM python:3.12-slim-bookworm AS runtime

# curl braucht nur der HEALTHCHECK. Sonst kommt nichts dazu.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 recall

WORKDIR /app
COPY --from=builder --chown=recall:recall /app/.venv /app/.venv
COPY --chown=recall:recall config.toml /app/config.toml
COPY --chown=recall:recall samples /app/samples
# Streamlit sucht seine Konfiguration im Arbeitsverzeichnis. Ohne diese Zeile
# faellt die App auf das dunkle Standardtheme zurueck, und die Diagrammfarben
# aus ui/theme.py sind gegen die helle Flaeche #fcfcfb geprueft, nicht dagegen.
COPY --chown=recall:recall .streamlit /app/.streamlit

# /data ist der Mountpunkt fuer die Lerndatenbank. Ohne Volume ist der Lernfortschritt
# nach `docker run --rm` weg, siehe docker-compose.yml.
RUN mkdir -p /data && chown recall:recall /data
VOLUME ["/data"]

ENV PATH="/app/.venv/bin:$PATH" \
    RECALL_DB=/data/recall.db \
    RECALL_CONFIG=/app/config.toml \
    PYTHONUNBUFFERED=1

USER recall
EXPOSE 8501 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

# ENTRYPOINT und CMD getrennt, damit `docker run <image> api` und
# `docker run <image> review stats` ohne --entrypoint funktionieren.
ENTRYPOINT ["recall"]
CMD ["ui", "--kein-browser", "--host", "0.0.0.0", "--port", "8501", "--db", "/data/recall.db"]
