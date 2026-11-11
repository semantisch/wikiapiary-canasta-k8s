# Hosting BunkerWeb controller recovery

The hosting cluster uses the separately installed BunkerWeb Helm release 1.0.13,
with BunkerWeb 1.6.8. WikiApiary does not own that Helm release. The application
chart owns its ingress policy and site-scoped firewall ConfigMaps.

On 11 November 2026, the controller was not applying ingress or ConfigMap
updates. Restarting it exposed repeated out-of-memory failures, including at a
2 GiB container limit. The serving proxies retained their last valid config.

Upstream 1.6.8 filters `NAMESPACES` after fetching cluster-wide snapshots and
opens cluster-wide watches without a read timeout. This patch uses namespaced,
paginated snapshots and namespaced watches with bounded network waits. It
preserves the configured namespaces and all existing ingress policy decisions.
Each watch starts from the collection resource version, triggers a configuration
resync, and resumes from its cursor after normal timeouts. Expired cursors cause
a fresh snapshot so missed deletions are reconciled.
After applying it, the controller successfully reconciled both proxies and
remained near 100 MiB during validation.

The init container checks the exact SHA-256 of the two upstream source files.
It changes discovery calls and the watch factory, and compiles the result.
The source image is unchanged. A future incompatible image fails the init
check rather than applying a patch to unknown code.

The live Deployment patch and ConfigMap survive pod replacement. They are
operational changes to the shared Helm installation, stored here for review
and repeatability. Reapply them after a Helm upgrade until the upstream
controller supports bounded discovery. Do not have Argo CD adopt the shared
Deployment as a WikiApiary resource.

```bash
python3 operations/bunkerweb-controller/test_scope.py
bash operations/bunkerweb-controller/apply.sh \
  --kubeconfig /home/vanya/.kube/dobriyai-hosting.yaml
```

The resource reservation prevents best-effort scheduling. The preferred node
has sufficient headroom in this hosting cluster, with fallback allowed if it
is unavailable. This changes the controller only, not the two serving proxies.

Before upgrading BunkerWeb, compare the patch with upstream
[KubernetesController.py](https://github.com/bunkerity/bunkerweb/blob/v1.6.8/src/autoconf/controllers/KubernetesController.py)
and [IngressController.py](https://github.com/bunkerity/bunkerweb/blob/v1.6.8/src/autoconf/controllers/IngressController.py).
Update the hashes only after reviewing and testing the new source.

Rollback requires removing the `scope-discovery` init container, the three
`patched-controller` mounts, and the `discovery-patch` and `patched-controller`
volumes from the Deployment. Retain the resource reservation. Remove the
ConfigMap only after the controller no longer mounts it. The original
unbounded controller may exhaust memory again, so validate reconciliation
before considering rollback complete.
