# Aetheric Forge website and admin

Kustomize manifests for `www.aethericforge.ca`, `aethericforge.ca`, and
`admin.int.aethericforge.ca` in namespace `aetheric-forge`.

## Layout

- `base/`: website Deployment, Service, CA ConfigMap, and Velero backup schedule.
- `base/admin/`: admin Deployment, internal Service, and 1Gi persistent volume.
- `base/worker/`: Operations provisioning worker and separate 1Gi persistent volume.
- `overlays/dev/`: existing development website ingress.
- `overlays/prod/`: production website and private admin ingress.
- `argocd/application.yaml`: Application targeting `overlays/prod`.

Production serves both public names directly using `nginx-public` and `le-prod`.
Admin uses `nginx-private` and the requested ClusterIssuer `step-ca-int-ca`.
Both ingresses declare their hostnames for external-dns. DNS targets come from
the ingress controller's published load-balancer status; no old development IP
is pinned. The existing Cloudflare external-dns instance must include
`aethericforge.ca`; internal DNS must include `int.aethericforge.ca`.

## Published images

Linux amd64 images are pinned by version and immutable digest:

- `ghcr.io/aetheric-forge/aethericforge-web:sha-c0a1653`, source commit
  `c0a1653f3dc26f42fc61aa1c6226689e70cc3378` (aetheric-web PR #51).
  Pinned Git modules for Parallel You, Library, Archive and Decisions; the
  sidebar links only to modules that are loaded. Immutable digest:
  `sha256:e144fb539af3e8faa040b6125547c9f06652d4dd1738b5df204789311e25bab4`.
- `ghcr.io/aetheric-forge/aetheric-admin:v2.0.7`, source commit
  `506d598a14109db8b65632db004cd0672081b982` (aetheric-admin PR #21), adding
  `/provisioning/institutions` to deploy pinned institutions (Library) through
  `institution/deploy` 2.0. Immutable digest:
  `sha256:443c05d5909cb8d0e139924e2a58a6e0178f054e6c3e83e63d9612c3e3c44a3e`.
- `ghcr.io/aetheric-forge/aetheric-provisioning-worker:sha-4c46cce`, built from
  aetheric-runtime commit `4c46cce` (PR #43), which delivers Library, Archive and
  Decisions consumer configurations to their web Secrets. Immutable digest:
  `sha256:b1c4163e649d8a15f7c48d8c2226193210676ff45e9de00c21a3fc8e94fe3572`.

The production Operations worker starts when the required RabbitMQ keys are present
in `aetheric-provisioning-worker-broker`, copied securely from the admin encrypted
AMQP credential store. It uses the same broker user and virtual host as
admin, subscribes to institution bootstrap and deployment requests, and publishes
results back to admin. It receives provisioning root credentials in each request.
Its separate PVC preserves checkpoints, generated secrets, and their encryption
key under `/data`. Like admin, the worker mounts `step-ca-root-ca` and sets
`SSL_CERT_FILE` so calls to private Keycloak trust the current platform CA.
Keep a single worker replica with Recreate updates. Back up
this PVC with the other resources in the `aetheric-forge` namespace.

The website defaults to public-site mode. Full campus mode requires
`PublicSite__Enabled=false` and the institution-specific credentials described
in aetheric-web's `docs/architecture/service-configuration.md`; the legacy flat
credential example is insufficient for campus mode.

## Application configuration

Website configuration is encrypted in `secrets/aethericforge-web.enc.env`.
Edit it with SOPS and apply it using `./scripts/apply-secrets.sh`. The existing
age identity is required.

Admin reads a separate required Secret, `aethericforge-admin-config`.
Use `.env.admin.example` as a key reference and populate a private file with
provisioned application credentials. Shared endpoint examples come from the
working BlackCircuit manifests; confirm endpoints against the target cluster.
Do not reuse BlackCircuit credentials or commit the populated file.

```sh
kubectl create secret generic aethericforge-admin-config \
  --namespace aetheric-forge --from-env-file=/private/path/.env.aetheric-admin \
  --dry-run=client -o yaml | kubectl apply -f -
```

Create the confidential `aetheric-admin` OIDC client in the configured realm:

- Redirect URI: `https://admin.int.aethericforge.ca/signin-oidc`.
- Post-logout redirect URI: `https://admin.int.aethericforge.ca/signout-callback-oidc`.
- Web origin: `https://admin.int.aethericforge.ca`.

Normal admin requires Redis, scoped Maintenance and Membership Mongo accounts,
and RabbitMQ permissions for the provisioning request/result exchanges and queues.
Optional marketing management uses its own Mongo account. Persisted bootstrap
state and encrypted root credentials live on the admin PVC under `/data`; the
single-replica Deployment uses Recreate to avoid overlapping admin instances.
This does not initialize the platform bootstrap workflow. Preserve the original
root encryption key if migrating existing bootstrap data.

The admin GHCR package is private. Create `aetheric-ghcr-secret` in
`aetheric-forge` using an account/token with pull access to the package.
The public website image does not require this Secret.

## Validate and deploy

```sh
kubectl kustomize overlays/prod
kubectl apply -f argocd/application.yaml
kubectl rollout status deployment/aethericforge-web -n aetheric-forge
kubectl rollout status deployment/aethericforge-admin -n aetheric-forge
```

The Application retains automatic sync. Its live source path must be updated to
`overlays/prod` by applying the Application manifest (or its parent GitOps app).
Provision admin configuration and the pull Secret before activating that overlay.
Admin access needs private DNS/network access and trust in the internal CA.
TCP probes verify the listener; verify authenticated SSO and database operations
after provisioning. Restart each Deployment after its configuration Secret changes.

## Infrastructure setup before University provisioning

Admin v2.0.2 automatically opens `/setup` when required provisioning root credentials are missing. `/university` redirects there until the credential workflow is completed. Existing encrypted credentials are retained for retesting; no manual `Bootstrap__Enabled` change is required. After administrator verification and tested credential save, the browser returns to University setup and normal admin sign-in.

The manifest configures the deployment-owned setup origin as `https://admin.int.aethericforge.ca` and uses the initial `provisioner` client in the configured Keycloak realm. That client needs realm administration permissions and the callback `https://admin.int.aethericforge.ca/setup/signin-oidc`; its secret is supplied through the wizard. The normal admin client remains configured by the existing secret. Keep the admin PVC and root encryption key across updates.

During initial setup, the suggested provisioner client ID can be changed. A changed ID is saved only after its existing Keycloak client verifies successfully. The saved ID survives restart and takes precedence over the manifest suggestion; choosing an administrator locks it. This step does not create the initial Keycloak client.

## Public sign-in

The website deploys the Git institution loader integration from source commit
`9f020acf371abbaf7a2defde91416ab19d011937` (`sha-9f020ac`, source PR #48),
including the existing public sign-in fix. Parallel You uses its external plugin
at commit `055551d6eba7e525665b89186ac914e46c8d3293` (Parallel You PR #17).
Startup loads the matching definition and bindings from public GitHub, so the
web pod needs outbound HTTPS access to GitHub. The existing provisioned consumer
Secret supplies the Library, Workbench, and OIDC settings.
Public content remains in `PublicSite__Enabled=true` mode.
`PublicSite__SignInEnabled=true` enables OIDC with the dedicated
`aetheric-web-public-signin` client in the saved bootstrap realm. The scoped
client secret is included in the encrypted web configuration backup. The admin
bootstrap root store and encryption key remain on the admin PVC.

The single-replica web Deployment uses Recreate updates and its own 1Gi PVC at
`/data` for Data Protection keys (`PublicSite__ProtectionKeyDirectory`). Preserve
this PVC so sign-in cookies and in-flight callbacks survive pod replacement.
Apply the encrypted web Secret with `scripts/apply-secrets.sh` before syncing.
The exact callbacks are `https://aethericforge.ca/signin-oidc` and
`https://www.aethericforge.ca/signin-oidc`; both logout callbacks are registered.
