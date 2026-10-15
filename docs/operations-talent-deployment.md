# Operations and Talent deployment

Source: aetheric-forge/aetheric-web#55, merged as
`0d4abddaf2857a5ac1c72f0cabb5f1790535e03e`.

Image: `ghcr.io/aetheric-forge/aethericforge-web:sha-0d4abdd@sha256:68f6bb80d81a6c665fa7937a4b96ec57ecc620200613e85c5c2f4a1cb121edfe`.
The published platform is linux/amd64.

This release changes only the web image. Full-campus mode, module pins, consumer
Secrets, campus credentials, storage mounts, and worker/admin images stay as configured.
Keep one web writer replica: runtime Warden/Sentinel catalog updates coordinate within
one process. Their Operations ledger now uses the existing Redis-backed owner stage,
under `operations/ledger-v1/`, without expiration. Redis persistence and backups remain
responsible for storage durability. Existing in-memory Operations records are not migrated;
the prior web screens were placeholders.

Administrator routes:

- `/operations`, `/operations/issue-reports`, `/operations/security`.
- Existing `/campus/admin/issue-reports` and `/campus/admin/security` aliases.
- `/talent`, `/talent/roles`, `/talent/personas`, `/talent/recruitment`.

Talent remains under Design using its scoped Mongo providers. Operations retains
Issue Reports and Security under its existing faculty. Recruitment saves consideration
snapshots; it does not deliver them to Decisions yet. Ordinary users are denied access
by the existing campus administrator policy. Anonymous requests challenge through SSO.

Validation: source CI green (59 web tests, 7 marketing tests). The built image started
in isolated public mode; homepage/projects returned 200 and all nine campus workspace
paths/aliases returned 404. Production Kustomize output passed server-side dry-run.
Post-rollout checks verify readiness, exact image, campus ownership, public pages/assets,
and SSO challenges for workspace routes. These checks do not submit workflow records or
use a human-account login.

Rollback by reverting this release's image change to:
`ghcr.io/aetheric-forge/aethericforge-web:sha-2ca4ac7@sha256:651056106c746b69e763061365170aff3f1e94ac2613b48cc0b91b5a73e24931`.
Retain the campus configuration, Secrets, volume claims, and any newly persisted records.
