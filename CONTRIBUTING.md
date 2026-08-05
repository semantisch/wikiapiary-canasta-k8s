# Contributing

Thank you for improving WikiApiary's infrastructure. Contributions from forks
are welcome; contributors do not need access to the production cluster.

## Workflow

1. Fork the repository and create a focused branch from `main`.
2. Make the smallest coherent change and add validation for new behavior.
3. Run the commands in the README's local validation section.
4. Open a pull request and complete the checklist.
5. Address review and keep the branch current until all required checks pass.

The public CI workflow receives read-only repository access. It does not expose
cluster credentials or production secrets to pull requests.

## Production changes

Changes under `values/prod.yaml`, `argocd/`, Helm templates, and GitHub workflows
affect the deployment path and require maintainer review. A merge to protected
`main` is a production release: Argo CD automatically reconciles it.

For a canonical-host change, edit only `site.primaryHost`; do not add literal
deployment hostnames inside MediaWiki or Caddy configuration blobs. Retained
TLS aliases belong in `ingress.edge.tlsHosts`, not in a cutover PR. Follow
[`docs/hostname/README.md`](docs/hostname/README.md) for the migration procedure.

## Secrets and security reports

Never include tokens, kubeconfigs, passwords, database dumps, or unredacted
production logs in commits, issues, or pull requests. Report vulnerabilities
privately through the repository's Security tab as described in `SECURITY.md`.
