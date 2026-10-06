# Aetheric Forge website and admin

Kustomize manifests for `www.aethericforge.ca`, `aethericforge.ca`, and
`admin.int.aethericforge.ca` in namespace `aetheric-forge`.

## Layout

- `base/`: website Deployment, Service, CA ConfigMap, and Velero backup schedule.
- `base/admin/`: admin Deployment, internal Service, and 1Gi persistent volume.
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

Both Linux amd64 images are pinned by version and immutable digest:

- `ghcr.io/aetheric-forge/aethericforge-web:v2.0.0`, source commit
  `48a8e3eaf7d0118fb20758b7552727cd8f6e2921`.
- `ghcr.io/aetheric-forge/aetheric-admin:v2.0.1`, built from the admin working
  tree based on `ecc7d35a28dccb5962cbe6c4e7b60381f950dc80`, including the
  RabbitMQ credential forms and existing bootstrap/login fixes. Immutable digest:
  `sha256:a868bf8784b7c207f9146d6bb19d086ad311a0bcd11b262aebffb71147b0c73d`.

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
