# SolarShare — Backend

Shared Solar Energy Forecasting, Fair Allocation and Time-of-Use Billing Platform for MSME Industrial Estates.

**Current status: Phase 1 — Foundational Architecture only.**
No data ingestion, forecasting, optimization, billing, invoicing, or frontend is implemented yet. See [Roadmap](#roadmap) below.

## Phase 1 scope

- Project structure, FastAPI app foundation
- Configuration management via environment variables (`.env`)
- SQLAlchemy models for core entities: `Estate`, `PVConfig`, `BatteryConfig`, `Tenant`, `Tariff`, `TariffPeriod`, `SolarTariffConfig`, `User`
- Database initialization (`create_all`, SQLite by default)
- Logging
- Basic error handling (validation + unhandled exception handlers)
- Authentication foundation: password hashing (bcrypt), JWT issuance/validation
- ADMIN / TENANT roles with role-enforcing dependency (`require_role`)
- Health-check endpoint
- Test suite (pytest) covering health, config, DB init, and auth/authorization

**Explicitly out of scope for Phase 1** (later phases): NASA POWER ingestion, public electricity dataset ingestion, Prophet forecasting, PuLP allocation, battery simulation, billing engine, PDF invoices, frontend dashboards, analytics.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # adjust values as needed
```

## Running the app

```bash
uvicorn app.main:app --reload
```

- API root: `http://localhost:8000/`
- Interactive docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`

On startup, the app initializes the database schema automatically (`create_all` against the SQLite file configured by `DATABASE_URL`).

## Running tests

```bash
pytest
```

Tests run against an isolated in-memory SQLite database — they never touch the `.env`-configured database file.

## Seeding demo data (optional, for manual verification)

```bash
PYTHONPATH=. python scripts/seed_demo.py
```

Creates one demo `Estate` (Coimbatore, 11.0168/76.9558) and one demo `Tenant`, printing their IDs — useful for manually registering a TENANT user against a real `tenant_id` via `/api/auth/register`. This is a Phase 1 verification convenience only; it does not seed the six locked tenant profiles, PV/battery configs, or tariffs (those are seeded by the phases that consume them).

## Project structure

```
app/
  core/        # config, logging, security (hashing + JWT)
  db/          # SQLAlchemy engine/session, schema init
  models/      # ORM models (Estate, PVConfig, BatteryConfig, Tenant, Tariff*, User)
  schemas/     # Pydantic request/response models
  api/         # FastAPI routers + auth dependencies
  main.py      # app entrypoint
tests/         # pytest suite
```

## Configuration

All settings are environment-driven (see `.env.example`). Notably:
- `DATABASE_URL` — defaults to local SQLite; swap to PostgreSQL later without code changes.
- `JWT_SECRET_KEY` — **must** be replaced with a real secret outside local development.

## Database strategy (Phase 1)

Tables are created via SQLAlchemy `Base.metadata.create_all()` on startup — no Alembic migrations yet. This is intentional for Phase 1 (see `app/db/init_db.py` for rationale) and should be revisited once the schema needs to evolve against data that already exists in a shared environment.

## Data & assumption honesty

Per the locked SolarShare specification, several values that will be introduced in later phases are **prototype assumptions**, not real specifications — and the schema already reflects this:
- `PVConfig` / `BatteryConfig` rows carry a `notes` field defaulting to an explicit prototype-assumption disclosure.
- `Tariff` carries a `label` field defaulting to "Tamil Nadu FY 2025-26 prototype tariff configuration" plus `source` / `source_reference` fields.
- `SolarTariffConfig` carries a `notes` field disclosing it is SolarShare's own internal prototype rate, not an official tariff.

## Public electricity dataset (Phase 2, ingestion scope)

**Source:** Zenodo "Electricity Hourly Dataset", DOI 10.5281/zenodo.4656140 — a public proxy for tenant-load data (NOT actual Coimbatore MSME smart-meter data).

**Locked unit interpretation:**
- Source: "Hourly average electricity demand in kW."
- Internal (SolarShare): "Hourly energy consumption in kWh."
- Conversion: `energy_kwh = hourly_average_kw × interval_hours` (`interval_hours = 1.0` for this dataset) — documented as Energy = Power × Time in `app/integrations/electricity_dataset.py`.

**Sandbox limitation:** this implementation environment cannot reach `zenodo.org` or `huggingface.co`, so the real ~36 MB `.tsf` file could not be downloaded or parsed here. The `.tsf` parser (`app/integrations/tsf_parser.py`) was instead verified against a real, official Monash Archive file (`tests/fixtures/real_monash_sample_ausgrid.tsf`, pulled from `github.com/rakshitha123/TSForecasting`) and exercised against a clearly-labeled synthetic fixture matching the electricity dataset's documented metadata (`tests/fixtures/sample_electricity_hourly_fixture.tsf`).

### Testing the parser against the real file yourself

1. Download the file from Zenodo: https://zenodo.org/records/4656140 — download `electricity_hourly_dataset.zip` and unzip it to get `electricity_hourly_dataset.tsf`.
2. Place it anywhere on your machine, e.g. `C:\data\electricity_hourly_dataset.tsf`.
3. Set the path in your `.env`:
   ```
   ELECTRICITY_DATASET_LOCAL_PATH=E:\SolarShare\data\electricity_hourly_dataset.tsf
   ```
   (Use a forward-slash or raw/escaped path as needed for your shell — e.g. `C:/data/electricity_hourly_dataset.tsf` also works.)
4. From the project root, with the venv activated:
   ```bash
   python -c "from app.integrations.tsf_parser import parse_tsf; ds = parse_tsf(r'C:\data\electricity_hourly_dataset.tsf'); print('series:', len(ds.series)); print('frequency:', ds.metadata.frequency); print('missing:', ds.metadata.missing); print('equallength:', ds.metadata.equallength); print('first series:', ds.series[0].series_name, ds.series[0].start_timestamp, len(ds.series[0].values))"
   ```
5. To run the full ingestion pipeline (parses, validates, converts, and persists to your local SQLite DB):
   ```bash
   python -c "
   from app.db.session import SessionLocal
   from app.db.init_db import init_db
   from app.services.electricity_ingestion import ingest_electricity_dataset
   init_db()
   db = SessionLocal()
   summary = ingest_electricity_dataset(db, local_path=r'C:\data\electricity_hourly_dataset.tsf')
   print(summary)
   "
   ```
6. Compare the printed `series` count against the expected **321** and the frequency against **hourly** — if either differs from what's documented here, that's a genuine discrepancy worth reporting back, not something to silently reconcile.

### Running the 321→6 load-profile selection (after real ingestion)

Once the real dataset is ingested (§ above), run the shape-aware profiling/clustering pipeline against your real 321-series data:

```bash
python -c "
from app.db.session import SessionLocal
from app.services.load_profiling import run_profiling_pipeline
import json

db = SessionLocal()
summary = run_profiling_pipeline(db, persist=True)
print(json.dumps(summary, indent=2, default=str))
"
```

This is strictly read-only against `PublicLoadObservation` (verified by an automated test asserting the row count is identical before/after) and writes results only to `PublicLoadSeriesProfile`. The methodology is fully documented in `app/services/load_profiling.py`'s module docstring: weekday/weekend 24-hour median shapes (normalized by own mean), PCA reduction (≥90% variance retained, deterministic sign convention), block-balanced combination with CV/PAR, deterministic Ward hierarchical clustering at k=6, and selection of the real series nearest each cluster centroid. Re-running is idempotent (upserts, doesn't duplicate) and deterministic (same input → same six selected series every time).

**Note:** this pipeline has only been tested in this environment against small synthetic fixtures (see `tests/test_load_profiling.py`) with deliberately distinct, controllable patterns — not against the real 321-series data, which is only available in your environment. Please share the `summary` output (especially `selected_profiles` and `validation_checks`) after running it against the real data so it can be reviewed.

## Running with Docker

Two images, orchestrated by Compose:

| Service | Image | Port | Role |
|---|---|---|---|
| `backend` | `Dockerfile` (multi-stage, non-root) | 8000 | FastAPI + Uvicorn, SQLite on a named volume |
| `frontend` | `Dockerfile.frontend` (multi-stage) | 80 | Nginx serving the built SPA, proxying `/api` → backend |

```bash
npm run docker:up        # build if needed + start the stack  ← prefer this
npm run docker:logs      # tail container logs
npm run docker:ps        # container status
npm run docker:down      # stop (keeps the DB volume)
```

`npm run docker:up` runs `docker compose up -d --build`. A `Makefile` with the same targets (`make up`, `make logs`, …) is included for Unix/macOS users.

Open <http://localhost> and sign in with `ADMIN` / `4005` (or a tenant such as `T258` / `101`).

### ⚠️ `docker compose up -d` does not rebuild

This is the single most common way to get misled here:

```bash
docker compose up -d           # ❌ starts the *previously built* image
docker compose up -d --build   # ✅ rebuilds, then starts
```

If you edit source and run the bare `up -d`, Compose happily starts the **old** image and your changes appear to do nothing. Always use `npm run docker:up`, or pass `--build` explicitly. `npm run docker:rebuild` forces a `--no-cache` rebuild.

### First run: the dashboard is empty until you ingest

`scripts/seed_demo.py` only creates the estate, tenants and users — it does **not** ingest the 8.44M dataset. So a fresh volume shows `0 obs` / `0 profiles` and an empty centroid panel. That is expected, not a bug. Populate it with:

```bash
npm run docker:seed                    # (already runs automatically on boot)
make ingest                            # parse + ingest the mounted Zenodo .tsf
make profiles                          # run the 321→6 load-profile selection
```

Running a file under `scripts/` directly puts `scripts/` — not the project root — on `sys.path`, which breaks `import app`. Both scripts now insert the project root themselves (matching `scripts/train_tenant_models.py`), so `python scripts/seed_demo.py` works with no `PYTHONPATH` prefix.

### The dataset is mounted, not baked in

`data/electricity_hourly_dataset.tsf` (~36 MB) is deliberately **excluded** from the backend image so the image stays small and no third-party dataset ships inside it. Compose mounts it read-only:

```yaml
- ./data:/app/data:ro
```

and points `ELECTRICITY_DATASET_LOCAL_PATH` at the POSIX path `/app/data/electricity_hourly_dataset.tsf` (the `.env` value uses a Windows path, which cannot resolve inside a Linux container, so Compose overrides it). If you never ingest the dataset locally, delete that mount line and the now-empty `./data` directory.

### Hardening applied

- Backend runs as the non-root `solarshare` user, with `cap_drop: ALL` and `no-new-privileges`.
- Seeding is non-fatal (`|| echo …`): a seed failure no longer prevents the API from starting.
- The backend `CMD` uses `exec uvicorn`, so uvicorn is PID 1 and receives `SIGTERM` directly — otherwise `sh` stays PID 1, swallows the signal, and Docker has to `SIGKILL` after the grace period.
- `PYTHONUNBUFFERED=1` so `docker logs` streams live instead of block-buffering.
- The base images are pinned to specific minor versions (`python:3.11-slim`, `node:20-alpine`, `nginx:1.27-alpine`) rather than floating digests, so upstream security patches still land on rebuild. Pin by digest only if you need byte-reproducible builds.

Not hardened: `--forwarded-allow-ips` is left at uvicorn's default (`127.0.0.1`). Since nginx reaches the backend over the Docker bridge rather than loopback, `X-Forwarded-For` is effectively ignored — the safer default, but it means request logs show the proxy IP. Set it to the bridge subnet if you need real client IPs, and drop the `8000:8000` publish so the backend is reachable only through nginx.



- **Phase 1 (this phase):** foundational architecture — done, pending your review.
- **Phase 2+:** NASA POWER ingestion, public electricity dataset ingestion + tenant mapping, PV estimation, Prophet forecasting (solar + load), PuLP fair allocation, battery simulation, Tamil Nadu ToU billing engine, PDF invoicing, FastAPI domain endpoints, React frontend (Admin/Tenant dashboards), analytics, Docker/CI.

Each phase begins only on explicit instruction.
