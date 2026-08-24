import { expect, test } from '@playwright/test';
import { openDesk } from './helpers';

test('Home leads with context, one P&L, account equity, then closest setup', async ({ page }) => {
  await openDesk(page);
  const order = await page.locator('#home > .panel').evaluateAll((els) => els.map((el) => el.id || el.className));
  expect(order[0]).toBe('explainBox');
  await expect(page.locator('#sessionClock')).toBeVisible();
  await expect(page.locator('#sessionPnl')).toContainText('+');
  await expect(page.locator('#portfolioValue')).toContainText('$100,504');
  await expect(page.locator('#dailyMove')).toBeVisible();
  await expect(page.locator('#heroChart')).toBeVisible();
  await expect(page.locator('#heroTitle')).toHaveText('ACCOUNT');
  await expect(page.locator('#heroChip')).toHaveText('ACCOUNT');
  await expect(page.locator('.factRail')).toHaveCount(0);
  await expect(page.locator('#watchlist')).toContainText('SPY');
  await expect(page.locator('#homeKpis')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Tape pulse' })).toHaveCount(0);
  const box = await page.locator('.heroChartFrame').boundingBox();
  expect(box?.height || 0).toBeGreaterThanOrEqual(200);
});

test('watchlist opens the tall inspect surface with step controls', async ({ page }) => {
  await openDesk(page);
  await page.locator('#watchlist [data-ticker="SPY"]').click();
  await expect(page.locator('#charts')).toHaveClass(/active/);
  await expect(page.locator('#inspectChart')).toBeVisible();
  await expect(page.locator('#inspectVolume')).toBeVisible();
  await expect(page.getByRole('button', { name: 'BAR →' })).toBeVisible();
  await expect(page.getByRole('button', { name: '← BAR' })).toBeVisible();
  await expect(page.locator('#inspectTitle')).toContainText('SPY');
  await expect(page.locator('#liveGrid')).toContainText('NEWS · Market opens with a measured tone · wire');
  const box = await page.locator('#charts .chartTall').boundingBox();
  expect(box?.height || 0).toBeGreaterThanOrEqual(300);
});

test('inspect brush keeps price and volume in one resettable window', async ({ page }) => {
  await openDesk(page);
  await page.locator('#watchlist [data-ticker="SPY"]').click();
  const chart = page.locator('#inspectChart');
  await expect(chart).toBeVisible();
  await expect(page.locator('#inspectReadout')).toContainText('O $');
  const box = await chart.boundingBox();
  expect(box).toBeTruthy();

  const y = box!.y + box!.height / 2;
  await chart.dispatchEvent('pointerdown', { pointerId: 7, pointerType: 'touch', clientX: box!.x + 72, clientY: y });
  await chart.dispatchEvent('pointermove', { pointerId: 7, pointerType: 'touch', clientX: box!.x + box!.width / 2, clientY: y });
  await expect(page.locator('#inspectReadout')).toContainText('ZOOM');
  await chart.dispatchEvent('pointerup', { pointerId: 7, pointerType: 'touch', clientX: box!.x + box!.width / 2, clientY: y });

  await expect(page.locator('#inspectReset')).toBeEnabled();
  await expect(page.getByRole('button', { name: 'FULL SESSION' })).toBeEnabled();
  await expect(page.getByRole('button', { name: '← WINDOW' })).toBeVisible();
  await page.getByRole('button', { name: '1m', exact: true }).click();
  await expect(page.locator('#inspectReset')).toBeEnabled();
  await page.keyboard.press('Escape');
  await expect(page.locator('#inspectReset')).toBeDisabled();
});

test('production monitor hides Connect, Lab, and mutation chrome', async ({ page }) => {
  await openDesk(page, 'production');
  await expect(page.locator('body')).toHaveClass(/monitor-lock/);
  await expect(page.locator('#setupLocalFields')).toBeHidden();
  await expect(page.getByRole('button', { name: 'Connect' })).toHaveCount(0);
  await expect(page.locator('.nav[data-page="research"]')).toBeHidden();
  await expect(page.getByRole('button', { name: 'RECONCILE' })).toBeHidden();
  await expect(page.getByRole('button', { name: /CHANGE LOCAL KEYS/i })).toBeHidden();
});

test('Replay pairs price and volume and exposes explicit transport state', async ({ page }) => {
  await openDesk(page);
  await page.locator('.nav[data-page="strategies"]').click();
  await page.getByRole('button', { name: /OPEN REPLAY/ }).click();
  await expect(page.locator('#replay')).toHaveClass(/active/);
  await expect(page.locator('#replayPlay')).toBeDisabled();
  await page.getByRole('button', { name: 'LOAD 3:45' }).click();
  await expect(page.locator('#replayPlay')).toBeEnabled();
  const price = await page.locator('#replayChart').boundingBox();
  const volume = await page.locator('#replayVolume').boundingBox();
  expect(price?.width).toBe(volume?.width);
  await page.locator('#replayPlay').click();
  await expect(page.locator('#replayPlay')).toHaveText(/PAUSE/);
  await expect(page.locator('.replayStep').first()).toBeDisabled();
});

test('Activity separates exceptional entries and missing quantity stays uncaptured', async ({ page }) => {
  await openDesk(page);
  await page.locator('.nav[data-page="activity"]').click();
  await expect(page.locator('#activitySummary')).toContainText('3 records');
  await expect(page.locator('#tradeRows')).not.toContainText('ENTRY_FAILED');
  await expect(page.locator('#failedTradeRows')).toContainText('ENTRY_FAILED');
  await page.locator('#failedTradeRows .activityTrade').click();
  await expect(page.locator('#tradeContract')).toContainText('NOT CAPTURED');
});

test('Settings communicates state and persists pressed preferences', async ({ page }) => {
  await openDesk(page);
  await page.getByRole('button', { name: 'Open settings' }).click();
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await expect(page.locator('#lanOrders')).toHaveText('DISABLED');
  await page.getByRole('button', { name: 'MONITOR' }).click();
  await expect(page.getByRole('button', { name: 'MONITOR' })).toHaveAttribute('aria-pressed', 'true');
  await page.reload();
  await page.getByRole('button', { name: 'Open settings' }).click();
  await expect(page.getByRole('button', { name: 'MONITOR' })).toHaveAttribute('aria-pressed', 'true');
});

test('Lab keeps extended endpoints lazy until a purpose section opens', async ({ page }) => {
  let requests = 0;
  page.on('request', (request) => {
    if (/\/api\/(near_misses|research_surface)/.test(request.url())) requests += 1;
  });
  await openDesk(page);
  await page.locator('.nav[data-page="research"]').click();
  await expect(page.getByRole('heading', { name: 'Strategy lab' })).toBeVisible();
  expect(requests).toBe(0);
  await page.getByText('Distributions & misses', { exact: true }).click();
  await expect.poll(() => requests).toBeGreaterThan(0);
});

test('typing letter shortcuts never changes the active page', async ({ page }) => {
  await openDesk(page);
  for (const key of ['a', 'c', 'h', 'i', 'l', 'm', 'r', 's', 'R']) await page.keyboard.press(key);
  await expect(page.locator('#home')).toHaveClass(/active/);
});
