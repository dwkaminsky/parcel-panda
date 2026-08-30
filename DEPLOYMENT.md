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
5. Collect required Prefect snapshots locally and review their manifests.
6. Publish reviewed snapshots to the intended database branch.
7. Verify the application locally.
8. Push the release commit and deploy it to Vercel.
9. Smoke-test the production homepage and API.

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
python -m pip install -r pipelines/requirements-dev.txt
deactivate
```

On Windows PowerShell:

```powershell
python -m venv pipelines/.venv
.\pipelines\.venv\Scripts\Activate.ps1
python -m pip install -r pipelines/requirements-dev.txt
deactivate
```

Do not install Pandas, GeoPandas, PyArrow, NumPy, Shapely, or other pipeline-only
packages into the root `.venv` or `requirements.txt`. Vercel installs only the
root requirements. Dedicated workers can install `pipelines/requirements.txt`;
the development file includes it and adds the test runner.

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

### Use an isolated branch for pipeline development

Create or select a Neon branch alongside each Git feature branch. Neon branches
are isolated copy-on-write database environments, so migrations and pipeline
writes on the child do not change its parent. `neon checkout` also pins the local
Neon context and pulls branch-scoped variables by default.

```bash
git switch -c feature/example
neon branch create --name dev-feature-example --parent production
neon checkout dev-feature-example
neon status
```

Keep `.env.local` pointed at that child while developing. If you obtain URLs
with `neon connection-string`, put the pooled child URL in `DATABASE_URL` and the
direct child URL in `DATABASE_URL_DIRECT`. Do not run a feature migration or a
snapshot publisher against `production` merely because the code is on a local
feature branch. Before merging a schema change, run `neon diff` and review the
child-to-parent schema difference.

Neon's environment pull may name the direct URL `DATABASE_URL_UNPOOLED`. This
repository uses the equivalent name `DATABASE_URL_DIRECT`, so copy the pulled
direct value to that key before running Alembic or a write pipeline.

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

Apply migrations before the first snapshot publication. The publisher writes to
the catalog, source provenance, ingestion run, and normalized record tables, so
running it against an older schema will fail. For a feature branch, use this
order:

1. `neon checkout` the isolated child and load its pooled/direct URLs.
2. Inspect the migration and run `alembic upgrade head` with
   `DATABASE_URL_DIRECT`.
3. Collect a bounded local snapshot and inspect its manifest.
4. Publish that exact snapshot against the child branch.
5. Inspect `neon diff`, application behavior, and the ingestion summary.
6. Only then apply the same reviewed migration to production, deploy compatible
   application code, and publish the reviewed snapshot to production.

Migrations use the direct URL because schema tools rely on session behavior that
is not guaranteed through PgBouncer's transaction pool. The web application
continues to use the pooled URL.

## Run the data pipeline

Pipeline jobs run on a workstation or dedicated worker, never inside the Vercel
web runtime. Prefect uses separate flows for source collection and database
publishing. Collection has no database code path; publishing never calls an
upstream source.

```bash
source pipelines/.venv/bin/activate
set -a
source .env.local
set +a

# Collect the default public starter set into pipelines/data/runs.
python -m pipelines collect

# Select one or more datasets and bound every source request.
python -m pipelines collect \
  --dataset parcel-records \
  --dataset property-tax \
  --county-fips 37183 \
  --limit 100

