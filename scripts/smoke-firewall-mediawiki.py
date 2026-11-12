#!/usr/bin/env python3
"""Read-only regression cases for observed MediaWiki WAF collisions."""
import argparse
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def cases():
    params = json.dumps({"subject": "!_(Video_Game)_Wiki", "ns": 0, "iw": "",
                         "subobject": "", "options": {"dir": None, "lang": "en",
                         "group": None, "offset": None}, "type": "html"})
    benign = [
        ("Bulk revision titles", "/w/api.php", {"action": "query", "prop": "revisions", "rvprop": "ids", "titles": "Main Page|Script Gallerie Photos de Carlito (albumphoto.charles-gaudon.com)", "format": "json"}, "GET"),
        ("ResourceLoader history module", "/w/load.php", {"modules": "mediawiki.action.history", "only": "scripts", "lang": "en"}, "GET"),
        ("Whois article", "/w/index.php", {"title": "Sveti_Vlas/Whois"}, "GET"),
        ("Whois backlinks", "/w/index.php", {"title": "Special:WhatLinksHere", "target": "Sveti_Vlas/Whois", "limit": "1"}, "GET"),
        ("Whois feed", "/w/api.php", {"action": "feedrecentchanges", "target": "Sveti_Vlas/Whois", "feedformat": "atom", "limit": "1"}, "GET"),
        ("Whois login return", "/w/index.php", {"title": "Special:UserLogin", "returnto": "Sveti_Vlas/Whois"}, "GET"),
        ("SMW subject JSON", "/w/api.php", {"action": "smwbrowse", "browse": "subject", "params": params, "format": "json"}, "POST"),
        ("Login history query", "/w/index.php", {"title": "Special:UserLogin", "returnto": "Main_Page", "returntoquery": "action=history&offset=20171030191406%7C3939931&limit=50"}, "GET"),
        ("Account browse query", "/w/index.php", {"title": "Special:CreateAccount", "returnto": "Special:Browse", "returntoquery": "offset=0&dir=both&article=ZDXPedia%2FNamespaces&group=hide"}, "GET"),
        ("Login exclamation title", "/w/index.php", {"title": "Special:UserLogin", "returnto": "Special:Browse/:Snap!-20Wiki-23Extension-5FGuidedTour"}, "GET"),
        ("Login ampersand title", "/w/index.php", {"title": "Special:UserLogin", "returnto": "Blackheat Freeroam & RP Wiki/Skins"}, "GET"),
        ("Article with .com suffix", "/wiki/Wiki.GIS.com", {}, "GET"),
        ("Dollar sign article title", "/wiki/" + urllib.parse.quote("A.I.M.$_(エイムズ)_Wiki", safe=""), {}, "GET"),
    ]
    for name, path, query, method in benign:
        yield name, path, query, method, False
    for name, path, query, method in benign:
        yield "XSS still denied: " + name, path, {**query, "waf_probe": "<script>alert(1)</script>"}, method, True
    yield "ResourceLoader traversal denied", "/w/load.php", {"modules": "../../etc/passwd"}, "GET", True
    yield "SMW exception restricted to action", "/w/api.php", {"action": "query", "params": params}, "POST", True
    yield "Whois title shell substitution denied", "/w/index.php", {"title": "$(id)/Whois"}, "GET", True
    yield "SMW params XSS denied", "/w/api.php", {"action": "smwbrowse", "browse": "subject", "params": '{"subject":"<script>alert(1)</script>","options":{"dir":null}}'}, "POST", True
    yield "Login return XSS denied", "/w/index.php", {"title": "Special:UserLogin", "returnto": "<script>alert(1)</script>"}, "GET", True
    yield "Non-wiki executable suffix denied", "/probe.com", {}, "GET", True
    yield "Bulk title exception requires revision property", "/w/api.php", {"action": "query", "prop": "info", "titles": "Main Page|Script Gallerie Photos de Carlito"}, "GET", True
    yield "Bulk title exception excludes other arguments", "/w/api.php", {"action": "query", "prop": "revisions", "titles": "Main Page", "waf_probe": "Main Page|Script Gallerie Photos de Carlito"}, "GET", True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    parser.add_argument("--routing-host")
    parser.add_argument("--ipv4", action="store_true")
    args = parser.parse_args()
    if args.ipv4:
        resolve = socket.getaddrinfo
        socket.getaddrinfo = lambda host, port, family=0, *rest, **kw: resolve(host, port, socket.AF_INET, *rest, **kw)

    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if args.routing_host:
                parsed = urllib.parse.urlsplit(newurl)
                if parsed.hostname not in {"dev.wikiapiary.com", "wikiapiary.dobriy.ai", args.routing_host}:
                    raise ValueError("Unexpected canary redirect host")
                newurl = args.origin.rstrip("/") + urllib.parse.urlunsplit(("", "", parsed.path, parsed.query, ""))
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(Redirect())
    failed = []
    total = 0
    for name, path, query, method, deny in cases():
        url = args.origin.rstrip("/") + path
        payload = urllib.parse.urlencode(query).encode()
        headers = {"User-Agent": "WikiApiary-MediaWiki-WAF-Regression/1.0"}
        if args.routing_host:
            headers["Host"] = args.routing_host
            headers["X-Forwarded-Proto"] = "https"
        if method == "GET":
            url += ("?" + payload.decode()) if payload else ""
            payload = None
        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            response = opener.open(request, timeout=40)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
        passed = status == 403 if deny else status in {200, 404} and bool(body)
        if not deny and name == "SMW subject JSON" and status == 200:
            try:
                passed = "query" in json.loads(body)
            except ValueError:
                passed = False
        if not deny and name == "Whois feed":
            try:
                passed = status == 200 and ET.fromstring(body).tag == "{http://www.w3.org/2005/Atom}feed"
            except ET.ParseError:
                passed = False
        if not passed:
            failed.append(name)
        total += 1
        print(json.dumps({"case": name, "status": status, "expected": "403" if deny else "MediaWiki response", "passed": passed}), flush=True)
        time.sleep(0.25)
    print(json.dumps({"checks": total, "failed": failed}), flush=True)
    raise SystemExit(bool(failed))


if __name__ == "__main__":
    main()
