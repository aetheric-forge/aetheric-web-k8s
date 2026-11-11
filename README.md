# Aetheric Forge website and admin

Kustomize manifests for `www.aethericforge.ca`, `aethericforge.ca`, and
`admin.int.aethericforge.ca` in namespace `aetheric-forge`.

## Layout

- `base/`: website Deployment, Service, CA ConfigMap, and Velero backup schedule.
- `base/admin/`: admin Deployment, internal Service, and 1Gi persistent volume.
- `base/worker/`: Operations provisioning worker and separate 1Gi persistent volume.
- `overlays/dev/`: existing development website ingress.
- `overlays/prod/`: production website and private admin ingress.
- `overlays/bootstrap/`: the same production resources with web replicas set to zero while admin and the provisioning worker run.
- `argocd/application.yaml`: Application targeting `overlays/prod`.

Production serves both public names directly using `nginx-public` and `le-prod`.
Admin uses `nginx-private` and the requested ClusterIssuer `step-ca-int-ca`.
Both ingresses declare their hostnames for external-dns. DNS targets come from
the ingress controller's published load-balancer status; no old development IP
is pinned. The existing Cloudflare external-dns instance must include
`aethericforge.ca`; internal DNS must include `int.aethericforge.ca`.

## Published images

Linux amd64 images are pinned by version and immutable digest:

