# Parcel Panda deployment guide

This guide covers the complete path from a fresh clone to a verified production
deployment. Run commands from the repository root unless a section says otherwise.

Production URL: [parcel-panda.vercel.app](https://parcel-panda.vercel.app/)

## Deployment order

Use this order for a new environment or release:

1. Install the frontend, web-backend, and pipeline dependencies.
2. Link the repository to the correct Neon organization, project, and branch.
3. Configure the pooled and direct database URLs.
4. Apply Alembic migrations with the direct URL.
5. Run any required pipeline jobs with the direct URL.
6. Verify the application locally.
7. Push the release commit and deploy it to Vercel.
8. Smoke-test the production homepage and API.

Database migrations must be compatible with both the currently deployed app and
the release being deployed. For breaking schema changes, use an expand-and-contract
migration sequence instead of removing old columns in the same release.

## Prerequisites

Install:

- Git and a GitHub account with access to `dwkaminsky/parcel-panda`
- Node.js and npm
- Python 3
- Neon CLI
- Vercel CLI

```bash
npm install -g neon vercel
neon --version
vercel --version
```

Authenticate both CLIs once per machine:

```bash
neon auth
vercel login
```

## Clone and install

```bash
git clone https://github.com/dwkaminsky/parcel-panda.git
cd parcel-panda
npm install
```

Create the lightweight Python environment used by FastAPI and Alembic:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate it with:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create the separate heavyweight pipeline environment:

```bash
python3 -m venv pipelines/.venv
source pipelines/.venv/bin/activate
python -m pip install -r pipelines/requirements.txt
deactivate
```

On Windows PowerShell:

```powershell
python -m venv pipelines/.venv
.\pipelines\.venv\Scripts\Activate.ps1
python -m pip install -r pipelines/requirements.txt
deactivate
```

Do not install Pandas, GeoPandas, PyArrow, NumPy, Shapely, or other pipeline-only
packages into the root `.venv` or `requirements.txt`. Vercel installs only the
root requirements.

## Configure Neon

Parcel Panda currently uses:

- Organization: `Danny` (`org-fragrant-sky-87717547`)
- Project: `parcel-panda` (`little-hall-78815749`)
- Production branch: `production`
- Region: `aws-us-east-2`

Link the checkout and verify its live configuration:

```bash
neon link \
  --org-id org-fragrant-sky-87717547 \
  --project-id little-hall-78815749 \
  --branch production \
  -y

neon status
neon config plan
```

`neon.ts` currently declares Postgres as the only utilized Neon service. A clean
plan should report no service changes.

### Configure local database URLs

Create the ignored local file from the committed template:

```bash
cp .env.example .env.local
```

Get both connection strings:

```bash
neon connection-string production --pooled --ssl require
neon connection-string production --ssl require
```

Copy them into `.env.local`:

```dotenv
DATABASE_URL="postgresql://...-pooler.../neondb?sslmode=require"
DATABASE_URL_DIRECT="postgresql://.../neondb?sslmode=require"
```

The host in `DATABASE_URL` must contain `-pooler`. The host in
`DATABASE_URL_DIRECT` must not. FastAPI uses the pooled URL; Alembic and pipeline
jobs use the direct URL.

Never commit `.env.local`, `.env`, `.neon`, `.vercel`, or either virtual
environment. Confirm the ignore rules before continuing:

```bash
git check-ignore .env.local .neon .vercel .venv pipelines/.venv
```

## Apply database migrations

Activate the lightweight environment and export the local variables:

```bash
source .venv/bin/activate
set -a
source .env.local
set +a
```

Check the current revision, inspect pending SQL, and migrate:

```bash
alembic current
alembic upgrade head --sql
alembic upgrade head
alembic current
```

For a schema change, edit the SQLAlchemy models and generate a revision:

```bash
alembic revision --autogenerate -m "describe schema change"
```

Always inspect a generated revision before applying it. It should change only
application-owned objects. `alembic/env.py` excludes PostGIS's
extension-managed `spatial_ref_sys` table from autogeneration comparisons.

On Windows PowerShell, load the two values explicitly before running Alembic:

```powershell
$env:DATABASE_URL = "postgresql://...-pooler..."
$env:DATABASE_URL_DIRECT = "postgresql://..."
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

## Run the data pipeline

Pipeline jobs run on the workstation or gaming PC, never inside the Vercel web
runtime. The starter job performs an idempotent upsert of the fake Raleigh parcel
`TEST-0001`.

```bash
source pipelines/.venv/bin/activate
python pipelines/ingest_properties.py
deactivate
```

The script loads `DATABASE_URL_DIRECT` from `.env.local`. Rerunning it updates the
existing parcel rather than creating a duplicate.

## Verify before deployment

Run the static and build checks:

```bash
npm run lint
npm run build
.venv/bin/python -m compileall -q api backend pipelines/ingest_properties.py
.venv/bin/python -m pip check
pipelines/.venv/bin/python -m pip check
git diff --check
```

### Run FastAPI directly

With the variables still exported from `.env.local`:

```bash
source .venv/bin/activate
uvicorn api.index:app --reload
```

Verify:

- `http://localhost:8000/api/health`
- `http://localhost:8000/api/properties`
- `http://localhost:8000/docs`

### Run the combined Vercel environment

Link the checkout to the existing Vercel project:

```bash
vercel link --project parcel-panda
```

Add `DATABASE_URL` to Vercel's Development environment or configure it in the
Vercel dashboard. Do not add `DATABASE_URL_DIRECT` to the web runtime; migrations
and pipelines run outside Vercel.

```bash
vercel env add DATABASE_URL development
vercel dev
```

Verify the combined application:

- `http://localhost:3000/`
- `http://localhost:3000/api/health`
- `http://localhost:3000/api/properties`

## Configure Vercel production

The Vercel project must have the pooled `DATABASE_URL` configured for Production.
Add it through Project Settings or the CLI:

```bash
vercel env add DATABASE_URL production
```

Use the pooled Neon value whose hostname contains `-pooler`. Do not configure the
direct migration URL in Vercel.

The committed `vercel.json` routes `/api/*` to `api/index.py`, while Next.js owns
the rest of the domain. The root `requirements.txt` controls the Python function
dependencies.

## Commit and deploy

Confirm no secrets are tracked:

```bash
git status
git ls-files | grep env
```

The tracked env-file output should contain only `.env.example`.

Commit and push:

```bash
git add .
git commit -m "Describe the release"
git push origin main
```

The connected GitHub repository automatically starts a production Vercel
deployment from `main`. Alternatively, deploy the linked checkout explicitly:

```bash
vercel deploy --prod
```

Wait until Vercel reports the deployment as `Ready` and confirms that
`parcel-panda.vercel.app` points to it.

## Production smoke test

```bash
curl --fail https://parcel-panda.vercel.app/
curl --fail https://parcel-panda.vercel.app/api/health
curl --fail https://parcel-panda.vercel.app/api/properties
```

Expected health payload:

```json
{
  "status": "ok",
  "service": "parcel-panda-api"
}
```

Also verify in a browser:

- The Parcel Panda title, favicon, hero, and property cards render.
- The browser console has no unexpected errors.
- The Raleigh test property appears when it exists in the selected Neon branch.

## Routine release checklist

1. Pull `main` and create a feature branch.
2. If the schema changes, generate and inspect an Alembic revision.
3. Run lint, build, Python compilation, and dependency checks.
4. Apply backward-compatible migrations with `DATABASE_URL_DIRECT`.
5. Run required pipeline jobs with `DATABASE_URL_DIRECT`.
6. Merge or push the release commit to `main`.
7. Wait for the production deployment to become `Ready`.
8. Run the production smoke test.
9. Confirm `.env.example` is still the only tracked env file.

## Common failures

### `KeyError: 'DATABASE_URL'`

The FastAPI process did not receive its pooled URL. Export `.env.local` for direct
Uvicorn use, or configure `DATABASE_URL` in the relevant Vercel environment.

### Alembic connects through `-pooler`

Stop before migrating. `DATABASE_URL_DIRECT` must use the direct hostname without
`-pooler`.

### `/api/*` returns a Next.js 404

Confirm `vercel.json` is deployed and rewrites `/api/:path*` to `/api/index`.
Use `vercel dev`, not `next dev`, when testing combined Next.js/Python routing.

### Pipeline packages appear in the Vercel build

Confirm heavy dependencies exist only in `pipelines/requirements.txt` and that
the root `requirements.txt` remains the lightweight FastAPI runtime.
