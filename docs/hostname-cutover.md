# Canonical hostname cutover

The chart derives the application identity from `site.primaryHost`. Aliases in
`site.additionalHosts` are routed to the same application, while
`ingress.edge.tlsHosts` controls which names cert-manager places on the edge
certificate.

Use two pull requests so certificate issuance and canonical-host changes remain
separate and reversible.

## 1. Prepare DNS and TLS

Lower the DNS TTL ahead of the maintenance window. Point `wikiapiary.com` (and
`www.wikiapiary.com` only if it will also be supported) at the current edge load
balancer. Confirm both A and AAAA behavior where both records exist.

After DNS reaches the load balancer, open a preparation pull request that keeps
the current primary host but adds the new name as an alias and TLS host:

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

Merge it and verify that cert-manager reports a ready certificate and that an
HTTPS request to the new host reaches WikiApiary. Do not request the certificate
before DNS points at this load balancer; the ACME challenge may fail.

## 2. Change the canonical host

Open a second pull request that makes the new host primary and preserves the old
host as an alias:

```yaml
site:
  primaryHost: wikiapiary.com
  additionalHosts:
    - wikiapiary.dobriy.ai
    - dev.wikiapiary.com
```

No literal MediaWiki, Caddy, cache-warmer, or job-runner hostname edits should
be necessary. CI renders this exact cutover shape and checks the canonical
origin, application environment, listeners, upstream Host header, ingress rules,
and TLS coverage.

After merge, the production workflow waits until the MediaWiki API reports
`wikiapiary.com` as canonical and the homepage returns a cache HIT.

## Rollback

Revert `site.primaryHost` to `wikiapiary.dobriy.ai`, keep both hosts routed and on
the TLS certificate, and merge the rollback pull request. Argo CD will reconcile
the old canonical identity. Retain the new DNS record until rollback validation
passes.

Keep the old host as an alias through a monitoring period so bots, crawlers,
bookmarks, and external integrations have time to move. Redirect policy can be
added in a later reviewed change after traffic and crawler behavior are known.
