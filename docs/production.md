# Production deployment

ArgoCD Application aetheric-web deploys overlays/prod from main into aetheric-forge. The website v2.0.0 and admin v2.0.3 images are pinned by digest.

- Public website: https://aethericforge.ca and https://www.aethericforge.ca (le-prod).
- Internal admin: https://admin.int.aethericforge.ca (step-ca-int-ca).
- SSO: https://sso.aethericforge.ca/realms/int.aethericforge.ca.

The admin client is aetheric-admin, with callback /signin-oidc and logout callback /signout-callback-oidc. The dedicated realm has registration disabled; create administrator accounts explicitly. Public Keycloak ingress permits only this realm and shared static resources; BlackCircuit realms return 404.

Create aethericforge-web-config, aethericforge-admin-config and aetheric-ghcr-secret before applying argocd/application.yaml. Configure the authenticated HTTPS repository Secret in argocd. Deployment and encrypted Secret recovery are documented in [infrastructure](https://github.com/aetheric-forge/infrastructure/blob/main/docs/operations/aetheric-production.md).

Normal admin mode requires explicit Maintenance:MongoDb:Host and Membership:MongoDb:Host in addition to credentials, even when a shared MongoDb:Host is present. Otherwise bootstrap defaults attempt to load a stored root credential. The .env.admin.example includes these endpoints.

The production step-ca root is supplied in base/step-ca-root-ca.yaml. Replace it as part of CA rotation. Admin data uses its own PVC; Redis ACLs and data protection keys use the platform Redis PVC.

Validation: both apps Ready, ArgoCD Synced/Healthy, public HTTPS / and /projects return 200, private admin redirects through the Aetheric OIDC client and loads the login form, and cross-tenant and encoded realm paths return 404. Interactive sign-in requires an account in the new realm. A provisioning worker was not deployed.

Admin automatically routes incomplete provisioning credentials through the existing setup wizard before University bootstrap. Setup uses the `provisioner` client and deployment-owned public origin from the admin manifest; normal admin login continues to use the existing configured client. Completing and saving tested infrastructure credentials returns to `/university` without a manual deployment-mode switch.
