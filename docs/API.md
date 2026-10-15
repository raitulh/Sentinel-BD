# API Guide (v1)

Base URL in local Compose: `http://localhost:8080/api/v1`. Protected routes use `Authorization: Bearer <access_token>`.

## Initial setup and login

`POST /auth/bootstrap` (first account only):

```http
X-Bootstrap-Token: <value from BOOTSTRAP_TOKEN>
Content-Type: application/json
```

```json
{
  "organization_name": "Sentinel Lab",
  "email": "admin@example.org",
  "password": "at-least-12-characters"
}
```

Returns a short-lived access token and public user object. Bootstrap is disabled once any account exists. `POST /auth/login` takes `email` and `password` and intentionally uses a generic invalid-credentials response.

## Create/list events

`POST /events` (admin, operator, reviewer):

```json
{
  "source_id": "camera-lab-01",
  "event_type": "sample_observation",
  "observed_at": "2026-10-14T12:15:00Z",
  "score": 0.42,
  "score_kind": "demo_score_not_probability",
  "details": { "synthetic": true, "note": "not a real detection" }
}
```

`GET /events?limit=50&offset=0&review_status=unreviewed&event_type=sample_observation` returns `items`, `total`, `limit` and `offset`. Limits and offsets are bounded; maximum `limit` is 200.

## Device and site inventory

- `POST /sites` body: `{ "name": "Test site", "description": "Optional" }`. Latitude and longitude must either both be provided or both omitted.
- `POST /devices` body: `{ "name": "Camera 01", "device_type": "camera", "site_id": null, "details": { "vendor": "example" } }`.
- `POST /devices/{id}/heartbeat` is an operator/admin metadata endpoint. In v0.1 a heartbeat from the web UI is not cryptographic proof of a device-originated signal; production device identity must be provisioned and authenticated separately.

## Human event reviews

`POST /events/{id}/reviews` (admin, operator, reviewer):

```json
{
  "decision": "needs_follow_up",
  "note": "Check source footage manually; model output is inconclusive."
}
```

Supported decisions: `confirmed`, `false_positive`, `not_actionable`, `needs_follow_up`. The event review status changes to `reviewed` after the first saved review; the decision history remains in `event_reviews`.

## Video motion scan

`POST /analysis/jobs` is multipart form data with field `file`, accepted extensions `.mp4`, `.avi`, `.mov`, `.mkv`; optional `site_id` is a query parameter. API upload size defaults to 200 MiB. The API stores the upload under the configured media root and returns `202 Accepted` with status `queued`. The separate worker processes jobs.

A successful result contains `analysis_type: generic_video_motion_scan`, `motion_events_created`, and `model_version: opencv-mog2-motion-v1`. Each resulting event has `event_type: motion_observed`, `score_kind: foreground_pixel_ratio` and `details.semantic_classification: false`. This reports coarse movement in frames only—not object identity, hostility, or threat probability.

Failed jobs can be retried by admins/operators up to the configured attempt limit. Media download is scoped to the authenticated user's organization.

## Role matrix

| Action | Admin | Operator | Reviewer | Viewer | Auditor |
|---|---:|---:|---:|---:|---:|
| Read events/devices/sites/jobs | Yes | Yes | Yes | Yes | Yes |
| Create event | Yes | Yes | Yes | No | No |
| Create site/device | Yes | Yes | No | No | No |
| Heartbeat metadata | Yes | Yes | No | No | No |
| Save event review | Yes | Yes | Yes | No | No |
| User list/create | Yes | No | No | No | No |
| Audit logs | Yes | No | No | No | Yes |
| Retry job | Yes | Yes | No | No | No |
