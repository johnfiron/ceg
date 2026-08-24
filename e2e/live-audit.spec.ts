import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const outDir = path.join('test-results', 'live-audit');
fs.mkdirSync(outDir, { recursive: true });

async function openLive(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(String(err)));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  await page.addInitScript(() => localStorage.setItem('ashIdle', 'pause'));
  await page.goto('/?intro=skip');
  await page.waitForFunction(() => {
    const home = document.getElementById('home');
    return !document.body.classList.contains('needs-keys') &&
      home && home.classList.contains('active') &&
      !document.getElementById('terminal')?.classList.contains('hidden');
  });
  await page.waitForFunction(() => {
    const open = document.getElementById('homeOpenTrades');
    const clock = document.getElementById('sessionClock');
    return open && clock && clock.textContent && clock.textContent !== '—' &&
      (open.querySelector('button, .metric') || /MACD|OPEN|No open paper trades\. The action/.test(open.textContent || ''));
  });
  return errors;
}

async function shot(page: Page, viewport: string, name: string) {
  const file = path.join(outDir, `${viewport}-${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

async function canvasInk(page: Page, selector: string) {
  return page.locator(selector).evaluate((c: HTMLCanvasElement) => {
    const w = c.width;
    const h = c.height;
    const g = c.getContext('2d');
    if (!g || w < 8 || h < 8) return { ok: false, w, h, ink: 0 };
    const data = g.getImageData(0, 0, w, h).data;
    let ink = 0;
    for (let i = 0; i < data.length; i += 16) {
      if (data[i + 3] > 20 && (data[i] > 24 || data[i + 1] > 24 || data[i + 2] > 24)) ink += 1;
    }
    return { ok: ink > 40, w, h, ink };
  });
}

async function pageAudit(page: Page) {
  return page.evaluate(() => {
    const vw = window.innerWidth;
    const tiny: string[] = [];
    const overflowX = document.documentElement.scrollWidth - vw;
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
    let n = 0;
    while (walk.nextNode() && n < 2500) {
      n += 1;
      const el = walk.currentNode as HTMLElement;
      if (!el.getBoundingClientRect || el.closest('.hidden,#intro,#bootOverlay')) continue;
      const style = getComputedStyle(el);
      if (style.display === 'none' || style.visibility === 'hidden') continue;
      const text = (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3) ? (el.textContent || '').trim() : '';
      if (text && parseFloat(style.fontSize) < 11 && !el.closest('.bootText')) {
        tiny.push(`${el.tagName}.${el.className} ${style.fontSize} "${text.slice(0, 40)}"`);
      }
    }
    const hits = [...document.querySelectorAll('.nav,.btn,.icon,button.activityTrade,button.tab,button.factButton,.watchRow')].map((el) => {
      const r = el.getBoundingClientRect();
      return { name: (el as HTMLElement).innerText.slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) };
    }).filter((x) => x.w && x.h && (x.w < 44 || x.h < 44));
    const nav = document.getElementById('nav')?.getBoundingClientRect();
    const covered = [...document.querySelectorAll('input,textarea')].filter((el) => {
      const r = el.getBoundingClientRect();
      return nav && r.height > 0 && r.bottom > nav.top + 2 && r.top < nav.bottom;
    }).map((el) => (el as HTMLElement).id || (el as HTMLElement).tagName);
    return {
      active: document.querySelector('.page.active')?.id,
      overflowX,
      tiny: tiny.slice(0, 20),
      smallHits: hits.slice(0, 20),
      covered,
      stale: document.getElementById('staleBanner')?.textContent || '',
      staleHidden: document.getElementById('staleBanner')?.classList.contains('hidden'),
      sessionPnl: document.getElementById('sessionPnl')?.textContent,
      clock: document.getElementById('sessionClock')?.textContent,
      watch: document.getElementById('watchlist')?.textContent,
      openHome: document.getElementById('homeOpenTrades')?.textContent,
      inspectTrades: document.getElementById('inspectTrades')?.textContent,
      actChip: document.getElementById('actSessionChip')?.textContent,
    };
  });
}

async function runAudit(page: Page, viewport: string) {
  const notes: Record<string, unknown> = {};
  const errors = await openLive(page);
  notes.bootErrors = errors.slice();
  notes.home = await pageAudit(page);
  expect(String(notes.home.openHome || ''), 'Home must show the open sleeve P&L').toMatch(/[+\-−]\$/);
  await shot(page, viewport, '01-home');

  await page.locator('#sessionDetails').evaluate((el: HTMLDetailsElement) => { el.open = true; });
  await page.waitForTimeout(400);
  notes.homeDetail = {
    health: await page.locator('#health').innerText().catch(() => ''),
    desk: await page.locator('#deskSummary').innerText().catch(() => ''),
  };
  await shot(page, viewport, '02-home-detail');

  await page.locator('.nav[data-page="activity"]').click();
  await expect(page.locator('#activity')).toHaveClass(/active/);
  await page.waitForTimeout(700);
  notes.activity = await pageAudit(page);
  notes.openRows = await page.locator('#openTradeRows').innerText();
  notes.closedRows = await page.locator('#tradeRows').innerText();
  notes.exceptionalRows = await page.locator('#failedTradeRows').innerText();
  notes.activitySummary = await page.locator('#activitySummary').innerText();
  await shot(page, viewport, '03-activity');

  const openRow = page.locator('#openTradeRows .activityTrade').first();
  if (await openRow.count()) {
    await openRow.click();
    await expect(page.locator('#tradeInspector')).toBeVisible();
    await page.waitForTimeout(900);
    notes.openInspector = {
      title: await page.locator('#tradeInspectorTitle').innerText(),
      sub: await page.locator('#tradeInspectorSub').innerText(),
      status: await page.locator('#tradeInspectorStatus').innerText(),
      expectation: await page.locator('#tradeExpectation').innerText(),
      contract: await page.locator('#tradeContract').innerText(),
      greeks: await page.locator('#tradeGreeks').innerText(),
      execution: await page.locator('#tradeExecution').innerText(),
      risk: await page.locator('#tradeRiskOutcome').innerText(),
      analysis: await page.locator('#tradeAnalysis').innerText(),
    };
    expect(notes.openInspector.analysis, 'Open inspector must use the live mark').toMatch(/\$/);
    await page.locator('summary:has-text("Signal, candidates")').click();
    await page.locator('summary:has-text("Audit timeline")').click();
    notes.openEvidence = await page.locator('#tradeEvidence').innerText();
    notes.openAudit = await page.locator('#tradeAudit').innerText();
    await shot(page, viewport, '04-inspector-open');
    await page.locator('#tradeInspectorBack').click();
    await expect(page.locator('#tradeInspector')).toBeHidden();
  }

  const closedRow = page.locator('#tradeRows .activityTrade').first();
  await closedRow.click();
  await expect(page.locator('#tradeInspector')).toBeVisible();
  await page.waitForTimeout(900);
  notes.closedInspector = {
    title: await page.locator('#tradeInspectorTitle').innerText(),
    expectation: await page.locator('#tradeExpectation').innerText(),
    execution: await page.locator('#tradeExecution').innerText(),
    risk: await page.locator('#tradeRiskOutcome').innerText(),
    analysis: await page.locator('#tradeAnalysis').innerText(),
  };
  expect(notes.closedInspector.expectation, 'Closed trades must not say OPEN for missing returns').not.toMatch(/ACTUAL OPTION RETURN\s+OPEN/);
  await shot(page, viewport, '05-inspector-closed');
  await page.keyboard.press('Escape');
  await expect(page.locator('#tradeInspector')).toBeHidden();

  await page.locator('#pnlReconciliation').evaluate((el: HTMLDetailsElement) => { el.open = true; });
  notes.reconciliation = await page.locator('#pnlReconciliationBody').innerText();
  await shot(page, viewport, '06-reconciliation');

  await page.locator('.nav[data-page="charts"]').click();
  await expect(page.locator('#charts')).toHaveClass(/active/);
  await page.waitForFunction(() => {
    const trades = document.getElementById('inspectTrades')?.textContent || '';
    const readout = document.getElementById('inspectReadout')?.textContent || '';
    const chip = document.getElementById('inspectChip')?.textContent || '';
    const busy = document.getElementById('inspectChart')?.getAttribute('aria-busy') === 'true';
    return /#\d+/.test(trades) && /\$/.test(readout) && /LOCAL TAPE · \d{4}/.test(chip) && !busy && !/No local minute bars yet/.test(readout);
  });
  await page.evaluate(() => {
    const draw = (window as unknown as { drawInspect?: () => void }).drawInspect;
    if (typeof draw === 'function') draw();
  });
  await page.evaluate(() => new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  }));
  notes.charts = await pageAudit(page);
  notes.chartTrades = await page.locator('#inspectTrades').innerText();
  notes.inspectTitle = await page.locator('#inspectTitle').innerText();
  notes.inspectChip = await page.locator('#inspectChip').innerText();
  notes.inspectSummary = await page.locator('#inspectSummary').innerText();
  expect(notes.inspectTitle, 'Charts should open on a booked ticker when no setup is live').toMatch(/QQQ|SPY|IWM|TSLA|META/);
  expect(notes.chartTrades, 'Open sleeve must stay on the inspect list').toMatch(/#12/);
  expect(notes.chartTrades, 'Open inspect row must show marked P&L').toMatch(/[+\-−]\$/);
  notes.inspectReadout = await page.locator('#inspectReadout').innerText();
  expect(notes.inspectReadout, 'Weekend inspect should fall back to the last session tape').not.toMatch(/No local minute bars yet/);
  notes.inspectCanvas = await canvasInk(page, '#inspectChart');
  expect(notes.inspectCanvas.ok, `Inspect canvas must have tape ink ${JSON.stringify(notes.inspectCanvas)}`).toBeTruthy();
  await shot(page, viewport, '07-charts');

  const chartTrade = page.locator('#inspectTrades .activityTrade').first();
  if (await chartTrade.count()) {
    await chartTrade.click();
    await expect(page.locator('#tradeInspector')).toBeVisible();
    await page.waitForTimeout(700);
    notes.chartInspector = await page.locator('#tradeInspectorTitle').innerText();
    await shot(page, viewport, '08-charts-inspector');
    await page.locator('#tradeInspectorBack').click();
    await expect(page.locator('#charts')).toHaveClass(/active/);
    await page.waitForTimeout(400);
  }

  await page.locator('.nav[data-page="strategies"]').click({ trial: false });
  await page.waitForFunction(() => document.getElementById('strategies')?.classList.contains('active'));
  await expect(page.locator('#strategies')).toHaveClass(/active/);
  await page.waitForFunction(() => (document.getElementById('strategyGrid')?.textContent || '').length > 40);
  notes.models = await pageAudit(page);
  notes.modelCards = (await page.locator('#strategyGrid').innerText()).slice(0, 400);
  await shot(page, viewport, '09-models');

  if (await page.locator('.nav[data-page="research"]').isVisible()) {
    await page.locator('.nav[data-page="research"]').click();
    await expect(page.locator('#research')).toHaveClass(/active/);
    await page.waitForFunction(() => (document.getElementById('labRows')?.querySelectorAll('tr').length || 0) > 0);
    notes.lab = await pageAudit(page);
    notes.labHint = await page.locator('#labHint').innerText();
    notes.labRows = (await page.locator('#labRows').innerText()).slice(0, 400);
    expect(notes.labRows, 'Lab table must use research_metrics rows').toMatch(/CEG|MACD|ORB|MVR|RSI2/);
    notes.labExtrasLazy = await page.locator('.labSection[data-loaded]').count();
    expect(notes.labExtrasLazy, 'Lab extras should remain lazy before disclosure').toBe(0);
    await shot(page, viewport, '10-lab');
  }

  await page.getByRole('button', { name: 'Open settings' }).click();
  await expect(page.locator('#settings')).toHaveClass(/active/);
  await page.waitForTimeout(500);
  notes.settings = await pageAudit(page);
  notes.settingsInfo = await page.locator('#settingsInfo').innerText();
  notes.orderCapability = await page.locator('#lanOrders').innerText();
  expect(notes.orderCapability, 'Settings must state explicit order capability').toMatch(/ARMED|DISABLED|INTERLOCK/);
  await shot(page, viewport, '11-settings');

  if (await page.locator('#ntfyUrl').isVisible()) {
    await page.locator('#ntfyUrl').focus();
    notes.settingsFocus = await pageAudit(page);
    await shot(page, viewport, '12-settings-focus');
  }

  fs.writeFileSync(path.join(outDir, `${viewport}-notes.json`), JSON.stringify(notes, null, 2));
  const real = errors.filter((e) => !/ResizeObserver|favicon/.test(e));
  expect(real, real.join('\n')).toEqual([]);
}

test('live desk audit across every surface', async ({ page }) => {
  test.skip(process.env.ASH_LIVE !== '1', 'live desk only');
  test.setTimeout(180_000);
  for (const vp of [
    { name: 'phone', width: 390, height: 844 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'desktop', width: 1280, height: 800 },
  ]) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await runAudit(page, vp.name);
  }
});
