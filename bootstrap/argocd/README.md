# Argo CD Bootstrap

Argo CD itself is installed directly into the hosting cluster. This directory
holds the reference repository registration.

The live bootstrap steps are:

1. Install Argo CD into namespace `argocd`.
2. Register `https://github.com/semantisch/wikiapiary-canasta-k8s.git` without
   credentials by applying `repository-secret.example.yaml`. The repository is
   public; storing a personal token makes GitOps depend on that token remaining
   valid and can stop reconciliation when it expires or is revoked.
3. Apply `argocd/wikiapiary.yaml`.

The Canasta application then syncs from Git into namespace
`canasta-wikiapiary-live`.