# Review the timestamped directory and checksummed manifest first.
python -m pipelines publish pipelines/data/runs/20260830T180000Z-ab12cd34
```

`--dataset` is repeatable. A three-digit NC county code is normalized to its
five-digit FIPS code, so `183` and `37183` both select Wake County. The record
limit must be between 1 and 5000. Raw source payload retention is enabled for
provenance by default; add `--no-raw-payloads` to retain only normalized records
and content hashes. Run `python -m pipelines collect --help` for collection
options and `python -m pipelines publish --help` for publishing.

`collect` writes only local compressed JSON Lines files plus `manifest.json`.
The manifest preserves source versions, retrieval times, warnings, skip reasons,
record counts, collection options, and SHA-256 checksums. `publish` verifies the
entire snapshot before opening `DATABASE_URL_DIRECT`; corrupt or incomplete
snapshots fail before any database mutation. Repeating publication is idempotent:
source keys and content hashes prevent identical records from being loaded again,
and each publication records an ingestion summary. Collection still calls
upstream sources and may consume licensed API quota, so use a small `--limit`
during development.

Local snapshots may contain personally identifying ownership data or licensed
provider payloads. `pipelines/data/` is git-ignored, but operators must still
protect, retain, and delete snapshots according to source terms and local policy.

### Pipeline credentials

Copy the committed template and fill secrets only in ignored local or worker
environment configuration:

```dotenv
DATABASE_URL="postgresql://...-pooler.../neondb?sslmode=require"
DATABASE_URL_DIRECT="postgresql://.../neondb?sslmode=require"
CENSUS_API_KEY="..."
RENTCAST_API_KEY="..."
```

- `DATABASE_URL_DIRECT` is required only for snapshot publishing and must target the
  intended Neon branch without `-pooler` in its hostname.
- `CENSUS_API_KEY` authenticates Census API requests and provides practical
  request capacity for ACS ingestion.
- `RENTCAST_API_KEY` is required for licensed active sale and rental listing
  endpoints. Provider usage limits and license terms still apply.

Do not put source credentials or the direct database URL in Vercel's browser
environment. A scheduler or Prefect worker should inject them as secrets when
pipeline runs move beyond local execution.

### Source limitations

The adapters preserve citations and provenance, but they cannot make unlike
government and commercial sources uniform at extraction time:

| Source family | Important boundary |
| --- | --- |
| NC OneMap parcels | County participation, field names, completeness, geometry, and refresh timing vary. Assessed values are county-provided snapshots, not a statewide real-time tax ledger. |
| NCDOR property-tax reports | Published reports provide tax context and aggregates; they do not replace county parcel bills or payment records. |
| Census ACS 5-year | Values are estimates for Census geographies, not property-level facts, and should be interpreted with their geography, vintage, and margins of error. |
| CFPB / New York Fed mortgage data | Delinquency and balance measures are aggregated and cannot identify a property's mortgage, borrower, or current loan status. |
| NC flood layers | Mapped flood zones and elevation layers are planning data, not a survey, insurance determination, or guarantee of present risk. |
| Municipal zoning | Coverage is municipality-specific; the initial Charlotte source should not be treated as statewide zoning. |
| RentCast listings | Requires a licensed key and is subject to provider coverage, quotas, freshness, and downstream-use terms. A missing listing is not proof that a property is off market. |

Source endpoints can change or temporarily fail. A successful flow means the
adapter processed the source response it received; it does not certify that the
publisher's underlying data is complete or current.

## Verify before deployment

Run the static and build checks:

```bash
npm run lint
npm run build
.venv/bin/python -m compileall -q api backend pipelines
.venv/bin/python -m pip check
pipelines/.venv/bin/python -m pip check
pipelines/.venv/bin/python -m pytest tests/pipelines
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

## Create a Preview deployment

Vercel automatically creates a Preview deployment for pushes to non-production
Git branches and for pull requests. The Preview receives a unique URL and does
not replace `parcel-panda.vercel.app`.

```bash
git switch -c preview/property-cards
git push -u origin preview/property-cards
```

Optionally open a pull request:

```bash
gh pr create
```

The Vercel URL appears in the GitHub checks and Vercel bot comment. Every new push
to the branch updates that Preview.

### Isolate Preview data

Do not point a writable Preview deployment at the production Neon branch. For
this existing Neon account, the recommended automated option is the
[Neon-managed Vercel integration](https://neon.com/docs/guides/neon-managed-vercel-integration),
which provisions Neon branches for Vercel previews and injects their environment
variables.

For a manual branch-specific setup, create and select a Neon branch:

```bash
neon checkout preview-property-cards
neon connection-string preview-property-cards --pooled --ssl require
neon connection-string preview-property-cards --ssl require
```

Use the first command's pooled URL as a branch-specific Vercel Preview variable:

```bash
vercel env add DATABASE_URL preview \
  --git-branch preview/property-cards
```

Keep the second, direct URL in local `DATABASE_URL_DIRECT`, apply migrations to
the Neon Preview branch, and run any Preview seed pipeline before testing:

```bash
source .venv/bin/activate
set -a
source .env.local
set +a
alembic upgrade head

source pipelines/.venv/bin/activate
python -m pipelines collect --limit 100
python -m pipelines publish pipelines/data/runs/<reviewed-snapshot>
```

Check both hostnames before running those commands: the Vercel value must contain
`-pooler`, while the local migration and pipeline value must not. After Preview
work, switch the Neon CLI back to production deliberately:

```bash
neon checkout production
```

For a one-off Preview from the linked local checkout, deploy without `--prod`:

```bash
vercel deploy
```

`vercel deploy --prod` is intentionally different and updates production. See
[Vercel environments](https://vercel.com/docs/deployments/environments) and the
[Neon–Vercel integration guide](https://neon.com/docs/guides/vercel-overview) for
the managed Preview-branch options.

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
5. Collect required snapshots, review their manifests, then publish those exact
   snapshots with `DATABASE_URL_DIRECT`.
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

### Snapshot publishing targets the wrong data

Stop the flow and inspect `neon status`, `.neon`, and the hostnames loaded from
`.env.local`. Git and Neon branches are independent; switching Git branches does
not switch the database. Run `neon checkout <expected-branch>` and reload the
environment before retrying. Collection remains safe because it never reads a
database URL; publishing should start only after the branch check is complete.

### A licensed or keyed dataset is skipped

Confirm the adapter's credential variable is present in the same process that
runs `python -m pipelines collect`. Census reads `CENSUS_API_KEY`; RentCast reads
`RENTCAST_API_KEY`. A key can still be rejected because of provider quotas,
subscription scope, or expiration.
