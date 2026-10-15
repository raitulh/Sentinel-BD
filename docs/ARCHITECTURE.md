# Architecture and Data Flow

## Boundaries

- **Web UI**: operator workflow; treats the API as source of truth. Session bearer is stored in `sessionStorage` for the browser session. This avoids long-lived storage but remains readable by same-origin JavaScript; deploy with reviewed web security controls and consider an HTTP-only BFF/session for higher assurance.
- **API**: auth, tenant scoping, schemas, device/site metadata, event/review APIs, uploads, audit trail and job state.
- **Worker**: consumes DB-backed queued video jobs, performs generic motion analysis, writes generated event records, records job success/failure.
- **PostgreSQL**: structured system-of-record. `organization_id` scoping is required on every tenant-owned query.
- **Media volume**: stores authorized uploaded files; DB holds only storage paths and metadata. Volume access is limited to API and worker services.

## Processing flow

1. An authenticated operator uploads a supported video.
2. API streams content from the upload object to a generated server filename while enforcing a configured maximum byte count. The original filename is stored as metadata only and never used as a path.
3. API creates a queued `processing_jobs` row.
4. A separate worker claims the oldest queued row under a DB transaction, marks it running, then releases the transaction before video processing.
5. OpenCV samples frames and runs a generic MOG2 foreground/background subtractor.
6. Motion observations become `motion_observed` events with a dedupe key, source job, model version and an explicit `semantic_classification=false` marker.
7. Operators can review events; review decisions and audit records are stored independently of AI output.

## Design choices

- Modular monolith first; a single API service plus a separate worker is sufficient for a small pilot.
- SQLite is only for local development/test convenience. PostgreSQL + Alembic is the production-like path.
- No cloud AI provider is called. Raw video is not sent to an external inference API.
- Core processing is designed to run on one on-prem server. External basemap tiles and cloud auth are not required by the current UI.
- `score` is paired with `score_kind`; the frontend never describes foreground ratio as calibrated probability.

## Data isolation

Each user belongs to one organization in this version. Every tenant-owned read/write is filtered by the authenticated user's `organization_id`. Global email uniqueness makes email-based login unambiguous. Audit logs are append-only from the application API, although the database administrator can still alter rows; stronger tamper evidence is future work.

## Current constraints

The DB queue uses a stale job timeout and supports basic crash recovery, but is not yet load-tested under multiple high-throughput workers or equipped with per-job heartbeat/lease ownership tokens. Media retention is manual. Device heartbeat endpoints record operator-entered metadata rather than verifying hardware identity. Hardware adapters, calibration and geospatial basemaps are future integration modules.
