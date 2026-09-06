#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"

secrets_file="$repo_root/secrets/aethericforge-web.enc.env"
namespace="aetheric-forge"
secret_name="aethericforge-web-config"

command -v sops >/dev/null 2>&1 || {
    echo "error: sops is required" >&2
    exit 1
}

command -v kubectl >/dev/null 2>&1 || {
    echo "error: kubectl is required" >&2
    exit 1
}

[[ -f "$secrets_file" ]] || {
    echo "error: secrets file not found: $secrets_file" >&2
    exit 1
}

sops --decrypt --input-type dotenv --output-type dotenv "$secrets_file" \
    | kubectl create secret generic "$secret_name" \
        --namespace "$namespace" \
        --from-env-file=/dev/stdin \
        --dry-run=client \
        --output=yaml \
    | kubectl apply -f -

echo "Applied secret/$secret_name in namespace $namespace from $secrets_file"
