# Parcel Panda

Parcel Panda is a real-estate data application that combines a Next.js frontend,
a FastAPI backend, and Neon Postgres in one Vercel deployment. A separate Python
pipeline environment handles heavyweight geospatial and data-processing work
without adding those dependencies to the deployed application.

Live application: [parcel-panda.vercel.app](https://parcel-panda.vercel.app/)

## Architecture

```mermaid
flowchart LR
    Browser[Browser] -->|GET /| Next[Next.js]
    Browser -->|GET /api/*| API[FastAPI on Vercel]
    API -->|pooled DATABASE_URL| Neon[(Neon Postgres)]
    Sources[Public and licensed sources] --> Collect[Prefect collect flow]
    Collect --> Snapshot[Checksummed local snapshot]
    Snapshot --> Publish[Prefect publish flow]
    Publish -->|direct DATABASE_URL_DIRECT| Neon
    Alembic[Alembic migrations] -->|direct DATABASE_URL_DIRECT| Neon
```

Vercel serves both runtimes from one domain:

- `/` is rendered by Next.js.
- `/api/health` and `/api/properties` are handled by FastAPI.
- `vercel.json` rewrites `/api/*` requests to the Python entrypoint.
- FastAPI reads application data from Neon through its pooled endpoint.
- Only Alembic and the snapshot publisher connect directly to Neon.

### Database connections

| Variable | Connection | Used by |
| --- | --- | --- |
| `DATABASE_URL` | Neon pooled endpoint (`-pooler`) | FastAPI and Vercel request traffic |
| `DATABASE_URL_DIRECT` | Neon direct endpoint | Alembic migrations and snapshot publishing |

SQLAlchemy uses Psycopg 3 and `NullPool` in the web application. Neon/PgBouncer
provides the shared connection pool, so ephemeral Vercel processes do not retain
their own persistent SQLAlchemy pools.

## Repository layout

```text
parcel-panda/
├── app/                       # Next.js App Router frontend
├── api/
│   └── index.py               # FastAPI/Vercel entrypoint
├── backend/
│   ├── database.py            # SQLAlchemy engine and sessions
│   ├── models.py              # Property model
│   ├── schemas.py             # API response schemas
│   └── routes/                # FastAPI route modules
├── alembic/                   # Database migrations
├── pipelines/
│   ├── __main__.py            # Collect/publish command-line interface
│   ├── flow.py                # Separate Prefect collection and publishing flows
│   ├── catalog.py             # Dataset and source registry
│   ├── contracts.py           # Normalized ingestion records
│   ├── local_snapshot.py      # Checksummed local snapshot storage
│   ├── requirements.txt       # Heavy data/geospatial dependencies
│   └── sources/               # Source adapters and pure normalization helpers
├── neon.ts                    # Neon branch and service policy
├── requirements.txt           # Lightweight Vercel Python dependencies
└── vercel.json                # Same-domain API routing
```

The root Python environment stays intentionally small. Packages such as Pandas,
GeoPandas, PyArrow, NumPy, and Shapely live only in `pipelines/.venv` and are not
installed in the Vercel runtime.

## Data pipelines

The catalog pipelines run outside Vercel and use Prefect for orchestration,
retries, and observable task/flow runs. Collection and publishing are separate:
`collect` fetches and normalizes sources into an ignored, checksummed local
snapshot, while `publish` verifies a completed snapshot before connecting to
Postgres. Content hashes and database constraints make repeated publication
idempotent.

Install the pipeline environment, copy `.env.example` to the ignored
`.env.local`, and load its values:

```bash
python3 -m venv pipelines/.venv
source pipelines/.venv/bin/activate
python -m pip install -r pipelines/requirements-dev.txt
set -a
source .env.local
set +a
```

Collection never connects to Postgres:

```bash
# Collect the default public starter set locally.
python -m pipelines collect

# Collect selected Wake County datasets into a timestamped snapshot.
python -m pipelines collect \
  --dataset parcel-records \
  --dataset housing-demographics \
  --county-fips 37183 \
  --limit 100

# Publish only after reviewing the generated manifest and database target.
python -m pipelines publish pipelines/data/runs/20260830T180000Z-ab12cd34
```

Each snapshot contains `manifest.json` plus one compressed JSON Lines file per
source. The manifest records collection options, counts, source versions,
warnings, skip reasons, and SHA-256 checksums. Local snapshots can contain owner
names or licensed source payloads, so `pipelines/data/` is git-ignored and should
be handled as sensitive data.

Use `--no-raw-payloads` when source payload retention is unnecessary. Run
`python -m pipelines collect --help` for every dataset slug and option.
Publishing is the only command that needs `DATABASE_URL_DIRECT`; Census and
RentCast collection read `CENSUS_API_KEY` and `RENTCAST_API_KEY`, respectively.
Never expose those values to the Next.js client or commit them.

The catalog is transparent about source boundaries: county parcel schemas and
update schedules vary, municipal zoning is not statewide, flood layers describe
mapped hazards rather than property-specific risk, mortgage data is aggregated
rather than loan-level, and licensed listing coverage depends on the provider.
Absence from a source is not proof that a property or condition does not exist.

## Deployment and operations

See [DEPLOYMENT.md](./DEPLOYMENT.md) for complete instructions covering local
environments, Neon configuration, migrations, pipeline execution, Vercel setup,
production deployment, and smoke testing.

## API

### `GET /api/health`

Returns basic service health:

```json
{
  "status": "ok",
  "service": "parcel-panda-api"
}
```

### `GET /api/properties`

Returns the properties currently stored in Neon. FastAPI's generated OpenAPI and
Swagger documentation is available at `/docs` when the Python application is run
directly.
