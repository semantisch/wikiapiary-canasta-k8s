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
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import yaml


class CacheBackendHandler(BaseHTTPRequestHandler):
    received: list[tuple[str, str | None]] = []
    homepage_seed_pending = False
    homepage_seed_started = False
    homepage_overlap = False
    homepage_fail = False

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        parsed = urlparse(self.path)
        homepage_forced = parsed.path == "/wiki/Main_Page" and self.headers.get("X-WikiApiary-Force-Refresh") == "1"
        if homepage_forced and type(self).homepage_seed_pending:
            if type(self).homepage_seed_started:
                type(self).homepage_overlap = True
            else:
                type(self).homepage_seed_started = True
                time.sleep(0.2)
                type(self).homepage_seed_pending = False
        type(self).received.append(
            (parsed.path, self.headers.get("X-WikiApiary-Force-Refresh"))
        )
        query = parse_qs(parsed.query)
        content_type = "text/html; charset=UTF-8"
        cache_control = "public, max-age=3600"
        cache_status = "HIT"
        cache_age: str | None = "42"
        status = 200
        if homepage_forced and type(self).homepage_fail:
            status = 503
        location: str | None = None

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

        if parsed.path == "/":
            status = 301
            location = "http://127.0.0.1:9/must-not-be-followed"
            payload = b""

        if parsed.path == "/wiki/Uncacheable":
            cache_control = "no-cache, no-store, max-age=0, must-revalidate"
            cache_status = "MISS"
            cache_age = None

        if parsed.path == "/wiki/Main_Page":
            cache_age = "0"

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", cache_control)
        self.send_header("X-WikiApiary-Cache", cache_status)
        if location is not None:
            self.send_header("Location", location)
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
        "worker-health.php",
        "run-discover.sh",
        "run-warm.sh",
        "run-warm-priority.sh",
        "run-worker.sh",
    }
    missing = required.difference(scripts)
    if missing:
        raise RuntimeError(f"cache-warmer ConfigMap is missing: {sorted(missing)}")

    for script_name in ("discover.php", "warm.php", "priority.php", "worker.php"):
        script = scripts[script_name]
        if "tempnam(dirname($path), basename($path) . '.tmp.')" not in script:
            raise RuntimeError(f"{script_name} must use collision-safe atomic JSON writes")

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
                "SITE_SERVER": "https://primary.example.test",
                "SITE_HOST": "primary.example.test",
                "WARM_CACHE_DIR": str(cache_dir),
                "WARM_BASE_URL": base_url,
                "WARM_FANOUT_HOST": "",
                "FORCE_REFRESH_PORT": str(server.server_port),
                "WARM_HOST_HEADER": "primary.example.test",
                "WARM_HOST_HEADERS": "primary.example.test,mirror.example.test",
                "DISCOVER_BASE_URL": base_url,
                "DISCOVER_HOST_HEADER": "primary.example.test",
                "ACCESS_LOG_FILE": str(cache_dir / "access.log"),
                "REQUEST_TIMEOUT_SECONDS": "3",
            }
        )

        try:
            CacheBackendHandler.received = []
            (cache_dir / "access.log").write_text(
                json.dumps(
                    {
                        "status": 200,
                        "request": {
                            "host": "primary.example.test",
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
            warm_report = assert_successful_report(cache_dir / "warm-run.json")
            health = json.loads((cache_dir / "cache-health.json").read_text(encoding="utf-8"))
            if health.get("status") != "ok" or health.get("failed") != 0:
                raise RuntimeError(f"cache health report is not healthy: {health!r}")
            if ("/wiki/Recently_changed", "1") not in CacheBackendHandler.received:
                raise RuntimeError("recently changed page was not force-refreshed")
            expected_hosts = {"primary.example.test", "mirror.example.test"}
            for result in warm_report.get("results", []):
                warmed_hosts = {
                    target.get("host") for target in result.get("targetResults", [])
                }
                if warmed_hosts != expected_hosts:
                    raise RuntimeError(
                        f"cache target did not warm every mirror: {warmed_hosts!r}"
                    )

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
            priority_start = len(CacheBackendHandler.received)
            CacheBackendHandler.homepage_seed_pending = True
            CacheBackendHandler.homepage_seed_started = False
            CacheBackendHandler.homepage_overlap = False
            run_checked(["php", str(script_dir / "priority.php")], env=priority_env)
            if CacheBackendHandler.homepage_overlap:
                raise RuntimeError("homepage cache misses overlapped before first render finished")
            priority_requests = CacheBackendHandler.received[priority_start:]
            if (("/wiki/Main_Page", "1") not in priority_requests
                    or ("/wiki/Main_Page", None) not in priority_requests):
                raise RuntimeError("homepage must be force-refreshed then verified through normal cache")
            priority_report = assert_successful_report(cache_dir / "priority-warm-run.json")
            main_page = next(
                result for result in priority_report["results"]
                if result["path"] == "/wiki/Main_Page"
            )
            if any(target.get("age") != 0 for target in main_page["targetResults"]):
                raise RuntimeError("fresh cache hits must retain Age: 0")
            root_result = next(
                (
                    result
                    for result in priority_report.get("results", [])
                    if result.get("path") == "/"
                ),
                None,
            )
            if not root_result or root_result.get("refresh", {}).get("status") != 301:
                raise RuntimeError("priority warmer followed the root redirect")
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

            repair_start = len(CacheBackendHandler.received)
            run_checked(["php", str(script_dir / "priority.php")], env=priority_env | {
                "PRIORITY_HOT_PAGES_LIMIT": "0", "PRIORITY_PAGES_LIMIT": "1",
            })
            repair_report = assert_successful_report(cache_dir / "priority-warm-run.json")
            if [r["path"] for r in repair_report["results"]] != ["/wiki/Main_Page"]:
                raise RuntimeError("single-page repair mode must refresh the canonical homepage")
            repair_requests = CacheBackendHandler.received[repair_start:]
            if (("/wiki/Main_Page", "1") not in repair_requests
                    or ("/wiki/Main_Page", None) not in repair_requests
                    or any(path != "/wiki/Main_Page" for path, _ in repair_requests)):
                raise RuntimeError("repair mode did not force and verify the canonical homepage")

            failed_start = len(CacheBackendHandler.received)
            CacheBackendHandler.homepage_fail = True
            failed_run = subprocess.run(["php", str(script_dir / "priority.php")],
                                        env=priority_env, capture_output=True, text=True, timeout=30)
            CacheBackendHandler.homepage_fail = False
            if failed_run.returncode != 1:
                raise RuntimeError("failed homepage render must return a failed warmer status")
            forced = [r for r in CacheBackendHandler.received[failed_start:]
                      if r == ("/wiki/Main_Page", "1")]
            # request_urls permits three attempts on the first target.
            # The other hostname must receive none after all three fail.
            if len(forced) != 3:
                raise RuntimeError("failed homepage render must stop remaining forced requests")
            failed_report = json.loads((cache_dir / "priority-warm-run.json").read_text())
            failed_home = next(r for r in failed_report["results"] if r["path"] == "/wiki/Main_Page")
            if failed_home.get("ok") or failed_home.get("skippedUncacheable"):
                raise RuntimeError("failed homepage refresh must remain retryable and unverified")

            worker = scripts["worker.php"]
            # Reproduce a homepage purge waiting behind a large import backlog.
            queue_functions = worker[
                worker.index("function drain_queue("):worker.index("function tier1_core_pages(")
            ]
            queue_test = script_dir / "queue-test.php"
            queue_test.write_text(
                "<?php\nfunction eligible_warm_path($path) { return true; }\n"
                + queue_functions
                + "\n$queue = $argv[1]; $items = drain_queue($queue, 2); "
                + "echo json_encode($items);\n",
                encoding="utf-8",
            )
            backlog = [{"path": f"/wiki/Profile_{i}", "reason": "page-save"} for i in range(1000)]
            homepage_purge = {"path": "/wiki/Main_Page", "reason": "article-purge"}
            queue_path = cache_dir / "queue-test.ndjson"
            queue_path.write_text(
                "".join(json.dumps(entry) + "\n" for entry in backlog + [homepage_purge]),
                encoding="utf-8",
            )
            drained = json.loads(run_checked(["php", str(queue_test), str(queue_path)]))
            remaining = [json.loads(line) for line in queue_path.read_text().splitlines()]
            if drained != [homepage_purge, backlog[0]] or remaining != backlog[1:]:
                raise RuntimeError("homepage purge starved or profile work was reordered/lost")
            for marker in (
                "'X-WikiApiary-Force-Refresh: 1'",
                "['page-save', 'article-purge', 'page-move']",
                "touch($heartbeatFile)",
            ):
                if marker not in worker:
                    raise RuntimeError(f"cache worker safety marker missing: {marker}")

            heartbeat = root / "worker-heartbeat"
            heartbeat.touch()
            health_env = common_env | {
                "WORKER_HEARTBEAT_FILE": str(heartbeat),
                "WORKER_MAX_STALE_SECONDS": "60",
            }
            run_checked(["php", str(script_dir / "worker-health.php")], env=health_env)
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
