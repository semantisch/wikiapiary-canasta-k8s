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
blocking mode. The User-Agent list blocks scanning tools: sqlmap, Nikto,
Nuclei, zgrab and masscan. Search engines and AI crawlers are allowed,
including Google, Bing, DuckDuckGo, Apple, OpenAI and Anthropic clients.
Scanner paths such as `/.env`, `/.git/config` and `/wp-login.php` are denied.
There are no third-party IP, ASN or reverse-DNS blocklists in this policy.

MediaWiki APIs, search, feeds, ResourceLoader and ordinary clients remain
accessible. WikiApiary's crawler is not blocked. Crawler User-Agent strings
are not treated as authentication or granted a WAF bypass. OpenAI's
GPTBot, OAI-SearchBot and ChatGPT-User receive ordinary request inspection.
The existing robots.txt permits public articles while excluding internal
MediaWiki routes and special pages. It has no crawler-specific exclusions.

Meta's `meta-externalagent` is allowed with the same request inspection as
other crawlers. Its former Varnish-wide HTTP 429 restriction is removed at
the operator's request. The [October incident report](security-2026-10-24.md)
records why that historical safeguard existed. This change does not introduce
per-client rate limiting, which still requires the trusted client-IP work below.

Custom rules are generated separately for every accepted hostname, including
hosts added during a primary-host cutover. They exclude content attack
rules for explicitly named MediaWiki content and password fields, and specific
rule IDs on observed MediaWiki navigation and module parameters. Other
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

## MediaWiki rule tuning, 12 November 2026

The retained access and rule logs identified collisions with ordinary wiki
navigation. The new rules remove only the matching CRS rule targets:

- ResourceLoader module names with a restricted character set, including history modules.
- Article URLs ending in `.com`, which are handled by the article router.
- Imported `/Whois` subpage names in article, backlink, feed and login parameters.
- Semantic MediaWiki subject-browser JSON with its `dir` option and page names.
- Login and account return titles with nested navigation query strings.
- The filename-only PHP heuristic on the imported `A.I.M.$_(...)` article title.

All other rule targets remain active, including the other parameters on the
same request. No User-Agent gains an inspection bypass. The read-only
`scripts/smoke-firewall-mediawiki.py` suite pairs normal requests with XSS probes
and checks exception boundaries, traversal and shell substitution. Run it
against each public hostname after the standard firewall suite.

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
code examples, search and AI crawler access, robots.txt permissions, blocked
scanners and injection probes. Spoofed crawler names must not bypass the WAF.
Run sequentially:

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

## Public rollout results, 11 November 2026

The initial rollout below used a broader crawler blacklist. The follow-up
policy removes search and AI crawlers from that blacklist, preserving scanner
blocking and all request inspection. The expanded regression suite checks
article access and robots.txt permissions for 18 crawler User-Agent strings,
including GPTBot, OAI-SearchBot and ChatGPT-User, and checks attack denial
with crawler names. It also verifies the pre-existing Meta crawler safeguard.

[PR 74](https://github.com/semantisch/wikiapiary-canasta-k8s/pull/74) deployed
the correction as `6746d5c185157566a41bee28eda18d337bd5f71e`. Argo CD reported
Synced and Healthy, and both BunkerWeb replicas loaded the scanner-only
User-Agent blacklist with CRS still enabled. All 84 regression checks then
passed on each public hostname. The full User-Agent examples published in
[OpenAI's crawler documentation](https://developers.openai.com/api/docs/bots)
for GPTBot, OAI-SearchBot and ChatGPT-User also returned HTTP 200 and cache HIT
on both hosts. Cache automation health and API host identity checks passed.

[PR 72](https://github.com/semantisch/wikiapiary-canasta-k8s/pull/72) deployed
commit `e10d94280cea0c30ecbbcd003d2368d3a99b7d5e`. Argo CD reported Synced and
Healthy, and both BunkerWeb replicas passed configuration tests and reloaded.

- All 39 HTTP checks passed through each public HTTPS hostname.
- All nine authenticated checks passed on each hostname. The dev-host upload
  staged a valid 10,832,793-byte PNG through ingress-nginx, the privacy gateway,
  BunkerWeb and MediaWiki. No file was published.
- Homepage cache HIT, public cache headers, API host identity and cache-worker
  health passed on both hosts. Logged-in responses used PASS and no-store.
- Desktop and mobile checks loaded the homepage, logo, footer images,
  ResourceLoader, login and exact-title search. Reading with JavaScript disabled
  remained available. No homepage image failures or horizontal overflow occurred.
- Public browser login, edit save and readback, and logout succeeded after
  rejecting optional analytics.
- The controller remained near 100 MiB with no restarts after the namespace
  patch. Watches now seed from the collection resource version and resume after
  normal timeouts, avoiding repeated initial-object replay.

Two pre-existing application problems were reproduced through a direct Caddy
port-forward, bypassing BunkerWeb and the privacy gateway:

1. Full-text `Special:Search` for `MediaWiki` throws a
   `Wikimedia\Assert\PreconditionException`. Imported rows contain reserved
   namespace prefixes inside namespace 0, for example
   `Extension:Semantic_MediaWiki`. Core SQL search cannot treat those titles as
   proper page identities. The old edge error interception hid the 500 behind
   a generic 404. This requires a separate, backed-up namespace-data repair.
2. `/wiki/WikiApiary` references `Chart` without loading its definition. The
   resulting chart error also occurs directly at the backend. The search error
   page additionally triggers an OOUI `Widget not found` error.

These findings mean this rollout does not establish that every existing wiki
function is healthy. They are not WAF false positives. No imported content was
rewritten as part of the firewall change.

The hosting control plane also had intermittent API outages during the work.
Validation used an available control-plane peer without modifying the user's
kubeconfig. A transient run of canary POST checks received 503 responses during
an outage. The repeated complete canary run and both public runs subsequently
passed. Broad hosting-cluster remediation is outside this change.

Cleanup removed the temporary canary ingress, its two ConfigMaps, the diagnostic
route, the validation user subpage and all three staged uploads. The test account
has no explicit groups, its password was replaced with a discarded random value,
and its sessions were invalidated. Local test credentials were deleted.

Operational evidence is under
`/srv/workspace/users/1000/wikiapiary-bunkerweb-20261111/evidence`.

## Rollback

Revert the WikiApiary policy commit and let Argo CD reconcile. Leave the
existing protected routing chain in place. If a particular request is a false
positive, first identify the exact CRS rule and argument. Prefer a narrow
field exception over disabling inspection for the entire API or trusting a
User-Agent. Verify both public aliases and both proxy replicas after changing
the policy.
