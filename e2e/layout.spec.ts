import { expect, test } from '@playwright/test';
import { boxOf, expectMinHit, openDesk } from './helpers';

test('primary chrome stays tappable and labeled', async ({ page }) => {
  await openDesk(page);
  await expect(page.locator('header.topbar')).toBeVisible();
  await expect(page.locator('main#terminal')).toBeVisible();
  await expect(page.locator('#home h1')).toHaveCount(1);
  await expect(page.locator('#nav')).toHaveAttribute('aria-label', 'Primary');
  await expect(page.locator('#sessionClock')).toHaveAttribute('aria-label', /New York market time/);
  await expect(page.locator('#heroChart')).toHaveAttribute('aria-label', 'ASH hero chart');
  await expectMinHit(page, '.nav[data-page="home"]');
  await expectMinHit(page, '.nav[data-page="activity"]');
  await expectMinHit(page, '.nav[data-page="charts"]');
  await expectMinHit(page, 'button[aria-label="Open settings"]');
  await expectMinHit(page, '#watchlist [data-ticker="SPY"]');
  const label = await page.locator('.nav[data-page="home"]').evaluate((el) => {
    const style = getComputedStyle(el);
    return parseFloat(style.fontSize);
  });
  expect(label).toBeGreaterThanOrEqual(11);
});

test('phone stays one column; desktop may add columns', async ({ page }) => {
  await openDesk(page);
  const width = page.viewportSize()?.width || 1280;
  const grid = await page.locator('#explainBox').evaluate((el) => getComputedStyle(el).display);
  expect(grid).toBeTruthy();
  if (width <= 850) {
    const watch = await boxOf(page, '#watchlist');
    const hero = await boxOf(page, '.heroChartFrame');
    expect(hero.height).toBeGreaterThanOrEqual(200);
    expect(watch.width).toBeGreaterThan(hero.width * 0.7);
    const columns = await page.locator('.timeHero').evaluate((el) => getComputedStyle(el).gridTemplateColumns);
    expect(columns.trim().split(/\s+/)).toHaveLength(1);
  } else {
    const hero = await boxOf(page, '.heroChartFrame');
    expect(hero.height).toBeGreaterThanOrEqual(200);
  }
});

test('keyboard opens Inspector and returns focus', async ({ page }) => {
  await openDesk(page);
  await page.locator('.nav[data-page="activity"]').click();
  await expect(page.locator('#activity')).toHaveClass(/active/);
  const row = page.locator('#tradeRows .activityTrade[data-id="12"]');
  await expect(row).toBeVisible();
  await expect(row).toHaveAttribute('aria-label', /Inspect trade 12 SPY/);
  await row.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#tradeInspector')).toBeVisible();
  await expect(page.locator('#tradeInspectorTitle')).toContainText('SPY');
  await expect(page.locator('#tradeExecution')).toContainText('Fees');
  await expect(page.locator('#tradeExecution')).toContainText('Modeled slippage');
  await expect(page.locator('#tradeRiskOutcome')).toContainText('Underlying beta');
  await expect(page.locator('#tradeUnderlyingSummary')).toContainText('Tape takeaway');
  await expect(page.locator('#tradeInspectorBack')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('#tradeInspector')).toBeHidden();
  await expect(row).toBeFocused();
});

test('charts list trades on this tape and route to Inspector', async ({ page }) => {
  await openDesk(page);
  await page.locator('.nav[data-page="charts"]').click();
  await expect(page.locator('#charts')).toHaveClass(/active/);
  await expect(page.getByText('TRADES ON THIS CHART')).toBeVisible();
  const row = page.locator('#inspectTrades .activityTrade').first();
  await expect(row).toBeVisible();
  await expect(row).toHaveAttribute('aria-label', /Open trade 12 inspector/);
  await row.click();
  await expect(page.locator('#activity')).toHaveClass(/active/);
  await expect(page.locator('#tradeInspector')).toBeVisible();
  await expect(page.locator('#tradeInspectorTitle')).toContainText('SPY');
  await page.locator('#tradeInspectorBack').click();
  await expect(page.locator('#charts')).toHaveClass(/active/);
});

test('sticky nav does not cover a focused settings field', async ({ page }) => {
  await openDesk(page);
  await page.getByRole('button', { name: 'Open settings' }).click();
  await expect(page.locator('#settings')).toHaveClass(/active/);
  const field = page.locator('#ntfyUrl');
  await expect(field).toBeVisible();
  await field.focus();
  const fieldBox = await boxOf(page, '#ntfyUrl');
  const navBox = await boxOf(page, '#nav');
  expect(fieldBox.y + fieldBox.height).toBeLessThanOrEqual(navBox.y + 1);
  const appPad = await page.locator('.app').evaluate((el) => parseFloat(getComputedStyle(el).paddingBottom));
  expect(appPad).toBeGreaterThanOrEqual(100);
});

test('200% text still reflows without a two-axis scroll', async ({ page }) => {
  test.skip(test.info().project.name !== 'zoom-200', 'zoom project only');
  await openDesk(page);
  const overflow = await page.evaluate(() => ({
    x: document.documentElement.scrollWidth - window.innerWidth,
    label: parseFloat(getComputedStyle(document.querySelector('.nav') as HTMLElement).fontSize),
  }));
  expect(overflow.x).toBeLessThanOrEqual(24);
  expect(overflow.label).toBeGreaterThanOrEqual(22);
  await expect(page.locator('#sessionClock')).toBeVisible();
  await expect(page.locator('#heroChart')).toBeVisible();
});

test('shared services copy is consumed, not invented', async ({ page }) => {
  await openDesk(page);
  await page.getByRole('button', { name: 'Open settings' }).click();
  await expect(page.locator('#settingsInfo')).toContainText('Runner');
  await expect(page.locator('#settingsInfo')).toContainText('HEALTHY');
  await expect(page.locator('#wdLine')).toContainText('HEALTHY');
  await page.locator('.nav[data-page="activity"]').click();
  await expect(page.locator('#actSessionChip')).toContainText('CLOSED');
  await expect(page.locator('#actSessionChip')).toContainText('HEALTHY');
});

test('all visible choice tabs expose pressed state', async ({ page }) => {
  await openDesk(page);
  await page.getByRole('button', { name: 'Open settings' }).click();
  const tabs = page.locator('#settings button.tab:visible');
  await expect(tabs.first()).toHaveAttribute('aria-pressed', /true|false/);
  expect(await tabs.count()).toBeGreaterThan(1);
});