- `ghcr.io/aetheric-forge/aethericforge-web:sha-2ca4ac7`, tested source commit
  `2ca4ac74bcef1392cfbffa3fab31178f16631fc9` (web PR #54, merged as `3ee03c7`).
  Full campus hosting mounts the new Decisions office under Administration,
  using its parent Workbench stage and scoped provisioned consumer. Immutable digest:
  `sha256:651056106c746b69e763061365170aff3f1e94ac2613b48cc0b91b5a73e24931`.
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

Production now runs full-campus mode (`PublicSite__Enabled=false`). The separate
`aethericforge-web-campus-v1` Secret supplies scoped campus credentials and the
validated Parallel You settings retained from its existing consumer artifact.
The original sign-in PVC and consumer Secrets are retained. Decisions delivery uses
`aethericforge-decisions-consumer-v1`, leaving the old public-mode slot untouched.
See [Decisions deployment](docs/decisions-deployment.md) for prerequisites and rollback.

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

The source type must be **Kustomize**, with path `overlays/prod`. The Application
manifest explicitly selects `spec.source.kustomize`. When configuring an existing
Application in the UI, remove `spec.source.directory` (including any empty Jsonnet
settings) before selecting Kustomize; ArgoCD must have only one explicit source type.
Preserve the existing Application name rather than creating a second app for the
same resources.

If sync reports `The Kubernetes API could not find
kustomize.config.k8s.io/Kustomization`, ArgoCD is treating `kustomization.yaml` as a
cluster resource in Directory mode. This is a source-rendering error, not a missing
CRD. Verify `kubectl kustomize overlays/prod` renders Deployments, Services, and
Ingresses with no `kind: Kustomization` in the output before retrying sync.

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

## Preserve provisioning state during updates

Update the existing Application in place. To pause reconciliation, disable
Auto-Sync and terminate an active sync. To stop a crashing web container, disable
Auto-Sync before scaling only the web Deployment to zero. Do not delete and
recreate the Application as an upgrade procedure.

The three application PVCs and five consumer Secrets carry
`Prune=false,Delete=false` so ArgoCD retains them during pruning and Application
deletion. These annotations must already be synced to the live resources to
protect them. They do not protect against direct Kubernetes deletion, namespace
deletion, or replacement/force operations. Intentional retirement requires a
separate, explicit cleanup after a verified backup.

Configure the Application from `argocd/application.yaml`, retaining its consumer
Secret `ignoreDifferences` rules and `RespectIgnoreDifferences=true`. Creating an
Application in the UI with only the repository and overlay path does not import
these Application settings. Do not enable Replace or Force for this application.

Before starting or updating full-campus hosting, verify the mounted Library,
Archive, and Decisions consumer Secrets contain their provisioned
`configuration.json`, and verify the existing admin/worker PVCs and their
credential encryption keys are preserved. An empty Secret slot is not a restored
consumer. The full-campus host requires Library even when its slot is empty.
Restore the original complete consumer artifacts from a verified backup, or use
the supported provisioning workflow; do not copy another institution's database
credentials or weaken the credential policy. Do not sync full-campus workloads
until this prerequisite is satisfied.

See [ArgoCD resource retention options](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/).

## Bootstrap, resume, and upgrade sequence

Use one Application throughout, with the settings in `argocd/application.yaml`.
For a fresh install or missing provisioning state, keep Auto-Sync disabled and
select `overlays/bootstrap` as its Kustomize source path. This uses the production
hosts, Secrets, and persistent storage, starts admin and Operations worker, and
keeps web at zero replicas. Do not create a second Application for the production
phase or sync `overlays/prod` concurrently.

1. Preserve existing operator-managed configuration Secrets. Validate their
   endpoints and scoped accounts rather than deleting them. Admin and worker
   still require their configuration and broker Secrets before they can start.
2. Restore bootstrap state, root credentials, and their ORIGINAL encryption key
   together when they exist. Admin reuses matching saved state and credentials;
   it opens `/setup` when required root credentials are missing. Corrupt,
   undecryptable, or mismatched state requires operator intervention, not a reset.
   A new cluster PVC does not automatically discover state in a local Docker
   volume. Transfer it securely if reusing it; never commit plaintext credentials.
   Application credentials in configuration Secrets are not provisioning roots.
3. Open `https://admin.int.aethericforge.ca/setup` if requested, complete verified
   setup, then use `/university` and institution provisioning. Review and submit
   the current required definitions and bindings. Preserve institution identities
   and existing resource ownership when reconciling infrastructure left behind
   by a missing worker volume. Ownership conflicts require review; do not delete
   shared databases or substitute another institution's credentials.
4. Explicitly rerun the affected provisioning request when definitions, bindings,
   required resources, or consumer configuration requirements change. The worker
   fingerprints definitions/bindings into a plan identity and resumes successful
   steps for that same plan from its checkpoints, requiring saved secrets to be
   decryptable. Successful institution requests deliver consumer configuration
   again, even when provisioning steps are already satisfied. Checkpoints alone
   do not verify that an externally deleted resource still exists; reconcile
   such drift deliberately. No web image update automatically submits a new plan.
5. Run the read-only structural gate:

   ```sh
   python3 scripts/check-web-prerequisites.py --context blackcircuit-ca-platform-prod
   ```

   It returns nonzero for missing PVCs, unbound admin/worker PVCs, missing campus credentials, empty
   consumer slots, or mismatched consumer identity/environment/Decisions owner.
   The paused web PVC may remain Pending with WaitForFirstConsumer storage; verify
   it binds when web is enabled. It prints only diagnostic names/codes, never Secret values. It is not a service
   connectivity test, complete host schema validation, or proof that a previous
   consumer plan satisfies new resource requirements. Review the submitted plan
   and consumer delivery results and test the scoped service access as well.
6. Only after provisioning and validation succeed, change the SAME Application
   source path to `overlays/prod` and sync it. Check web startup and readiness,
   then public pages and authenticated workflows. Re-enable automatic sync after
   those checks. For ordinary updates with intact state and unchanged provisioning
   requirements, keep using `overlays/prod`; do not repeat bootstrap or initialize
   its state again.

Offline gate tests: `python3 -m unittest discover -s scripts -p 'test_web_prerequisites.py'`.
Both overlays can be checked without deployment using `kubectl kustomize` and
`kubectl apply --dry-run=server -k overlays/bootstrap` (or `overlays/prod`).
