# WikiApiary feedback

The native Foreground skin renders the bee-branded Feedback tab. Opening it
loads the existing FeatureHub SDK and the WikiApiary form. The tab is also a
working link to the standalone form when JavaScript is disabled. SDK failure
falls back to that same form. Closing the panel restores keyboard focus.

The board is https://featurehub.dobriy.ai/p/wikiapiary. Its registered origins
are `https://wikiapiary.dobriy.ai` and `https://dev.wikiapiary.com`. The board,
original bee logo and scoped form stylesheet are maintained in
`semantisch/dobriyai-featurehub`, including `scripts/provision-wikiapiary.py`
and `scripts/deploy-wikiapiary-colours.py`. Provisioning is idempotent and
rejects a conflicting organisation or origin registration.

The integration sends no wiki account identity. Page context is restricted to
the origin, excluding titles, paths and query strings. The visitor chooses
whether to attach an image, capture a page element or capture an area. The
shared SDK masks inputs, editable fields and explicitly private elements.
Reports default to private. Optional email and update subscription remain
unchecked. The embedded form does not load optional analytics.

The wiki's header, layout and tab colours remain native PHP/CSS. Only opening
the optional feedback panel requires the external SDK. FeatureHub's scoped
stylesheet styles its own iframe, without changing other applications.
Previously cached HTML can acquire the same optional tab when the updated
native script loads. This avoids invalidating the entire article cache.

## Validation

Run the chart validations from README. Browser verification uses Playwright:

```sh
node scripts/verify-featurehub.mjs --preview
node scripts/verify-featurehub.mjs
```

Set `PLAYWRIGHT_MODULE` to an existing Playwright installation if needed. Set
`WIKIAPIARY_ORIGIN` to verify the retained dev hostname. The preview intercepts
only the homepage HTML in the test browser. All form requests reach the real
FeatureHub service. Tests cover desktop/mobile layout, no background feedback
requests, logo and palette, image upload, capture, keyboard operation, message
origin protection, single mounting and blocked-SDK fallback. These checks do
not submit feedback. Screenshots and results are written under the ignored
`artifacts/featurehub` directory. Supply `wikiapiary-logo.png` there as the
upload fixture before running.

Deploy through the normal reviewed GitOps release. Refresh the homepage and
warm both cache replicas after the web rollout, retaining homepage grace.
Invalidate only `/w/load.php` objects on each ready Varnish replica with
`varnishadm ban 'req.url ~ ^/w/load[.]php'`. Startup and stylesheet URLs can
otherwise keep the previous resource definitions. Do not flush all cached
wiki pages just to publish this integration.

The 12 November 2026 deployment passed desktop/mobile browser checks and a
real private submission with an image. Replaying its idempotency key returned
the same request ID. An unrelated visitor received 404, the request stayed off
the public board, and storage contained only the site origin as page context.
Two private validation records were marked done with audit events. Neither had
an email address or subscribers, and no notification was requested.
