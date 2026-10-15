# Administration Decisions deployment

The new organization is `administration-decisions`; its production deployment ID is
`acd89aae84c4757e04128aa135bd5fbddaa609396ef4fbbec1646f99e0b1023f`.
Its selected existing owner is Administration:
`585a1b4fc7d725844c4a1b82f51412f5b372acbf182bac9edb0072bffcdd24a5`.
The parent campus supplies Library, Archive, Post Office and Workbench; University
supplies Registry. The former Decisions catalog entry and workspace are retained.

The worker verified parent Library/Workbench capabilities and delivered the new
consumer to `aethericforge-decisions-consumer-v1`. This versioned Secret allowed
provisioning and candidate checks while the old public web still mounted its empty
`aethericforge-decisions-consumer` slot. Worker RBAC and Argo data exclusions cover
the new slot.

`aethericforge-web-campus-v1` is an operator-managed prerequisite Secret, created
without storing plaintext credentials in Git or local files. It contains:

- Scoped Membership and Talent Mongo users, each limited to its own database.
- Separate Workbench and Data Protection Redis ACL users and key patterns.
- Separate Archive and Parallel You S3 keys, limited to the parent archive bucket.
- The campus's scoped Post Office credential and actual Workbench routing.
- Existing Parallel You database, browser-client and institution metadata copied
  from the validated production consumer, preserving its captures and sign-in client.
- The independently selected Decisions owner and `orchard-sky-workbench` stage.

The operator's new generated credentials are encrypted under the admin PVC's
`/data/web-campus-secrets`, with its encryption key in
`/data/web-campus-secrets-key/secret-key.key`. Include both in the existing backups.
The web receives only scoped credentials; infrastructure roots remain in admin.

Full-campus mode cannot load the standalone Parallel You consumer directly, so its
loader path is cleared and the validated settings snapshot is supplied in the campus
Secret. If Parallel You is reprovisioned or its credentials rotate, refresh that
snapshot from the newly validated consumer before restarting campus hosting.
Keep Library's separately provisioned Mongo settings unchanged.

Decisions uses a read-only directory client. Token acquisition uses the public SSO
origin; directory reads use the private `/admin/` API via the explicit
`Decisions__Directory__Keycloak__AdminApiBaseAddress` deployment setting. The public
SSO ingress intentionally does not expose that API.

Infrastructure PR #35 enables verified HTTPS between S3 ingress and SeaweedFS on
8334. It preserves the bucket's deny-insecure-transport policy. The existing
cert-manager Secret is mounted, and SeaweedFS 4.48 reloads renewed certificates.
The HTTP listener on 8333 remains for existing callers.

Before cutover an isolated pod with the exact image, Secrets and module bundles
completed campus startup and directory group queries. HTTP checks verified the
public pages, Decisions navigation, Administration ownership, and the existing
public SSO challenges for Decisions, Library and Parallel You. The new Registry
service registration is covered by a regression test; all 43 web tests pass, and
web PR #54 CI is green. No human account password or live authenticated draft/review
workflow was used for these deployment checks.

## Rollback

Revert only the campus activation manifest commit, retaining delivery-isolation PR
#11. That returns the old public image, `PublicSite__Enabled=true`, original Parallel
You artifact path, original Decisions slot, and original configuration Secret.
The new office/resources remain available for diagnosis and are not deleted.
The sign-in PVC is preserved. Campus sessions use the Redis Data Protection ring;
public-mode sessions use the existing PVC ring and may require another sign-in.
