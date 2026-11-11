#!/usr/bin/env python3
"""Read-only structural gate before enabling the full-campus web Deployment.

Secret values stay in memory and are never printed. This is not a connectivity
check or a substitute for the host's complete consumer-schema validation.
"""
import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys

CONSUMERS = {
    "library": "aethericforge-library-consumer",
    "archive": "aethericforge-archive-consumer",
    "decisions": "aethericforge-decisions-consumer-v1",
}
PVCS = ("aethericforge-admin-data", "aetheric-provisioning-worker-data", "aethericforge-web-signin-data")


def check_consumer(secret, module, environment, expected_owner):
    """Return fixed diagnostic codes only, never exception text or artifact values."""
    try:
        raw = base64.b64decode(secret.get("data", {}).get("configuration.json", ""), validate=True)
        if not raw:
            return "missing configuration.json; rerun provisioning with consumer delivery"
        if len(raw) > 65536:
            return "consumer artifact exceeds host size limit"
        artifact = json.loads(raw)
        if not isinstance(artifact, dict):
            return "invalid consumer artifact"
        repository = "https://github.com/aetheric-forge/" + ("adr-campus" if module == "decisions" else module)
        # Match InstitutionDeploymentAttempt.Identity in the pinned runtime.
        deployment_id = hashlib.sha256(json.dumps([repository, module, environment], separators=(",", ":")).encode()).hexdigest()
        settings = artifact.get("Settings")
        if (artifact.get("Version") != 1 or artifact.get("Module") != module
                or artifact.get("InstitutionId") != module or artifact.get("Environment") != environment
                or artifact.get("DeploymentId") != deployment_id
                or not re.fullmatch(r"[0-9a-f]{64}", artifact.get("PlanId", ""))
                or not isinstance(settings, dict) or not settings
                or any(not isinstance(v, str) or not v.strip() for v in settings.values())):
            return "consumer identity, environment, plan, or settings are invalid"
        section = module.capitalize()
        if settings.get(section + ":Enabled", "").lower() != "true":
            return "consumer is not enabled"
        if module == "decisions" and (not expected_owner
                or settings.get("Decisions:Owner:DeploymentId") != expected_owner
                or settings.get("Decisions:Owner:Environment") != environment):
            return "consumer does not match the configured campus owner"
        return None
    except (ValueError, TypeError, UnicodeError, AttributeError):
        return "invalid consumer artifact"


def inspect(items, environment):
    secrets = {x["metadata"]["name"]: x for x in items if x["kind"] == "Secret"}
    pvcs = {x["metadata"]["name"]: x for x in items if x["kind"] == "PersistentVolumeClaim"}
    issues = []
    for name in PVCS:
        if pvcs.get(name, {}).get("status", {}).get("phase") != "Bound":
            issues.append(name + ": PVC missing or not Bound; establish persistent provisioning storage")
    config = {}
    for name in ("aethericforge-web-config", "aethericforge-web-campus-v1"):
        if name not in secrets:
            issues.append(name + ": required configuration Secret missing")
        for key, value in secrets.get(name, {}).get("data", {}).items():
            try:
                config[key] = base64.b64decode(value, validate=True).decode()
            except (ValueError, UnicodeError):
                issues.append(name + ": invalid configuration encoding")
    required_credentials = {
        "Registry__Keycloak": ("ClientId", "ClientSecret"),
        "Membership__MongoDb": ("Username", "Password"),
        "Talent__MongoDb": ("Username", "Password"),
        "PostOffice__RabbitMq": ("Username", "Password"),
        "ForgeCampus__Redis": ("Password",),
        "Workbench__Redis": ("Password",),
        "ParallelYou__MongoDb": ("Username", "Password"),
        "ParallelYou__S3": ("AccessKey", "SecretKey"),
    }
    for prefix, fields in required_credentials.items():
        for field in fields:
            key = prefix + "__" + field
            if not config.get(key, "").strip():
                issues.append(key + ": scoped credential missing; complete campus configuration")
    owner = config.get("Decisions__ExpectedOwnerDeploymentId")
    for module, name in CONSUMERS.items():
        error = check_consumer(secrets.get(name, {}), module, environment, owner)
        if error:
            issues.append(name + ": " + error)
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", help="Explicit kubectl context (otherwise use the current context)")
    parser.add_argument("--namespace", default="aetheric-forge")
    parser.add_argument("--environment", default="production")
    args = parser.parse_args()
    command = ["kubectl"]
    if args.context:
        command += ["--context", args.context]
    command += ["--request-timeout=20s", "get", "secrets,pvc", "--namespace", args.namespace, "-o", "json"]
    try:
        result = subprocess.run(command, capture_output=True, check=True, text=True)
        issues = inspect(json.loads(result.stdout)["items"], args.environment)
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, TypeError):
        print("BLOCKED: unable to inspect Secrets/PVCs; check kubectl context, connectivity, and read access.")
        return 2
    if issues:
        print("NOT READY: keep the bootstrap overlay active (web replicas: 0).")
        for issue in issues:
            print("- " + issue)
        return 1
    print("Structural prerequisites present. Verify provisioned plan requirements and service access before enabling web.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
