# Verification Report — Sentinel BD v0.1.0

**Verification date:** 2026-10-14 (artifact-building environment)

This report records checks actually performed while preparing this source bundle. It is not a certification or claim of operational defence readiness.

## Checks completed

- **Backend automated tests:** 56 tests passed in 15.96 seconds with Python 3.13.5, pytest 9.0.2, FastAPI TestClient/HTTPX, SQLAlchemy 2 and isolated in-memory SQLite databases. The final command returned exit code 0.
- **Python syntax/bytecode compilation:** `python -m compileall -q app tests scripts migrations` passed.
- **Alembic migration smoke test:** created an isolated SQLite database, ran `alembic upgrade head`, then `alembic check`; result: `No new upgrade operations detected.` The temporary database was removed.
- **Frontend TS/TSX syntax parse:** 12 TypeScript/TSX source files parsed with the globally available TypeScript transpiler; zero syntax diagnostics.
- **Frontend config syntax:** `node --check` passed for `apps/web/eslint.config.mjs` and `apps/web/postcss.config.mjs`.

## Tests represented in the 56-test backend suite

- Health/liveness and standard security response headers.
- One-time admin bootstrap, bootstrap token, password policy and password hashing.
- Login success/failure, inactive users, malformed/expired/tampered/wrong-secret tokens.
- Production secret/database configuration validation.
- Role restrictions, admin user management, last-admin protection and audit-log access control.
- Event creation/list/filter/pagination, input ranges, UTC normalization, review history and cross-organization isolation.
- Site coordinates, device registration, site tenancy, heartbeat permissions and duplicate constraints.
- Upload extension/content-type/empty/size rejection, tenant-scoped media access, upload queueing, synthetic AVI processing, generic-motion output, duration/frame limits, invalid-video failure, retry limits and stale-job recovery.

## Checks not completed in this environment

- **Next.js production build, TypeScript type-check and ESLint:** not run. The environment could not resolve `registry.npmjs.org` (`EAI_AGAIN`), so NPM dependencies were unavailable. Syntax parsing alone is not a substitute for type-checking or a production build.
- **PostgreSQL integration/concurrency:** not run; backend tests use SQLite. Test against PostgreSQL before production.
- **Docker image build / Compose startup:** not run because Docker/Podman binaries were unavailable here.
- **Browser end-to-end testing:** not run in an actual browser.
- **Coverage report / Ruff:** not generated; Ruff was not installed in this environment. Run the documented checks in a provisioned development/CI environment.
- **Hardware tests, performance qualification, penetration test, independent security review and regulatory certification:** not performed.

## Release caution

A passing test suite is not a production security certification. This is a production-oriented pilot foundation that still requires an online frontend build, PostgreSQL-backed integration tests, real-browser tests, deployment review, secrets/TLS/backups configuration, privacy review and independent security testing before handling sensitive data or being used in a real operational environment.
