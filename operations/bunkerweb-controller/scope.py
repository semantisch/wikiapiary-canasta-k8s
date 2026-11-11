"""Bound BunkerWeb 1.6.8 discovery to its configured namespaces."""
from functools import wraps


def list_scoped(api, resource, namespaces):
    """Stream paginated snapshots instead of materialising a cluster-wide list."""
    method = getattr(api, f"list_namespaced_{resource}" if namespaces else f"list_{resource}_for_all_namespaces")
    for namespace in namespaces or [None]:
        options = {"namespace": namespace} if namespace else {}
        while True:
            page = method(watch=False, limit=50, _request_timeout=(10, 30), **options)
            yield from page.items
            cursor = page.metadata._continue
            if not cursor:
                break
            options["_continue"] = cursor


def watcher(method, namespace=None):
    # Watch uses the generated client's docstring to discover the response type.
    @wraps(method)
    def scoped(**kwargs):
        kwargs.update(timeout_seconds=60, _request_timeout=(10, 90))
        if namespace is not None:
            kwargs["namespace"] = namespace
        return method(**kwargs)
    return scoped


def watchers(core, networking, namespaces):
    resources = {"pod": core, "ingress": networking, "configmap": core, "service": core, "secret": core}
    result = {}
    for resource, api in resources.items():
        # API method spelling differs from the short event label.
        noun = "config_map" if resource == "configmap" else resource
        for namespace in namespaces or [None]:
            method = getattr(api, f"list_namespaced_{noun}" if namespace else f"list_{noun}_for_all_namespaces")
            result[f"{resource}/{namespace or '*'}"] = watcher(method, namespace)
    return result


def seed_watch(method, event_watcher):
    """Start at the collection cursor, not an old object's resource version.

    The controller rebuilds all configuration on RESYNC, so only one item is
    needed to obtain a consistent current collection cursor. This also catches
    deletions missed while a watch cursor was expired.
    """
    snapshot = method(watch=False, limit=1)
    event_watcher.resource_version = snapshot.metadata.resource_version
    return {"type": "RESYNC"}
