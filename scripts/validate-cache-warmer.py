#!/usr/bin/env python3
"""Validate rendered cache-warmer scripts, including a live PHP smoke test."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import yaml


class CacheBackendHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        content_type = "text/html; charset=UTF-8"
        cache_control = "public, max-age=3600"
        cache_status = "HIT"
        cache_age: str | None = "42"

        if parsed.path == "/w/api.php":
            content_type = "application/json"
            if query.get("list") == ["recentchanges"]:
                body = {
                    "query": {
                        "recentchanges": [
                            {
                                "type": "edit",
                                "title": "Recently changed",
                                "timestamp": "2026-01-01T00:00:00Z",
                            }
                        ]
                    }
                }
            elif "languages" in query.get("siprop", []):
                body = {
                    "query": {
                        "languages": [
                            {"code": "en"},
                            {"code": "de"},
                        ]
                    }
                }
            elif query.get("list") == ["allpages"]:
                body = {"query": {"allpages": []}}
            elif query.get("action") == ["ask"]:
                body = {"query": {"results": []}}
            else:
                body = {"query": {}}
            payload = json.dumps(body).encode()
        elif query.get("action") == ["raw"]:
            content_type = "text/plain; charset=UTF-8"
            payload = b"[[Websites]] [[Websites/Youngest]]"
        else:
            payload = (
                b'<html><div id="mw-content-text">'
                b'<a href="/wiki/Websites">Websites</a>'
                b'<a href="/wiki/Websites/Youngest">Youngest</a>'
                b"</div></html>"
            )

        if parsed.path == "/wiki/Uncacheable":
            cache_control = "no-cache, no-store, max-age=0, must-revalidate"
            cache_status = "MISS"
            cache_age = None

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", cache_control)
        self.send_header("X-WikiApiary-Cache", cache_status)
        if cache_age is not None:
            self.send_header("Age", cache_age)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def run_checked(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        check=False,
        env=env,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout


def find_cache_warmer(rendered_path: Path) -> dict[str, str]:
    with rendered_path.open(encoding="utf-8") as rendered:
        documents = list(yaml.safe_load_all(rendered))
    matches = [
        document
        for document in documents
        if isinstance(document, dict)
        and document.get("kind") == "ConfigMap"
        and str(document.get("metadata", {}).get("name", "")).endswith("cache-warmer")
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one cache-warmer ConfigMap, found {len(matches)}")
    data = matches[0].get("data")
    if not isinstance(data, dict):
        raise RuntimeError("cache-warmer ConfigMap has no data")
    return {str(name): str(content) for name, content in data.items()}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def assert_successful_report(path: Path) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    results = report.get("results", [])
    if not results:
        raise RuntimeError(f"{path.name} contains no cache targets")
    failed = [result for result in results if not result.get("ok")]
    if failed:
        raise RuntimeError(f"{path.name} contains failed targets: {failed}")
    return report


def validate(rendered_path: Path) -> None:
    scripts = find_cache_warmer(rendered_path)
    required = {
        "discover.php",
        "warm.php",
        "priority.php",
        "worker.php",
        "run-discover.sh",
        "run-warm.sh",
        "run-warm-priority.sh",
        "run-worker.sh",
    }
    missing = required.difference(scripts)
    if missing:
        raise RuntimeError(f"cache-warmer ConfigMap is missing: {sorted(missing)}")

    with tempfile.TemporaryDirectory(prefix="wikiapiary-cache-test-") as temporary:
        root = Path(temporary)
        script_dir = root / "scripts"
        cache_dir = root / "cache"
        script_dir.mkdir()
        cache_dir.mkdir()

        for name, content in scripts.items():
            script_path = script_dir / name
            script_path.write_text(content, encoding="utf-8")
            script_path.chmod(0o755)

        for php_script in sorted(script_dir.glob("*.php")):
            run_checked(["php", "-l", str(php_script)])
        for shell_script in sorted(script_dir.glob("*.sh")):
            run_checked(["sh", "-n", str(shell_script)])

        server = ThreadingHTTPServer(("127.0.0.1", 0), CacheBackendHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"

        common_env = os.environ.copy()
        common_env.update(
            {
                "SITE_SERVER": "https://wikiapiary.dobriy.ai",
                "SITE_HOST": "wikiapiary.dobriy.ai",
                "WARM_CACHE_DIR": str(cache_dir),
                "WARM_BASE_URL": base_url,
                "WARM_FANOUT_HOST": "",
                "WARM_HOST_HEADER": "wikiapiary.dobriy.ai",
                "DISCOVER_BASE_URL": base_url,
                "DISCOVER_HOST_HEADER": "wikiapiary.dobriy.ai",
                "ACCESS_LOG_FILE": str(cache_dir / "access.log"),
                "REQUEST_TIMEOUT_SECONDS": "3",
            }
        )

        try:
            (cache_dir / "access.log").write_text(
                json.dumps(
                    {
                        "status": 200,
                        "request": {
                            "host": "wikiapiary.dobriy.ai",
                            "method": "GET",
                            "uri": "/wiki/Hot_Page",
                            "headers": {"User-Agent": ["Cache validator"]},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            run_checked(["php", str(script_dir / "discover.php")], env=common_env)

            run_checked(["php", str(script_dir / "warm.php")], env=common_env)
            assert_successful_report(cache_dir / "warm-run.json")

            write_json(
                cache_dir / "seed-pages.json",
                {
                    "pages": [
                        "/wiki/Main_Page",
                        "/wiki/Websites/Youngest",
                        "/wiki/Websites/WikiTeam/Deep",
                        "/wiki/Template:Hidden",
                        "/wiki/Uncacheable",
                    ]
                },
            )
            priority_env = common_env | {
                "PRIORITY_HOT_PAGES_LIMIT": "1",
                "PRIORITY_PAGES_LIMIT": "10",
            }
            run_checked(["php", str(script_dir / "priority.php")], env=priority_env)
            priority_report = assert_successful_report(cache_dir / "priority-warm-run.json")
            priority_seeds = priority_report.get("prioritySeeds", [])
            for expected in ["/wiki/Main_Page", "/wiki/Websites/Youngest"]:
                if expected not in priority_seeds:
                    raise RuntimeError(f"priority seed missing from report: {expected}")
            for rejected in ["/wiki/Websites/WikiTeam/Deep", "/wiki/Template:Hidden"]:
                if rejected in priority_seeds:
                    raise RuntimeError(f"ineligible priority seed entered report: {rejected}")
            skipped = [
                result.get("path")
                for result in priority_report.get("results", [])
                if result.get("skippedUncacheable")
            ]
            if "/wiki/Uncacheable" not in skipped:
                raise RuntimeError("no-store page was not classified as uncacheable")
            priority_uncacheable = json.loads(
                (cache_dir / "priority-uncacheable-pages.json").read_text(encoding="utf-8")
            )
            if "/wiki/Uncacheable" not in priority_uncacheable.get("pages", {}):
                raise RuntimeError("no-store page was not persisted in priority skip list")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rendered", type=Path, help="path to helm template output")
    args = parser.parse_args()
    validate(args.rendered)
    print("cache-warmer validation passed")


if __name__ == "__main__":
    main()
