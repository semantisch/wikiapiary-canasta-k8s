# WikiApiary BunkerWeb protection

Both `dev.wikiapiary.com` and `wikiapiary.dobriy.ai` already traversed BunkerWeb.
Their bot blacklist and OWASP Core Rule Set were disabled. This change enables
request protection on both hosts without changing the public routing chain:

```text
Hetzner load balancer → ingress-nginx → privacy gateway → BunkerWeb
                     → Canasta Caddy → Varnish → MediaWiki
```

## Policy

The production ingress enables BunkerWeb's blacklist and OWASP CRS 4 in
blocking mode. The reviewed User-Agent list blocks bulk crawlers including
GPTBot, ClaudeBot, Bytespider, CCBot, Amazonbot and common scanning tools.
Scanner paths such as `/.env`, `/.git/config` and `/wp-login.php` are denied.
There are no third-party IP, ASN or reverse-DNS blocklists in this policy.

MediaWiki APIs, search, feeds, ResourceLoader and ordinary clients remain
accessible. WikiApiary's crawler is not blocked. Search-engine User-Agent
strings are not treated as authentication or granted a WAF bypass.

Custom rules are generated separately for every accepted hostname, including
hosts added during a primary-host cutover. They only exclude content attack
rules for explicitly named MediaWiki content and password fields. Other
arguments on those same endpoints remain inspected. MediaWiki retains its
authentication, CSRF, permission and HTML sanitisation checks. Response-body
inspection is disabled because returned wiki articles intentionally contain
software examples and security documentation.

The proxy preserves application errors, including JSON errors and 404 pages.
Audit logging uses sections A, H and Z, excluding whole request/response
bodies and cookie headers. Matched rule messages can still contain snippets
of rejected input and must be treated as operational logs.

Both ingress-nginx and BunkerWeb allow 100 MiB request bodies, consistent with
the existing PHP post limit. BunkerWeb previously allowed 10 MiB. Non-file
request inspection allows 8 MiB, enough for URL-encoded articles within
MediaWiki's existing 2 MiB article limit. MediaWiki still enforces file types,
upload permissions and application size limits.

## Client-IP limitation

The load balancer currently presents `138.199.129.254` as every visitor's
address. A temporary diagnostic confirmed that `X-Original-Forwarded-For`
contains caller-supplied data, not an authenticated visitor address. Trusting
it would allow spoofing.

Per-IP rate limits, connection caps and behavioural IP bans remain disabled
to avoid blocking unrelated visitors together. JavaScript challenges remain
disabled so APIs, feeds and reading without JavaScript continue to work.
User-Agent blocking can be evaded by changing the header. CRS adds independent
request inspection, but this policy is not a claim that every automated client
can be identified or that volumetric attacks are solved. Per-visitor quotas
require a separately coordinated, trusted client-IP path through the shared
load balancer and ingress controller.

## Deployment and verification

Merge the Helm values and templates through the normal WikiApiary GitOps
workflow. Argo CD reconciles both site policies. Check the BunkerWeb scheduler
for successful configuration tests and reloads on both replicas, rather than
assuming that an ingress annotation has taken effect.

The shared controller also required recovery. Its namespace-scoped discovery
patch, tests and repeatable deployment instructions are in
[operations/bunkerweb-controller](../operations/bunkerweb-controller/README.md).
That shared Helm installation is managed separately from WikiApiary's Argo CD
application.

The read-only regression suite exercises normal MediaWiki requests, legitimate
code examples, blocked bots and injection probes. Run sequentially:

```bash
python3 scripts/smoke-firewall.py https://dev.wikiapiary.com --ipv4
python3 scripts/smoke-firewall.py https://wikiapiary.dobriy.ai --ipv4
python3 scripts/smoke-production.py
```

`--ipv4` is optional and useful for runners without a working IPv6 route.
`--baseline` skips attack probes before the policy is enabled. Private canary
tests can use a loopback port-forward with `--routing-host`.

Pre-rollout validation passed all 39 HTTP checks on each BunkerWeb replica.
Authenticated canary checks passed login, content save and readback, browser
edit-form preview, shared-cache bypass, a preview above 128 KiB, multipart
upload staging and logout. Validation uses a dedicated temporary account and
its own user subpage. Remove the test content, staged files and account access
after public validation. Do not use production administrator credentials.

## Rollback

Revert the WikiApiary policy commit and let Argo CD reconcile. Leave the
existing protected routing chain in place. If a particular request is a false
positive, first identify the exact CRS rule and argument. Prefer a narrow
field exception over disabling inspection for the entire API or trusting a
User-Agent. Verify both public aliases and both proxy replicas after changing
the policy.
