# Aetheric Forge website Kubernetes deployment

Kustomize manifests for deploying the Aetheric Forge website to the Aetheric Forge Kubernetes cluster.

## Layout

```text
base/          Deployment, Service, and namespace backup schedule
overlays/dev/  Public ingress and TLS configuration
```

## Application configuration secret

Copy `.env.example` to a local file named `.env.aethericforge-web`, replace the example values, and do not commit it.

Create or update the Kubernetes Secret:

```bash
kubectl create secret generic aethericforge-web-config \
  --namespace aetheric-forge \
  --from-env-file=.env.aethericforge-web \
  --dry-run=client \
  --output=yaml \
  | kubectl apply -f -
```

The application reads ASP.NET Core configuration from these environment variables. Double underscores map to configuration sections; for example, `RabbitMq__Password` maps to `RabbitMq:Password`.

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
