# Changing the WikiApiary hostname

This runbook changes WikiApiary's canonical public hostname without breaking
TLS issuance, aliases, MediaWiki identity, job runners, or cache warming. Use two
pull requests so certificate preparation and the canonical-host change remain
separate and independently reversible.

## Where the hostname is configured

The production source of truth is [`values/prod.yaml`](../../values/prod.yaml):

| Value | Purpose |
| --- | --- |
| `site.primaryHost` | Canonical MediaWiki origin and default host used by application workloads |
| `site.additionalHosts` | Temporary or permanent aliases routed to the same application |
| `ingress.edge.tlsHosts` | Hostnames included on the edge certificate |

Helm derives MediaWiki, Caddy, ingress, job-runner, Semantic MediaWiki, and
cache-automation configuration from these values. Do not add hostname literals
to generated configuration or edit `argocd/wikiapiary.yaml` for a hostname
change. The live API links in the repository's main README are documentation and
must be changed to the new canonical origin in the canonical-host pull request.

## Before making changes

1. Confirm the new DNS name and the edge load-balancer address.
2. Lower the DNS TTL early enough for cached records to expire before cutover.
3. Decide whether `www` or any other alias will be supported and include it in
   both the alias and TLS lists if so.
4. Keep the old canonical hostname available throughout rollout and monitoring.

## Pull request 1: prepare DNS, routing, and TLS

Point the new hostname at the existing edge load balancer. Confirm both A and
AAAA behavior wherever both record types are published. Do not request the
certificate before DNS reaches this load balancer; the ACME challenge may fail.

Keep the current primary host, then add the new hostname to both the alias and
TLS lists in `values/prod.yaml`:

```yaml
site:
  primaryHost: wikiapiary.dobriy.ai
  additionalHosts:
    - dev.wikiapiary.com
    - wikiapiary.com

ingress:
  edge:
    tlsHosts:
      - wikiapiary.dobriy.ai
      - wikiapiary.com
```

Run the [local validation](../../README.md#local-validation), open the first pull
request, and merge it after review. Then verify:

- DNS resolves the new hostname to the intended load balancer;
- cert-manager reports the certificate ready;
- HTTPS reaches WikiApiary on both the old and new names;
- the old hostname remains canonical at this stage.

## Pull request 2: change the canonical host

Make the new name primary and preserve the old name as an alias:

```yaml
site:
  primaryHost: wikiapiary.com
  additionalHosts:
    - wikiapiary.dobriy.ai
    - dev.wikiapiary.com
```

Keep every routed hostname in `ingress.edge.tlsHosts`. Update the live API links
in the main README from the old origin to the new canonical origin. No literal
MediaWiki, Caddy, cache-warmer, job-runner, Argo CD, or workflow hostname edits
should be necessary.

Run local validation and open the second pull request. CI renders the exact
cutover shape and checks canonical origin, application environment, listeners,
upstream `Host` handling, ingress rules, and TLS coverage. After merge, the
production workflow waits until the MediaWiki API reports the new canonical host
and the homepage returns a cache HIT.

## Post-cutover checks

- Open the homepage and a representative article on the canonical hostname.
- Query `/w/api.php?action=query&meta=siteinfo&format=json` and confirm the
  reported server and article paths use the new origin.
- Confirm `/wiki/Special:ApiSandbox` is reachable.
- Confirm an anonymous cacheable page produces a Varnish cache HIT.
- Check that job runners and cache-automation workloads remain healthy.
- Keep the old hostname as an alias through a monitoring period so bots,
  crawlers, bookmarks, and integrations can migrate.

## Rollback

Revert `site.primaryHost` to the old hostname, keep both hosts in
`site.additionalHosts` and `ingress.edge.tlsHosts`, and merge the rollback pull
request. Argo CD will reconcile the old canonical identity. Retain the new DNS
record until rollback validation passes.

Redirect policy should be added only in a later reviewed change after traffic
and crawler behavior are understood.
