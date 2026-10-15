# Deployment Guide

## Local / lab deployment

Use Docker Compose on a single Linux server or workstation. The default external bind is `127.0.0.1:8080`; this reduces accidental exposure. PostgreSQL is not published on the host. The API and worker share `media_data`; the web UI calls the same-origin `/api/v1` route through Nginx.

## Before remote access

1. Set `APP_ENV=production`; the API then hides interactive documentation and refuses development secret defaults.
2. Replace `SECRET_KEY`, `BOOTSTRAP_TOKEN` and database password with unique randomly generated values. Do not commit `.env`.
3. If the database password is embedded in `DATABASE_URL`, URI-encode reserved characters or use an alphanumeric hex password.
4. Configure a domain and TLS. Put a managed TLS reverse proxy in front of the local service, or provide reviewed TLS settings in Nginx. Do not expose the current HTTP-only port directly to the public Internet.
5. Update `CORS_ORIGINS` and `NEXT_PUBLIC_API_BASE_URL` to match the final origin, rebuild the web image, and test login/logout in a browser.
6. Configure encrypted off-host backup for PostgreSQL and media, then prove that restore works.
7. Establish a media retention and secure deletion schedule; v0.1 does not automatically purge uploaded files.
8. Review authentication, RBAC, dependency vulnerability scan, audit logging, disk monitoring, alerting and incident response.
9. Apply Alembic migrations on a staging copy before any production migration. Keep a tested backup and rollback plan.
10. Validate all requirements specific to the customer, camera/device and intended use before a pilot.

## Configuration variables

| Variable | Required / default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Use `production` for deployment hardening/docs disabled |
| `SECRET_KEY` | Development default only outside production | HMAC signing key, 32+ random chars in production |
| `BOOTSTRAP_TOKEN` | Empty unless set | Enables one-time first-admin bootstrap |
| `DATABASE_URL` | SQLite development | SQLAlchemy connection URL; Compose provides PostgreSQL |
| `MEDIA_ROOT` | `./data/media` | Root for uploaded videos; API and worker must share it |
| `MAX_UPLOAD_BYTES` | `209715200` | Upload limit (200 MiB by default) |
| `CORS_ORIGINS` | localhost entries | Explicit allowed browser origins; no wildcard in production |
| `VIDEO_FRAME_STRIDE` | `5` | Process one frame every N decoded frames |
| `VIDEO_MOTION_THRESHOLD` | `0.08` | Foreground ratio threshold for generic motion observations |
| `VIDEO_MIN_GAP_SECONDS` | `2.0` | Minimum time between consecutive motion events |
| `MAX_VIDEO_DURATION_SECONDS` | `3600` | Reject video uploads longer than this duration during processing |
| `MAX_VIDEO_FRAMES` | `100000` | Reject videos whose reported/decoded frame count exceeds this processing limit |
| `WORKER_POLL_SECONDS` | `2.0` | Delay between empty queue polls |
| `JOB_STALE_MINUTES` | `180` | Lease timeout after which a running job is recovered |
| `MAX_JOB_ATTEMPTS` | `3` | Maximum automatic/manual attempts before investigation |
| `HTTP_BIND_ADDRESS` | `127.0.0.1` | Host bind address for Nginx service |

## Upgrade and rollback

- Review the migration diff before release.
- Back up the database and media before upgrading.
- Apply migrations from the backend image (`alembic upgrade head`).
- Deploy a versioned image and verify `/health/ready`, login, event list, upload and worker processing.
- If rollback is required, return to the previous application image. Database downgrade should only occur if the migration author has verified the downgrade path on a copy; prefer a forward repair migration for data-affecting changes.
