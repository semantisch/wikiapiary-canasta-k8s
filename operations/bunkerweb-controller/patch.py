"""Apply a version-checked, minimal patch inside an init container."""
import hashlib
from pathlib import Path
import shutil

source = Path("/usr/share/bunkerweb/autoconf/controllers")
target = Path("/patched")
expected = {
    "KubernetesController.py": "ef85ec09239f56e12f65ee29b435eaffb5dbfea5b5046b6839c6552f510201c4",
    "IngressController.py": "c0f8bf223dff320336d570af188e316155ffbc4dd6a1e632810725f490a90457",
}
for filename, digest in expected.items():
    data = (source / filename).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise SystemExit(f"Unexpected upstream {filename}, review patch before upgrading BunkerWeb")
    text = data.decode()
    text = text.replace("from os import getenv", "from os import getenv\nfrom controllers.namespace_scope import list_scoped, watchers, seed_watch")
    text = text.replace("self._corev1.list_pod_for_all_namespaces(watch=False).items", "list_scoped(self._corev1, 'pod', self._namespaces)")
    text = text.replace("self._corev1.list_config_map_for_all_namespaces(watch=False).items", "list_scoped(self._corev1, 'config_map', self._namespaces)")
    text = text.replace("self._networkingv1.list_ingress_for_all_namespaces(watch=False).items", "list_scoped(self._networkingv1, 'ingress', self._namespaces)")
    if filename == "KubernetesController.py":
        # Keep the watch cursor across normal server timeouts. A fresh Watch
        # would replay every existing object each minute and force redundant
        # reconciliations. Reset only when the API says the cursor expired.
        text = text.replace("        while attempt < retries:", "        event_watcher = watch.Watch()\n        while attempt < retries:")
        text = text.replace("                yield from watch.Watch().stream(what)", "                if event_watcher.resource_version is None:\n                    yield seed_watch(what, event_watcher)\n                yield from event_watcher.stream(what, resource_version=event_watcher.resource_version, timeout_seconds=60)\n                attempt = 0\n                continue")
        text = text.replace("        if self._first_start:", '        if self._first_start or event.get("type") == "RESYNC":')
        text = text.replace('                    ignored = True\n                    attempt += 1', '                    ignored = True\n                    event_watcher.resource_version = None\n                    attempt += 1')
    if filename == "IngressController.py":
        start = text.index("    def _get_watchers(self):")
        end = text.index("    def _patch_ingress_status", start)
        text = text[:start] + "    def _get_watchers(self):\n        return watchers(self._corev1, self._networkingv1, self._namespaces)\n\n" + text[end:]
    compile(text, filename, "exec")
    (target / filename).write_text(text)
shutil.copyfile("/patch/scope.py", target / "namespace_scope.py")
print("Applied namespace-scoped discovery and bounded watch patch")
