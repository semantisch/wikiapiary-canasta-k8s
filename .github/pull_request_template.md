## What changed

<!-- Describe the problem and the resulting behavior. -->

## Validation

- [ ] I ran Helm lint and rendered `values/prod.yaml`.
- [ ] I ran `scripts/validate-gitops.py` against the rendered manifests.
- [ ] I ran `scripts/validate-cache-warmer.py` when cache behavior changed.
- [ ] I did not include credentials, kubeconfigs, private data, or production logs.
- [ ] I reviewed the hostname cutover guide if routing, TLS, or canonical URLs changed.

## Deployment and rollback

<!-- Explain production impact and the smallest safe rollback. -->
