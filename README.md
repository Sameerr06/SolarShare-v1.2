# SolarShare

**Shared solar energy forecasting, fair allocation and time-of-use billing for MSME industrial estates.**

A rooftop solar estate does not have one customer — it has dozens of MSMEs drawing
from the same inverter, the same battery and the same grid connection, each with a
different tariff window and a different idea of what a "fair share" of the
generated power means. SolarShare models that shared estate: it forecasts solar
generation and per-tenant load, apportions the solar between tenants, and bills
each of them against the Tamil Nadu time-of-use tariff.

* **Backend** — FastAPI, SQLAlchemy 2, Pydantic v2, Prophet, scikit-learn, ReportLab
* **Frontend** — React 18 + Vite + TypeScript + Tailwind + Recharts
* **Delivery** — multi-stage Docker images orchestrated with Compose, GitHub Actions CI
* **Tests** — 308 pytest tests, green on Python 3.10 / 3.11 / 3.12

---

## What is real and what is a prototype

Every response that mixes measured data with a prototype assumption says so in the
payload itself (`is_demo`, `explanatory_note`). Nothing here pretends to be real
data.

| Area | Status | Source |
|---|---|---|
| Tenant load ingestion (321 series, 8.44M hourly readings) | **Real** | Zenodo "Electricity Hourly Dataset" (Monash), DOI `10.5281/zenodo.4656140` |
| 321 → 6 load-profile selection (k-means clustering, CV/PAR) | **Real** | computed from the ingested series |
| Solar generation estimates | **Real, once synced** | NASA POWER hourly API (ALLSKY_SFC_SW_DWN) × estate PV config |
| Solar & tenant load forecasting (Prophet) | **Real when history exists**, transparent demo fallback otherwise | trained on the rows above; tenant models cached in `app/resources/models/` |
| Billing summaries, allocation split, battery status | **Prototype values** | documented assumptions, not measured |
| Fair-allocation optimizer (PuLP) | **Not implemented** — `/api/allocation/current` returns a labelled demo split | — |
| Tariffs, PV/battery sizing | **Prototype assumptions** | disclosed on every model (`notes`, `source`, `source_reference`) |

The electricity dataset is a **public proxy** for Coimbatore MSME smart-meter data.
It is never presented as the real thing.

---

## Feature tour

**Admin**

* **Overview** — estate KPIs: dataset scale, solar output, battery state, allocation, savings
* **Load profiles** — all 321 clustered series, the 6 selected tenant profiles, weekday/weekend shapes
* **Solar generation** — PV configuration and the hourly generation series with provenance
* **Forecasting** — Prophet solar forecast and per-tenant load forecast with uncertainty bounds, retrained on demand and cached
* **Allocation** — current fair-allocation split across tenants (demo model)
* **Battery** — configuration and live state-of-charge view
* **Billing** — Tamil Nadu ToU tariff periods, monthly per-tenant summary, generated PDF invoices
* **Analytics** — dataset-wide statistics over the real ingested series
* **Tenants** (`/tenants`) — browse any tenant's load telemetry from the admin side

**Tenant** (`/portal`)

* Own load forecast, own allocation row, own bill — a tenant token can never read another tenant's data
* Consumption and savings against the shared solar supply

**Roles in one table**

| Route group | ADMIN | TENANT |
|---|---|---|
| `/api/estates*`, `/api/load-profiles/selected`, `/api/solar/generation`, `/api/battery/status` | read | read |
| `/api/allocation/current` | all tenants' rows | **own row only** |
| `/api/billing/summary` | any tenant or whole estate | **pinned to own tenant** |
| `/api/forecasting/tenants/{id}` | any tenant | **own tenant only** |
| `/api/dashboard/overview`, `/api/analytics/overview`, `/api/load-profiles`, `/api/solar/pv-config`, `/api/battery/config`, `/api/billing/tariffs`, `/api/forecasting/solar` | read | 403 |
| `/api/billing/invoices` (list), `/api/billing/invoices/pdf` | any invoice | **own invoices only** (`?tenant_id=` of another tenant → 403) |
| `/api/estates` (write), `/api/estates/{id}/sync-weather`, `/api/billing/invoices/generate`, `/api/billing/invoices/estate/summary.pdf`, `/api/data/nasa-power` | read/write | 403 |

