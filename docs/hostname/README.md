# Change the WikiApiary hostname

The hostname is controlled in one file: [`values/prod.yaml`](../../values/prod.yaml).

## Switch the main hostname to `wikiapiary.com`

1. Point the DNS records for `wikiapiary.com` at the same load balancer as
   `wikiapiary.dobriy.ai`. At the time of writing these are:

   - A: `138.199.129.254`
   - AAAA: `2a01:4f8:c01e:12e5::1`

   Check that those addresses are still current before changing DNS, then wait
   until public DNS resolvers return them.

2. Change exactly one line in `values/prod.yaml`:

   ```diff
    site:
   -  primaryHost: wikiapiary.dobriy.ai
   +  primaryHost: wikiapiary.com
   ```

   Do not change Caddy, MediaWiki, ingress rules, cache settings,
   `site.additionalHosts`, or `ingress.edge.tlsHosts`.

3. Open a pull request, wait for the `Validate / Helm and policy` check to pass,
   and merge it into `main`.

4. Wait for the `Production / Observe GitOps deployment` workflow to pass.
   This confirms HTTPS, MediaWiki, and the cache on every configured hostname.

5. Verify publicly:

   ```bash
   curl --fail --silent --show-error --head https://wikiapiary.com/
   curl --fail --silent --show-error \
     'https://wikiapiary.com/w/api.php?action=query&meta=siteinfo&format=json'
   curl --fail --silent --show-error --head https://wikiapiary.dobriy.ai/
   ```

That is the complete switch. The chart automatically updates the routes,
certificate, application hostname, pod rollouts, and cache warmers. The old
hostname stays available because it is retained in `ingress.edge.tlsHosts`.

## Add another mirror instead

Point the mirror's A and AAAA records at the same load balancer, then add only
the hostname under `site.additionalHosts`:

```yaml
site:
  additionalHosts:
    - dev.wikiapiary.com
    - mirror.example.org
```

After the pull request is merged, the mirror receives its own certificate,
serves pages on its own hostname without redirecting, and gets its own warmed
cache entries.

## Roll back

Change `site.primaryHost` back to `wikiapiary.dobriy.ai`, open and merge the
rollback pull request, and wait for the production workflow to pass. Do not
remove either DNS record during rollback.
