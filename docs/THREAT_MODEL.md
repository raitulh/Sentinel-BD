# Threat Model and Security Checklist

## Assets

- User credentials and access tokens.
- Organization/site/device inventory.
- Uploaded video and evidence references.
- Event/review history and audit records.
- Database and media storage integrity.
- Model artifact/version and evaluation records.

## Trust boundaries

- Browser ↔ reverse proxy/API.
- API ↔ PostgreSQL.
- API ↔ media volume.
- Worker ↔ media volume/database.
- External source equipment ↔ any future device gateway.

## Main threats and controls

| Threat | Current control | Remaining work |
|---|---|---|
| Cross-tenant data disclosure | Organization scoping in queries; tests for events/media; global user identity | Broader row-level security and authorization audit |
| Credential stuffing | Sample Nginx login rate limit; generic login error | API-level distributed throttling, MFA/SSO, alerting |
| Secret leakage | Environment secrets; no credentials in repository | Use secret manager on hosted deployments and rotate keys |
| Malicious upload/path traversal | Extension/content-type checks, generated path, root containment, size limit | Malware scanning, stronger media probing, retention policy |
| Worker crash/stale job | Status tracking, attempts and stale-job recovery | Lease heartbeat, multi-worker load tests and idempotent transaction strategy |
| Unreviewed model output interpreted as truth | UI/API wording, score_kind and non-semantic metadata | User training, sign-off and independent evaluation |
| Unauthorized config changes | Role checks on core mutating operations; audit events | Security review for every future endpoint and object-level policy |
| Dependency vulnerabilities | Dependency/container scan in workflow | Actual scheduled scans, SBOM and patch SLA |
| Data loss | PostgreSQL volume and media volume persistence | Automated encrypted off-host backups and restore drills |
| Remote interception | Compose binds to localhost by default | TLS/reverse proxy/network/firewall before remote binding |

## Release gate

Do not use the prototype with sensitive operational footage until the deployment owner has completed a threat model, data classification, permission review, secure storage/retention policy, vulnerability testing, backup/restore rehearsal, incident-response runbook and customer-specific approvals.

## Explicit non-goals

No weapon control, targeting, active countermeasure, RF jamming, interceptor guidance or automated use-of-force decision is implemented.
