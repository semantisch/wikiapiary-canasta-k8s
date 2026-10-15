#!/usr/bin/env python3
"""Regression coverage for proxy responses and interrupted production requests."""

import importlib.util
from http.client import IncompleteRead
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "smoke_production", Path(__file__).with_name("smoke-production.py")
)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class ProductionSmokeTest(unittest.TestCase):
    def test_edge_holding_page_has_actionable_error(self):
        with patch.object(smoke, "request", return_value=(
            b"<html>Applying secure edge configuration</html>",
            {"Content-Type": "text/html"},
        )):
            with self.assertRaisesRegex(RuntimeError, "example.test.*non-JSON.*text/html"):
                smoke.request_json("https://example.test/w/api.php")

    def test_transient_transport_errors_retry(self):
        for error in (TimeoutError("read timed out"), ConnectionResetError(), IncompleteRead(b"")):
            with self.subTest(error=type(error).__name__), \
                    patch("sys.argv", ["smoke", "--attempts", "2", "--delay", "0"]), \
                    patch.object(smoke, "configured_hosts", return_value=["example.test"]), \
                    patch.object(smoke, "smoke", side_effect=[error, "healthy"]) as probe, \
                    patch.object(smoke.time, "sleep"):
                smoke.main()
                self.assertEqual(probe.call_count, 2)

    def test_persistent_timeout_still_fails(self):
        with patch("sys.argv", ["smoke", "--attempts", "2", "--delay", "0"]), \
                patch.object(smoke, "configured_hosts", return_value=["example.test"]), \
                patch.object(smoke, "smoke", side_effect=TimeoutError("read timed out")) as probe, \
                patch.object(smoke.time, "sleep"):
            with self.assertRaisesRegex(SystemExit, "failed after 2 attempts.*read timed out"):
                smoke.main()
            self.assertEqual(probe.call_count, 2)


if __name__ == "__main__":
    unittest.main()
