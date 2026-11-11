import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from scope import list_scoped, watcher, watchers


class NamespaceScopeTests(unittest.TestCase):
    def test_pages_stay_in_allowed_namespaces_and_reset_cursor(self):
        api = SimpleNamespace(list_namespaced_config_map=Mock(side_effect=[
            SimpleNamespace(items=[1], metadata=SimpleNamespace(_continue="next")),
            SimpleNamespace(items=[2], metadata=SimpleNamespace(_continue="")),
            SimpleNamespace(items=[3], metadata=SimpleNamespace(_continue="")),
        ]))
        self.assertEqual(list(list_scoped(api, "config_map", ["wiki", "edge"])), [1, 2, 3])
        calls = [call.kwargs for call in api.list_namespaced_config_map.call_args_list]
        self.assertEqual([call["namespace"] for call in calls], ["wiki", "wiki", "edge"])
        self.assertEqual(calls[1]["_continue"], "next")
        self.assertNotIn("_continue", calls[2])
        self.assertTrue(all(call["limit"] == 50 and not call["watch"] for call in calls))

    def test_watch_preserves_model_docstring_and_bounds_network_wait(self):
        received = {}
        def method(**kwargs):
            """:return: V1PodList"""
            received.update(kwargs)
            return "stream"
        wrapped = watcher(method, "wiki")
        self.assertEqual(wrapped(watch=True, resource_version="123"), "stream")
        self.assertEqual(wrapped.__doc__, method.__doc__)
        self.assertEqual(received, {"watch": True, "resource_version": "123", "namespace": "wiki", "timeout_seconds": 60, "_request_timeout": (10, 90)})

    def test_all_resource_watches_are_namespaced(self):
        core = SimpleNamespace(**{f"list_namespaced_{name}": lambda **kw: kw for name in ("pod", "config_map", "service", "secret")})
        network = SimpleNamespace(list_namespaced_ingress=lambda **kw: kw)
        result = watchers(core, network, ["wiki", "edge"])
        self.assertEqual(len(result), 10)
        for key, watch in result.items():
            self.assertEqual(watch(watch=True)["namespace"], key.split("/")[1])

    def test_no_namespace_filter_retains_bounded_cluster_mode(self):
        api = SimpleNamespace(list_pod_for_all_namespaces=Mock(return_value=SimpleNamespace(items=[1], metadata=SimpleNamespace(_continue=""))))
        self.assertEqual(list(list_scoped(api, "pod", None)), [1])
        self.assertNotIn("namespace", api.list_pod_for_all_namespaces.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