Every route except `/api/health` (and FastAPI's auto-generated docs) requires a
bearer token. `tests/test_api_auth_enforcement.py` pins the whole matrix down.

---

## Quick start (Docker)

Requires Docker with the Compose plugin. On first boot the backend creates its
schema, seeds the demo estate/tenants/users, and starts serving.

```bash
cp .env.example .env
npm run docker:up        # docker compose up -d --build  (first build ~6-10 min)
```

Open <http://localhost> and sign in:

| Role | Username | Password |
|---|---|---|
| Estate admin | `ADMIN` | `4005` |
| Tenant | `T258`, `T11`, `T301`, `T300`, `T84`, `T3` | `101` … `106` |

> `docker compose up -d` **without** `--build` starts the previously built image and
> silently ignores your changes. `npm run docker:up` and `make up` always rebuild.
> Use `npm run docker:rebuild` to force `--no-cache`.

Other commands: `npm run docker:logs`, `npm run docker:ps`, `npm run docker:down`,
`npm run docker:seed`. A `Makefile` mirrors these (`make up`, `make logs`, …) plus
`make ingest`, `make profiles` and `make train`.

The API is published on `127.0.0.1:8000` only, so <http://localhost:8000/docs> works
locally while the port stays unreachable from the network.

## Local development (no Docker)

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt                  # or requirements-dev.txt on 3.12+
cp .env.example .env
uvicorn app.main:app --reload --port 8000

npm install
npm run dev            # Vite on http://localhost:3000, proxies /api → :8000
```

`pytest` runs the suite against an isolated in-memory SQLite database — it never
touches your `.env` database.

---

## Populating real data

`scripts/seed_demo.py` only creates the estate, tenants and users, so a fresh
volume shows `0 obs` until the dataset is ingested. The seed attaches the demo
users to the tenants of the estate the API already treats as active (lowest id,
same rule as `GET /api/estates/active`) and is safe to re-run - so a database
that already holds ingested data, PV config or invoices keeps them, and the demo
logins land on the tenants that own them. To fill a fresh volume:

```bash
# 1. The Zenodo .tsf (34 MB) is committed at data/electricity_hourly_dataset.tsf
#    and mounted read-only into the backend container.
docker compose exec backend python -c "from app.db.session import SessionLocal; from app.db.init_db import init_db; from app.services.electricity_ingestion import ingest_electricity_dataset; init_db(); print(ingest_electricity_dataset(SessionLocal(), local_path='/app/data/electricity_hourly_dataset.tsf'))"

# 2. Cluster 321 series → 6 tenant profiles and persist the selection.
docker compose exec backend python -c "from app.db.session import SessionLocal; from app.services.load_profiling import run_profiling_pipeline; import json; print(json.dumps(run_profiling_pipeline(SessionLocal(), persist=True), indent=2, default=str))"

# 3. (Optional) Refresh the tenant load models.
docker compose exec backend python scripts/train_tenant_models.py
```

Solar data comes from NASA POWER instead, per estate, on demand:

```bash
curl -X POST http://localhost/api/estates/1/sync-weather \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{}'
```

NASA POWER's hourly parameters lag real time by months (default window is
back-dated by `NASA_POWER_DATA_LAG_DAYS=120`), so a "last 3 days" sync returns
fill values and no generation estimates. Changing an estate's coordinates purges
the rows recorded at the old location, so one estate can never blend two sites.

---

## Configuration

All settings come from the environment (`app/core/config.py`, `.env.example`).
Nothing is hardcoded in business logic.

| Variable | Default | Notes |
|---|---|---|
| `APP_NAME` / `APP_ENV` / `DEBUG` | `SolarShare` / `development` / `true` | set `APP_ENV=production`, `DEBUG=false` when deploying |
| `DATABASE_URL` | `sqlite:///./solarshare.db` | Compose overrides this to the `db_data` volume |
| `JWT_SECRET_KEY` | placeholder | **must** be replaced: `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | token lifetime |
| `CORS_ORIGINS` | localhost dev servers | only needed when the frontend is hosted separately |
| `NASA_POWER_*` | public API defaults | community, parameters, retries, fill value, data lag |
| `ELECTRICITY_DATASET_*` | Zenodo provenance | `..._LOCAL_PATH` points at the mounted `.tsf` |

`.env` is git-ignored and `.dockerignore`d; only `.env.example` is committed.

---

## Deployment

### Option A — single VPS with Docker Compose (recommended)

This is the shape the repo is built and tested for: two containers, one SQLite
volume, nginx in front of the API.

```bash
# Ubuntu 24.04, 2 vCPU / 4 GB RAM / 30 GB disk (the ingested DB alone is ~1.5 GB)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER" && newgrp docker

git clone https://github.com/Sameerr06/SolarShare-v1.2.git && cd SolarShare-v1.2

cp .env.example .env
sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$(openssl rand -hex 32)|" .env
sed -i 's/^DEBUG=true/DEBUG=false/; s/^APP_ENV=development/APP_ENV=production/' .env

docker compose up -d --build
docker compose ps            # both services should reach "healthy"
```

Terminate TLS in front of nginx — Caddy gets you a certificate automatically:

```bash
echo 'solarshare.example.com { reverse_proxy 127.0.0.1:80 }' | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo ufw allow 22,80,443 && sudo ufw enable
```

Verify: `curl https://solarshare.example.com/api/health` → `{"status":"ok","database":"ok"}`.

**Updating a deployed instance** (the rebuild is not optional):

```bash
git pull && docker compose up -d --build
```

**Backups** — the SQLite file *is* the application state:

```bash
docker run --rm -v <project>_db_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/solarshare-$(date +%F).tar.gz -C /data .
```

The volume name is `<directory>_db_data`; confirm with `docker volume ls`.

### Option B — split hosting

| Piece | Where | Notes |
|---|---|---|
| Frontend | Vercel / Netlify / Cloudflare Pages | `npm run build`; set `VITE_API_BASE_URL=https://api.example.com/api` (`src/api/client.ts`) |
| Backend | Render / Railway / Fly | build from `Dockerfile`, expose port 8000 |

Caveats: SQLite lives on a **volume**, so the backend needs a persistent disk —
free tiers without one lose every ingested row on each redeploy (the demo seed
re-runs, the 8.44M-row dataset does not come back). Add the frontend origin to
`CORS_ORIGINS`. Serving `/api` through nginx as in Option A avoids all of this and
is what CI and the Dockerfiles already exercise.

---

## Testing and CI

```bash
pytest                  # 308 tests
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
npm run lint            # tsc --noEmit
```

`.github/workflows/python-package.yml` runs install → lint → pytest on Python
3.10, 3.11 and 3.12 (3.9 was dropped: `numpy>=2.1`/`scipy>=1.14` no longer ship
3.9 wheels). Route tests authenticate explicitly, and
`tests/test_api_auth_enforcement.py` fails the build if any endpoint stops
requiring a token.

---

## Known limitations

* **No migrations.** The schema is created with `create_all()` on startup, so a
  schema change does not alter an existing database — recreate the volume
  (`docker compose down -v`) to pick up model changes.
* **SQLite, one worker.** Uvicorn runs with `--workers 1` deliberately. Scaling
  out needs PostgreSQL (`DATABASE_URL` is already swappable) and migrations.
* **No rate limiting or account lockout** on `/api/auth/login`.
* **No HTTPS inside Compose** — put a reverse proxy in front (Option A).
* **Fair allocation is not implemented**; the endpoint returns a labelled demo split.
* **Billing numbers are prototype values**, not metered readings; the ToU tariff
  table is a labelled Tamil Nadu FY 2025-26 prototype configuration.
* **Docs are public** at `/docs` and `/openapi.json` (no data, but the route map
  is visible). Disable them in `app/main.py` if that matters for your deployment.
* **1.5 GB database.** Ingesting the full dataset is the single largest cost of
  both disk and first-boot time.

---

## Repository layout

```
app/
  api/          FastAPI routers (auth, estates, data, solar, forecasting,
                allocation, battery, billing, invoices, analytics, dashboard)
  core/         settings, logging, security (bcrypt + JWT)
  db/           engine, session, schema init
  models/       Estate, Tenant, User, configs, tariffs, weather, load profiles
  schemas/      Pydantic request/response models
  services/     ingestion, profiling, forecasting, billing, invoicing, PDF
  integrations/ NASA POWER client, Zenodo .tsf parser, dataset provenance
  resources/models/  cached tenant Prophet models
scripts/        seed_demo.py, train_tenant_models.py, generate_invoice_pdf.py
src/            React SPA (pages/, components/, api/, contexts/)
tests/          pytest suite (in-memory SQLite, offline)
data/           Zenodo .tsf dataset (mounted, not baked into the image)
```

## Data & assumption honesty

Per the locked specification, several values are prototype assumptions rather than
real specifications, and the schema says so on the row itself:

* `PVConfig` / `BatteryConfig` carry a `notes` field disclosing the prototype assumption.
* `Tariff` carries `label` ("Tamil Nadu FY 2025-26 prototype tariff configuration")
  plus `source` / `source_reference`.
* `SolarTariffConfig.notes` discloses that the internal solar rate is SolarShare's own
  prototype rate, not an official tariff.
* Forecast, dashboard, billing and allocation payloads carry `is_demo` and an
  `explanatory_note` whenever prototype values are involved.
