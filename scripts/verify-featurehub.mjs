// PLAYWRIGHT_MODULE may point to an existing installation outside this repo.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import fs from 'node:fs/promises';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const preview = process.argv.includes('--preview');
const origin = process.env.WIKIAPIARY_ORIGIN || 'https://wikiapiary.dobriy.ai';
const output = 'artifacts/featurehub';
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: chromium.executablePath() });
const results = [];
async function pageFor(viewport, blocked = false) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  page.setDefaultNavigationTimeout(60000);
  if (preview) {
    await page.route(origin + '/wiki/Main_Page', async route => {
      const response = await route.fetch();
      let html = await response.text();
      html = html.replace(/<a id="wikiapiary-feedback"[\s\S]*?<\/a>/, '');
      const css = await fs.readFile('charts/canasta/files/foreground/wikiapiary.css', 'utf8');
      const js = await fs.readFile('charts/canasta/files/foreground/wikiapiary-feedback.js', 'utf8');
      html = html.replace('</head>', '<style>' + css + '</style></head>');
      html = html.replace('</body>', '<a id="wikiapiary-feedback" role="button" aria-haspopup="dialog" aria-expanded="false" href="https://featurehub.dobriy.ai/embed/wikiapiary"><img src="/w/images/wikiapiary/thumb/5/5e/WikiApiary_Bee.png/128px-WikiApiary_Bee.png" alt="" width="28" height="28"><span>Feedback</span></a><script>' + js + '</script></body>');
      await route.fulfill({ response, body: html });
    });
  }
  if (blocked) await page.route('https://featurehub.dobriy.ai/widget.js', route => route.abort());
  return { context, page };
}
try {
  for (const width of [1440, 390]) {
    const { context, page } = await pageFor({ width, height: 900 });
    const errors = [], requests = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (r.url().startsWith('https://featurehub.dobriy.ai/')) requests.push(r.url()); });
    await page.goto(origin + '/wiki/Main_Page', { waitUntil: 'domcontentloaded' });
    const trigger = page.locator('#wikiapiary-feedback');
    await trigger.waitFor();
    await page.waitForFunction(() => document.querySelector('#wikiapiary-feedback')?.dataset.bound === 'true');
    assert.equal(requests.length, 0, 'Feedback must not make requests before opening');
    await page.screenshot({ path: output + '/tab-' + width + (preview ? '-preview' : '') + '.png' });
    await trigger.click();
    const frame = page.frameLocator('#featurehub-widget iframe');
    await frame.locator('textarea').first().waitFor();
    const logo = frame.locator('img[alt="WikiApiary"]');
    await logo.waitFor();
    assert(await logo.evaluate(el => el.complete && el.naturalWidth > 0));
    assert.equal(await frame.locator('.fh-widget > header').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(255, 245, 204)');
    assert.equal(await page.locator('#featurehub-widget').count(), 1);
    assert.equal(await page.locator('#featurehub-widget .tab').isVisible(), false);
    assert.equal(await frame.locator('.fh-widget > footer').count(), 0);
    assert.equal(await trigger.getAttribute('aria-expanded'), 'true');
    assert(await frame.getByText('Add image', { exact: true }).isVisible());
    assert(await frame.getByRole('button', { name: 'Select element', exact: true }).isVisible());
    assert(await frame.getByRole('button', { name: 'Select area', exact: true }).isVisible());
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert(await frame.locator('body').evaluate(el => el.scrollWidth <= innerWidth));
    await page.screenshot({ path: output + '/form-' + width + (preview ? '-preview' : '') + '.png' });
    // Attach a real image, then remove it without submitting a request.
    await frame.locator('input[type=file]').setInputFiles(output + '/wikiapiary-logo.png');
    await frame.getByAltText('Attachment preview').waitFor();
    await frame.getByRole('button', { name: 'Remove image' }).click();
    assert.equal(await frame.getByAltText('Attachment preview').count(), 0);
    if (width === 1440) {
      // Capture a selected page element and a rectangle, then remove both previews.
      await frame.getByRole('button', { name: 'Select element', exact: true }).click();
      await page.locator('#featurehub-widget .pick').waitFor();
      await page.mouse.move(170, 30);
      await page.mouse.click(170, 30);
      await frame.getByAltText('Attachment preview').waitFor();
      await frame.getByRole('button', { name: 'Remove image' }).click();
      await frame.getByRole('button', { name: 'Select area', exact: true }).click();
      await page.locator('#featurehub-widget .pick').waitFor();
      await page.mouse.move(80, 8);
      await page.mouse.down();
      await page.mouse.move(260, 55, { steps: 6 });
      await page.mouse.up();
      await frame.getByAltText('Attachment preview').waitFor();
      await frame.getByRole('button', { name: 'Remove image' }).click();
      results.push({ captureElement: true, captureArea: true });
    }
    // A forged close message from the host must not bypass the origin/source check.
    await page.evaluate(() => window.postMessage({ type: 'featurehub:close' }, location.origin));
    assert(await page.locator('#featurehub-widget dialog').isVisible());
    await frame.locator('textarea').first().press('Escape');
    await page.waitForFunction(() => document.querySelector('#wikiapiary-feedback').getAttribute('aria-expanded') === 'false');
    assert(await trigger.evaluate(el => el === document.activeElement));
    await trigger.press('Space');
    await page.locator('#featurehub-widget dialog').waitFor();
    assert.equal(requests.filter(x => x.endsWith('/widget.js')).length, 1);
    await page.locator('#featurehub-widget').getByRole('button', { name: 'Close', exact: true }).click();
    assert.deepEqual(errors.filter(x => /featurehub|wikiapiary-feedback/i.test(x)), []);
    results.push({ width, lazyLoading: true, logo: true, theme: true, uploads: true, keyboard: true, singleWidget: true, overflow: false, pageErrors: errors });
    await context.close();
  }
  const { context, page } = await pageFor({ width: 1280, height: 900 }, true);
  await page.goto(origin + '/wiki/Main_Page', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelector('#wikiapiary-feedback')?.dataset.bound === 'true');
  await page.locator('#wikiapiary-feedback').click();
  await page.waitForURL('https://featurehub.dobriy.ai/embed/wikiapiary');
  await page.locator('textarea').first().waitFor();
  results.push({ blockedSdkFallback: true });
  await context.close();
  // Reproduce pre-release cached HTML, with no native feedback anchor.
  const legacy = await pageFor({ width: 1280, height: 900 });
  await legacy.page.route(origin + '/wiki/VideoLAN_Wiki/General', async route => {
    const response = await route.fetch();
    let html = (await response.text()).replace(/<a id="wikiapiary-feedback"[\s\S]*?<\/a>/, '');
    if (preview) {
      const js = await fs.readFile('charts/canasta/files/foreground/wikiapiary-feedback.js', 'utf8');
      html = html.replace('</body>', '<script>' + js + '</script></body>');
    }
    await route.fulfill({ response, body: html });
  });
  await legacy.page.goto(origin + '/wiki/VideoLAN_Wiki/General', { waitUntil: 'domcontentloaded' });
  await legacy.page.waitForFunction(() => document.querySelector('#wikiapiary-feedback')?.dataset.bound === 'true');
  assert.equal(await legacy.page.locator('#wikiapiary-feedback').count(), 1);
  await legacy.page.locator('#wikiapiary-feedback').click();
  await legacy.page.frameLocator('#featurehub-widget iframe').locator('textarea').first().waitFor();
  results.push({ olderCachedPage: true });
  await legacy.context.close();
  await fs.writeFile(output + '/validation' + (preview ? '-preview' : '') + '.json', JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results));
} finally {
  await browser.close();
}
