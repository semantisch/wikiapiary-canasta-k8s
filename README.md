# WikiApiary Canasta Kubernetes

GitOps deployment repo for running WikiApiary on the `dobriyai-hosting`
Kubernetes cluster.

## Layout

- `charts/canasta/` vendored upstream Canasta Helm chart from
  `CanastaWiki/Canasta-CLI`
- `values/prod.yaml` production values for `wikiapiary.dobriy.ai`
- `argocd/wikiapiary.yaml` Argo CD `Application`
- `bootstrap/argocd/` bootstrap manifests and examples
- `.github/workflows/validate.yaml` PR validation
- `scripts/vendor-canasta-chart.sh` refresh helper for the vendored chart

## Deploy Flow

1. Make changes in Git.
2. CI runs `helm lint` and `helm template`.
3. Merge to `main`.
4. Argo CD syncs the application into namespace `canasta-wikiapiary`.

## First-Time Bootstrap

Argo CD and the private repo credential are bootstrapped into the hosting
cluster outside this repo. After that, Argo CD manages the Canasta release
defined here.

## Storage

The initial production values use `local-path` and a single web replica.
This is suitable for the first Canasta base install on the hosting cluster,
but it is not the final multi-node RWX layout for WikiApiary migration.

When we add shared storage, update:

- `web.replicaCount`
- `persistence.*.storageClass`
- `persistence.*.accessMode`

## Upstream Chart Refresh

Use `scripts/vendor-canasta-chart.sh` to refresh the vendored Canasta chart
from a checked-out `Canasta-CLI` tree, then review the diff before merging.
