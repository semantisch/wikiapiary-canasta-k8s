# Social sharing preview

Both public hosts publish Open Graph and Twitter large-image metadata. Their
canonical origin is `site.primaryHost`, currently `wikiapiary.dobriy.ai`.
MediaWiki emits this in the initial HTML, including when JavaScript is disabled.
Special pages and edit actions do not receive the generic sharing card.

The 1200 by 630 JPEG is served at `/assets/wikiapiary-social-v1.jpg` directly by
Caddy from a Git-managed ConfigMap. It does not depend on PHP, login, uploads or
an external image provider. The image URL is absolute and uses the canonical
origin on both hosts. Existing page titles are escaped by MediaWiki's HTML helper.

The editable composition is `design/social-preview/index.html`. Render it at
1200 by 630 CSS pixels and device scale 1, after local fonts and images have
loaded. Export JPEG at quality 92 to
`charts/canasta/files/social/wikiapiary-social-v1.jpg`.
The wordmark and bee are the existing WikiApiary presentation artwork. Poppins
is the existing presentation font, distributed under the SIL Open Font License.

When changing the artwork, increment the versioned filename in the chart,
Caddy route and metadata. The image is cached for one year. Refresh the relevant
HTML page cache after rollout. Social platforms may retain earlier URL previews
until their next scrape.

Validation for the initial release covered Helm lint, GitOps hostname cutover,
cache-warmer validation, PHP syntax, canonical metadata for both hosts, title
escaping, non-view exclusions, and Caddy configuration adaptation.
