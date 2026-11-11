#!/usr/bin/env python3
"""Small, sequential, read-only MediaWiki and BunkerWeb regression checks."""
from __future__ import annotations

import argparse
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    parser.add_argument("--routing-host", help="Host header for a private canary")
    parser.add_argument("--baseline", action="store_true", help="Skip attack probes")
    parser.add_argument("--ipv4", action="store_true", help="Use IPv4 when the test runner has no working IPv6 route")
    args = parser.parse_args()
    if args.ipv4:
        resolve = socket.getaddrinfo
        socket.getaddrinfo = lambda host, port, family=0, *rest, **kw: resolve(host, port, socket.AF_INET, *rest, **kw)
    class CanaryRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, message, headers, newurl):
            if args.routing_host:
                parsed = urllib.parse.urlsplit(newurl)
                if parsed.hostname not in {"dev.wikiapiary.com", "wikiapiary.dobriy.ai", urllib.parse.urlsplit(args.origin).hostname}:
                    raise ValueError("Canary redirected to an unexpected host")
                newurl = args.origin.rstrip("/") + urllib.parse.urlunsplit(("", "", parsed.path, parsed.query, parsed.fragment))
            return super().redirect_request(request, fp, code, message, headers, newurl)

    opener = urllib.request.build_opener(CanaryRedirect())
    results = []

    def check(name, path, *, data=None, status=200, ua=None, json_key=None, robots_for=None):
        headers = {"User-Agent": ua or "WikiApiary-Firewall-Validation/1.0 (+https://dev.wikiapiary.com)"}
        if args.routing_host:
            headers["Host"] = args.routing_host
        payload = urllib.parse.urlencode(data).encode() if data is not None else None
        request = urllib.request.Request(args.origin.rstrip("/") + path, payload, headers)
        try:
            response = opener.open(request, timeout=40)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            actual = response.status
            passed = actual == status
            if json_key and actual == 200:
                try:
                    passed = passed and json_key in json.loads(body)
                except ValueError:
                    passed = False
            if robots_for and actual == 200:
                robots = urllib.robotparser.RobotFileParser()
                robots.parse(body.decode("utf-8").splitlines())
                passed = passed and robots.can_fetch(robots_for, args.origin.rstrip("/") + "/wiki/Main_Page")
            results.append({"case": name, "status": actual, "expected": status, "passed": passed})
            print(json.dumps(results[-1]), flush=True)
        time.sleep(0.25)

    for name, path in [
        ("article", "/wiki/Main_Page"),
        ("login form", "/wiki/Special:UserLogin"),
        ("signup form", "/wiki/Special:CreateAccount"),
        ("edit form", "/w/index.php?title=Main_Page&action=edit"),
        ("upload form", "/wiki/Special:Upload"),
        ("search interface", "/w/index.php?title=Special:Search&search=WikiApiary"),
        ("semantic query interface", "/wiki/Special:Ask"),
        ("recent changes feed", "/w/index.php?title=Special:RecentChanges&feed=atom"),
        ("ResourceLoader CSS", "/w/load.php?modules=mediawiki.skinning.interface&only=styles&lang=en&skin=foreground"),
        ("ResourceLoader JS", "/w/load.php?modules=startup&only=scripts&lang=en&skin=foreground"),
        ("robots", "/robots.txt"),
    ]:
        check(name, path)
    for name, params, key in [
        ("siteinfo GET", {"action": "query", "meta": "siteinfo", "siprop": "general|statistics|extensions|skins"}, "query"),
        ("search API", {"action": "query", "list": "search", "srsearch": "WikiApiary", "srlimit": 1}, "query"),
        ("SMW ask", {"action": "ask", "query": "[[Category:Website]]|limit=1"}, "query"),
        ("login token", {"action": "query", "meta": "tokens", "type": "login"}, "query"),
    ]:
        params["format"] = "json"
        check(name, "/w/api.php?" + urllib.parse.urlencode(params), json_key=key)
    check("siteinfo POST", "/w/api.php", data={"action": "query", "meta": "siteinfo", "format": "json"}, json_key="query")
    samples = {
        "plain wikitext": "== Firewall validation ==\nA read-only preview with [[Main Page]] and '''bold''' text.",
        "HTML wikitext": '<div class="example">Example</div><script>alert(1)</script>',
        "SQL documentation": "<pre>SELECT * FROM websites WHERE name = 'example' OR 1=1;</pre>",
        "shell documentation": "<pre>curl https://example.org; cat /etc/passwd; php -r 'echo 1;'</pre>",
        "semantic markup": "[[Website URL::https://example.org]] {{#ask:[[Category:Website]]|limit=1}}",
    }
    for name, content in samples.items():
        check(name, "/w/api.php", data={"action": "parse", "text": content, "contentmodel": "wikitext", "prop": "text", "format": "json"}, json_key="parse")
    check("anonymous write denied by MediaWiki", "/w/api.php", data={"action": "edit", "title": "User:FirewallValidation/NoWrite", "text": "This must not be saved", "token": "invalid", "format": "json"}, json_key="error")
    check("unknown API action preserves JSON", "/w/api.php?action=notarealaction&format=json", json_key="error")
    check("missing article preserves 404", "/wiki/FirewallValidationNonexistent20261111", status=404)

    crawler_agents = (
        "Googlebot/2.1", "bingbot/2.0", "DuckDuckBot/1.1", "Applebot/0.1",
        "YandexBot/3.0", "Baiduspider/2.0", "PetalBot/1.0",
        "GPTBot/1.4", "OAI-SearchBot/1.4", "ChatGPT-User/1.0",
        "ClaudeBot/1.0", "Claude-SearchBot/1.0", "Claude-User/1.0",
        "Amazonbot/0.1", "CCBot/2.0", "Bytespider", "Diffbot/0.1",
        "meta-externalagent/1.1", "FacebookBot/1.0",
    )
    for ua in crawler_agents:
        check("crawler article " + ua, "/wiki/Main_Page", ua=ua)
        check("crawler robots policy " + ua, "/robots.txt", ua=ua, robots_for=ua)
    for ua in ("WikiApiary/2.0 (+https://dev.wikiapiary.com; contact: wikiapiary@dobriy.ai)", "curl/8.5", "Googlebot/2.1", "GPTBot/1.4", "OAI-SearchBot/1.4", "ChatGPT-User/1.0"):
        check("ordinary API client " + ua.split("/")[0], "/w/api.php?action=query&meta=siteinfo&format=json", ua=ua, json_key="query")

    if not args.baseline:
        for ua in ("sqlmap/1.8", "Nikto/2.5", "Nuclei/3.0", "zgrab/0.1", "masscan/1.3"):
            check("blocked scanner " + ua, "/wiki/Main_Page", ua=ua, status=403)
        for ua in ("Googlebot/2.1", "GPTBot/1.4", "OAI-SearchBot/1.4", "ChatGPT-User/1.0"):
            check("crawler UA does not bypass WAF " + ua, "/w/api.php?" + urllib.parse.urlencode({"action": "query", "meta": "siteinfo", "format": "json", "waf_probe": "<script>alert(1)</script>"}), ua=ua, status=403)
        for path in ("/.env", "/.git/config", "/wp-login.php", "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php"):
            check("scanner path " + path, path, status=403)
        for name, value in (("XSS", "<script>alert(1)</script>"), ("SQL injection", "1' OR '1'='1' --")):
            check("blocked " + name, "/w/api.php?" + urllib.parse.urlencode({"action": "query", "meta": "siteinfo", "format": "json", "waf_probe": value}), status=403)
        check("content exception does not exempt another field", "/w/api.php", data={"action": "parse", "text": samples["HTML wikitext"], "format": "json", "waf_probe": "<script>alert(1)</script>"}, status=403)
    failed = [result["case"] for result in results if not result["passed"]]
    print(json.dumps({"checks": len(results), "failed": failed}), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
