# Argo CD Bootstrap

Argo CD itself is installed directly into the hosting cluster. This directory
holds only reference manifests for the repo credential pattern.

The live bootstrap steps are:

1. Install Argo CD into namespace `argocd`.
2. Create a private repository credential secret for
   `https://github.com/semantisch/wikiapiary-canasta-k8s.git`.
3. Apply `argocd/wikiapiary.yaml`.

The Canasta application then syncs from Git into namespace
`canasta-wikiapiary-live`.
