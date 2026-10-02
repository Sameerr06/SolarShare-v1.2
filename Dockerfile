# ============================================================
# SolarShare — Backend (FastAPI + Uvicorn)
# ============================================================
# Stage 1: builder — install all deps (including heavy ones
# like prophet / scikit-learn) into a virtual-env layer so
# the final image stays clean.
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# System libs needed to compile Prophet / scipy wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libstdc++6 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create isolated venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================
# Stage 2: runtime — lean image, copy only the venv + source
# ============================================================
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="SolarShare Backend" \
      org.opencontainers.image.description="FastAPI backend for the SolarShare solar-energy sharing platform" \
      org.opencontainers.image.version="0.2.0"

# Runtime system libs (libgomp needed by prophet/lightgbm)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual-env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Unbuffered stdout/stderr so container logs stream live under `docker logs`.
# PYTHONDONTWRITEBYTECODE keeps the runtime tree free of stray .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

# Copy application source
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY .env.example ./.env.example

# NOTE: the Zenodo `electricity_hourly_dataset.tsf` (~36 MB) is deliberately
# NOT baked into the image. Mount it instead (see docker-compose.yml) so the
# image stays small and no third-party dataset is shipped inside it.
RUN mkdir -p /app/db_data /app/data && \
    adduser --disabled-password --gecos "" solarshare && \
    chown -R solarshare:solarshare /app /app/db_data /app/data

# Persistent volume mount-point for the SQLite database
VOLUME ["/app/db_data"]

EXPOSE 8000

USER solarshare

# Health-check — hits the /api/health endpoint
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Seed the demo estate/tenants/users (idempotent), then start Uvicorn.
# `exec` makes uvicorn PID 1 so it receives SIGTERM directly and shuts down
# gracefully; without it, `sh` stays PID 1 and swallows the signal, forcing
# Docker to SIGKILL after the grace period.
# PYTHONPATH=/app is required: running `python scripts/seed_demo.py` puts
# `scripts/` (not /app) on sys.path, so `import app` fails without it.
# Seeding is non-fatal: a seed failure must not take the API down.
#
# Two deployment-target switches:
#   * SEED_DEMO=false skips seeding. Compose sets it to true; Vercel (where a
#     cold start re-runs this CMD against an already-migrated PostgreSQL
#     database) leaves it false so no bcrypt hashing happens on every cold start.
#   * $PORT is honoured because serverless platforms inject the listening port;
#     Compose injects nothing, so it falls back to 8000.
CMD ["sh", "-c", "if [ \"${SEED_DEMO:-false}\" = \"true\" ]; then PYTHONPATH=/app python scripts/seed_demo.py || echo '[seed] failed - continuing with existing data'; fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers"]
