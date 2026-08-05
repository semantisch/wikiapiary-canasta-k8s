#!/usr/bin/env python3
"""Wait for the repo-configured WikiApiary host to become healthy and cached."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import yaml


USER_AGENT = "WikiApiary-GitOps-Smoke/1.0 (+https://github.com/semantisch/wikiapiary-canasta-k8s)"


def request(url: str) -> tuple[bytes, Any]:
    http_request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(http_request, timeout=20) as response:  # noqa: S310 - configured HTTPS host
        return response.read(), response.headers


def configured_host(values_path: Path) -> str:
    values = yaml.safe_load(values_path.read_text(encoding="utf-8"))
    host = values.get("site", {}).get("primaryHost")
    tls_hosts = values.get("ingress", {}).get("edge", {}).get("tlsHosts", [])
    if not isinstance(host, str) or not host:
        raise RuntimeError("values file has no site.primaryHost")
    if host not in tls_hosts:
        raise RuntimeError("site.primaryHost is not covered by ingress.edge.tlsHosts")
    return host


def smoke(host: str) -> str:
    origin = f"https://{host}"
    api_query = urlencode(
        {
            "action": "query",
            "meta": "siteinfo",
            "siprop": "general",
            "format": "json",
        }
    )
    api_payload, _ = request(f"{origin}/w/api.php?{api_query}")
    general = json.loads(api_payload)["query"]["general"]
    if general.get("sitename") != "WikiApiary":
        raise RuntimeError(f"unexpected sitename: {general.get('sitename')!r}")
    reported_host = urlparse(general.get("base", "")).hostname
    if reported_host != host:
        raise RuntimeError(f"MediaWiki reports canonical host {reported_host!r}, expected {host!r}")

    _, first_headers = request(f"{origin}/wiki/Main_Page")
    _, second_headers = request(f"{origin}/wiki/Main_Page")
    cache_status = second_headers.get("X-WikiApiary-Cache", "").upper()
    cache_control = second_headers.get("Cache-Control", "").lower()
    if cache_status != "HIT":
        first_status = first_headers.get("X-WikiApiary-Cache", "unknown")
        raise RuntimeError(
            f"homepage cache did not reach HIT (first={first_status}, second={cache_status or 'missing'})"
        )
    if "no-store" in cache_control or "private" in cache_control:
        raise RuntimeError(f"homepage is not publicly cacheable: {cache_control!r}")
    return f"{origin} reports WikiApiary and homepage cache HIT"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--values", type=Path, default=Path("values/prod.yaml"))
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--delay", type=int, default=20)
    args = parser.parse_args()

    host = configured_host(args.values)
    last_error: Exception | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            result = smoke(host)
            print(f"production smoke passed: {result}")
            return
        except (HTTPError, URLError, KeyError, ValueError, RuntimeError) as error:
            last_error = error
            print(f"attempt {attempt}/{args.attempts} not ready: {error}", flush=True)
            if attempt < args.attempts:
                time.sleep(args.delay)
    raise SystemExit(f"production smoke failed after {args.attempts} attempts: {last_error}")


if __name__ == "__main__":
    main()
