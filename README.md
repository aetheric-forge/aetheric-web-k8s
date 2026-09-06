# Aetheric Forge website Kubernetes deployment

Kustomize manifests for deploying the Aetheric Forge website to the Aetheric Forge Kubernetes cluster.

## Layout

```text
base/          Deployment, Service, and namespace backup schedule
overlays/dev/  Public ingress and TLS configuration
```

## Application configuration secret

The application's configuration lives encrypted at rest in `secrets/aethericforge-web.enc.env`, using [SOPS](https://github.com/getsops/sops) with an `age` recipient (see `.sops.yaml`). Only holders of the matching `age` private key can decrypt it.

The application reads ASP.NET Core configuration from these environment variables. Double underscores map to configuration sections; for example, `RabbitMq__Password` maps to `RabbitMq:Password`. `.env.example` documents the expected keys.

To edit the secret values (opens your `$EDITOR` on the decrypted contents, re-encrypts on save):

```bash
sops secrets/aethericforge-web.enc.env
```

To create or update the Kubernetes Secret from the encrypted file:

```bash
./scripts/apply-secrets.sh
```

This requires `sops`, `kubectl`, and a valid `age` private key available at `$SOPS_AGE_KEY_FILE` (default `~/.config/sops/age/keys.txt`).

After changing the Secret on an existing deployment, restart the workload so the process receives the new environment:

```bash
kubectl rollout restart deployment/aethericforge-web \
  --namespace aetheric-forge
kubectl rollout status deployment/aethericforge-web \
  --namespace aetheric-forge \
  --timeout=180s
```

## Validate and deploy

Render the complete development overlay before applying it:

```bash
kubectl kustomize overlays/dev
```

Apply and observe the rollout:

```bash
kubectl apply -k overlays/dev
kubectl rollout status deployment/aethericforge-web \
  --namespace aetheric-forge \
  --timeout=180s
```
