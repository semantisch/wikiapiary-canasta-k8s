#!/usr/bin/env bash
set -euo pipefail
# Kubeconfig/server/context arguments are passed through to kubectl.
patch_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
kubectl "$@" -n bunkerweb create configmap bunkerweb-scoped-discovery \
  --from-file="patch.py=$patch_dir/patch.py" --from-file="scope.py=$patch_dir/scope.py" \
  --dry-run=client -o yaml | kubectl "$@" apply -f -
kubectl "$@" -n bunkerweb patch deployment controller-bunkerweb \
  --type=strategic --patch-file "$patch_dir/deployment-patch.yaml"
kubectl "$@" -n bunkerweb rollout status deployment/controller-bunkerweb --timeout=180s
