# WikiApiary Canasta Kubernetes

[![Validate](https://github.com/semantisch/wikiapiary-canasta-k8s/actions/workflows/validate.yaml/badge.svg)](https://github.com/semantisch/wikiapiary-canasta-k8s/actions/workflows/validate.yaml)
[![Production](https://github.com/semantisch/wikiapiary-canasta-k8s/actions/workflows/production.yaml/badge.svg)](https://github.com/semantisch/wikiapiary-canasta-k8s/actions/workflows/production.yaml)

GitOps source for WikiApiary on the three-node `dobriyai-hosting` Kubernetes
cluster. The live Argo CD application reads this repository's `main` branch,
renders `charts/canasta` with `values/prod.yaml`, and reconciles namespace
`canasta-wikiapiary-live` with pruning and self-healing enabled.

## Repository layout

- `charts/canasta/` contains the Canasta Helm chart and WikiApiary workloads.
- `values/prod.yaml` is the reviewed production configuration.
- `argocd/wikiapiary.yaml` declares the live Argo CD application.
- `bootstrap/` contains examples for cluster-only secrets and bootstrap state.
- `scripts/` contains policy, cache behavior, cutover, and production smoke tests.
- `.github/workflows/validate.yaml` validates every pull request and `main` push.
- `.github/workflows/production.yaml` observes the pull-based Argo CD deployment.

## CI/CD flow

1. A contributor opens a pull request from any fork.
2. `Validate / Helm and policy` lints the chart, renders production manifests,
   rejects duplicate YAML keys or unsafe GitOps drift, exercises the cache
   warmer, and simulates a `wikiapiary.com` hostname cutover.
3. Protected `main` accepts only reviewed, validated pull requests.
4. Argo CD detects the merge and automatically reconciles the live namespace.
5. The `Production / Observe GitOps deployment` job waits for the repo-configured
   canonical hostname, MediaWiki identity, and homepage cache HIT.

GitHub Actions has no kubeconfig, Argo CD token, or production secret. Argo CD
pulls from GitHub, which keeps workflows from untrusted forks isolated from the
cluster. Runtime secrets remain in Kubernetes and are referenced by name.

## Hostname configuration

`site.primaryHost` in `values/prod.yaml` is the canonical source of truth for
MediaWiki, Caddy, ingress routing, job runners, Semantic MediaWiki, and cache
warming. `site.additionalHosts` contains aliases accepted during migrations.

Do not replace only an ingress hostname. Follow the two-phase procedure in
[docs/hostname-cutover.md](docs/hostname-cutover.md) after DNS points at the edge
load balancer and before making `wikiapiary.com` canonical.

## Local validation

Install Helm 3, Python 3, PHP 8.2 CLI, and the Python requirements, then run:

```bash
python3 -m pip install --requirement requirements-ci.txt
helm lint charts/canasta -f values/prod.yaml
helm template canasta-wikiapiary charts/canasta -f values/prod.yaml > /tmp/wikiapiary-rendered.yaml
python3 scripts/validate-gitops.py /tmp/wikiapiary-rendered.yaml
python3 scripts/validate-cache-warmer.py /tmp/wikiapiary-rendered.yaml
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Bootstrap and secrets

Argo CD, its repository credential, and live application secrets are bootstrapped
outside this public repository. Examples under `bootstrap/` contain names and
shapes only; never commit real credentials.

## Storage

Production runs multiple web, Caddy, Varnish, and job-runner replicas across the
worker nodes. Shared image, extension, skin, public-asset, and cache-warmer paths
use static RWX volumes backed by the in-cluster NFS workload. MariaDB,
Elasticsearch, and NFS backing storage are pinned to the designated data node.

## Upstream chart refresh

Use `scripts/vendor-canasta-chart.sh` to refresh the vendored Canasta chart from
a checked-out `Canasta-CLI` tree. Review the complete diff and run all validation
before opening a pull request.
