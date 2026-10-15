# Engineering Roadmap after v0.1.0

## v0.2 — Reliability & identity

- Add API-level login throttling in addition to reverse-proxy limits.
- Add account disable/reset flows, invitation audit and MFA/OIDC option.
- Add job lease heartbeats, retention/purge tooling with explicit dry-run, and queue integration tests across multiple workers.
- Add PostgreSQL integration tests in CI and browser E2E using Playwright.
- Add request metrics, structured JSON logs, versioned health status and safer exception correlation IDs.

## v0.3 — Site/device integration SDK

- Specify stable, versioned `DeviceAdapter` interface and manifest schema.
- Add read-only adapter for an authorized commercial camera/telemetry interface after protocol and credential review.
- Add authenticated device identities, replay protection and per-device permissions; operator-entered heartbeat must not stand in for device authentication.
- Add calibration/configuration records, device firmware/version inventory and test harness.

## v0.4 — ML governance

- Dataset manifests with source/license, annotation guidelines and version hashes.
- Train/validation/test split validation to prevent near-duplicate leakage.
- MLflow experiment logs and model-card generation.
- Per-class metrics, calibration checks, environmental error slices and release acceptance thresholds.
- Signed model artifacts, rollback, model drift alerts and human feedback curation.

## v0.5 — Pilot readiness

- On-prem installer and signed update packages.
- Customer data classification, retention configuration, restore drills, security assessment and audit/export controls.
- Hardware-integration bench, device compatibility matrix, acceptance report templates and support SLAs.
- Customer-specific operational acceptance and regulatory review before any production usage.

## Not in the roadmap by default

Autonomous weapon control, interceptor guidance, targeting or active jamming are not part of this software roadmap.
