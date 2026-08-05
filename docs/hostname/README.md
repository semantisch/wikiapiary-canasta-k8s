# Changing the WikiApiary hostname

The production chart is designed so a canonical-host cutover changes exactly
one Git value: `site.primaryHost` in [`values/prod.yaml`](../../values/prod.yaml).
Do not edit ingress rules, TLS lists, MediaWiki configuration, Caddy, job
runners, cache automation, Argo CD, workflows, or README links in the cutover
pull request.

## How hostname derivation works

| Value | Behavior |
| --- | --- |
| `site.primaryHost` | Canonical application origin; always routed and automatically included on the edge certificate |
| `site.additionalHosts` | Additional route-only aliases that do not automatically expand the public certificate |
| `ingress.edge.tlsHosts` | Retained certificate aliases; these are also routed through MediaWiki and Caddy |

The production values intentionally keep `wikiapiary.dobriy.ai` in
`ingress.edge.tlsHosts`. It is redundant while that name is primary, but it
preserves the old hostname, route, and certificate SAN automatically after
`wikiapiary.com` becomes primary.

CI renders a synthetic `wikiapiary.com` cutover by overriding only
`site.primaryHost`. It verifies the resulting MediaWiki identity, Caddy
listeners and upstream host, internal and edge ingress rules, certificate SANs,
job runners, cache automation, and pod checksums.

## Before merging the cutover

DNS is the only required change outside Git.

1. Prepare a pull request containing the one-line values change shown below and
   wait for CI to pass.
2. Lower the `wikiapiary.com` DNS TTL early enough for existing records to expire.
3. Immediately before merging, point the `wikiapiary.com` A and, if used, AAAA
   records at the production edge load balancer.
4. Confirm public resolvers return only the intended load-balancer addresses.
5. Merge the prepared pull request. Do not merge while the hostname still points
   at another service: cert-manager must be able to complete the ACME challenge
   through this cluster.

The new certificate is requested as part of reconciliation. A short issuance
interval is therefore expected; the production observation workflow retries for
up to 15 minutes and fails visibly if HTTPS, MediaWiki identity, or cache behavior
does not converge.

## The complete Git change

Change only this line in `values/prod.yaml`:

```diff
 site:
-  primaryHost: wikiapiary.dobriy.ai
+  primaryHost: wikiapiary.com
```

Do not remove `wikiapiary.dobriy.ai` from `ingress.edge.tlsHosts`: that entry is
what retains the previous hostname as a certificate-covered alias.

Run [local validation](../../README.md#local-validation), open the pull request,
and confirm `Validate / Helm and policy` succeeds. After merge, Argo CD applies
the new primary identity and cert-manager updates the existing edge certificate
to cover both the new primary hostname and retained TLS aliases.

## Post-cutover checks

- Open the homepage and a representative article on `wikiapiary.com`.
- Query `/w/api.php?action=query&meta=siteinfo&format=json` and confirm the
  reported server is `https://wikiapiary.com`.
- Confirm `/wiki/Special:ApiSandbox` is reachable.
- Confirm an anonymous cacheable page produces a Varnish cache HIT.
- Confirm `wikiapiary.dobriy.ai` remains reachable as an alias.
- Check that web, Caddy, job-runner, and cache-automation workloads are healthy.
- Keep the old hostname available through a monitoring period so bots, crawlers,
  bookmarks, and integrations can migrate.

## Rollback

Rollback is also a one-line change:

```diff
 site:
-  primaryHost: wikiapiary.com
+  primaryHost: wikiapiary.dobriy.ai
```

Merge the rollback pull request and retain the new DNS record until production
validation passes. The configured retained TLS alias ensures the old hostname
is already present on the edge certificate.

Redirect policy should be added only in a later reviewed change after traffic
and crawler behavior are understood.
