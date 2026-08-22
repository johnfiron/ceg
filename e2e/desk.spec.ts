import { expect, test, type Page } from '@playwright/test';

const now = '2026-08-21T16:00:00-04:00';

function status(environment = 'development') {
  return {
    configured: true,
    paper_only: true,
    broker_orders_enabled: false,
    environment,
    process_role: 'web',
    clock: {
      hm: '16:00',
      phase: 'CLOSED',
      label: 'CLOSED',
      current: [],
      next: { id: 'OPN', start: '09:35' },
      remaining: null,
    },
    session_complete_pct: 1,
    watchdog_stale: false,
    data_stale: false,
    guest: false,
    unread_errors: 0,
  };
}

const live = {
  clock: {
    hm: '16:00',
    phase: 'CLOSED',
    label: 'CLOSED',
    current: [],
    next: { id: 'OPN', start: '09:35' },
    remaining: null,
  },
  session_complete_pct: 1,
  bar_count: 390,
  last_ingest: now,
  watchlist: [
    {
      sym: 'SPY',
      c: 650.12,
      setup: { score: 0.91, fired: false, bottleneck_en: 'waiting on RVOL', book_label: 'OPN' },
    },
  ],
  tickers: {
    SPY: {
      sym: 'SPY',
      c: 650.12,
      ret: 0.012,
      setup: { score: 0.91, fired: false, bottleneck_en: 'waiting on RVOL' },
      regime: 'TREND',
    },
  },
  explain: {
    headline: 'Market is closed',
    paragraphs: ['No sleeve is live. ASH is waiting for OPN at 09:35.'],
    why_not: [],
    books: [],
  },
};

const bootstrap = {
  as_of: now,
  window_days: 30,
  cutoff: '2026-07-22',
  status: status(),
  account: { equity: 100504, portfolio_value: 100504, cash: 98000, last_equity: 100000 },
  trades: {
    trades: [
      { id: 11, status: 'CLOSED', strategy_id: 'ORB', ticker: 'QQQ', pnl: 120, trade_date: '2026-08-21' },
      { id: 12, status: 'CLOSED', strategy_id: 'MVR', ticker: 'SPY', pnl: -40, trade_date: '2026-08-21' },
    ],
  },
  dashboard: {
    curve: [{ date: '2026-08-21', cumPnl: 80 }],
    balanceCurve: [
      { t: '2026-08-21T09:30:00-04:00', equity: 100000, portfolio_value: 100000 },
      { t: now, equity: 100504, portfolio_value: 100504 },
    ],
    totals: { realizedToday: 80, open: 0, sessionDate: '2026-08-21' },
    openTrades: [],
    strategies: [],
    tickerStats: {},
  },
};

const bars = {
  ticker: 'SPY',
  date: '2026-08-21',
  state: { or_high: 648, or_low: 646, prev_close: 642.5, vwap: 647 },
  bars: [
    { t: '2026-08-21T09:30:00-04:00', o: 643, h: 644, l: 642, c: 643.5, v: 1000, vwap: 643.2 },
    { t: '2026-08-21T09:35:00-04:00', o: 643.5, h: 646, l: 643, c: 645, v: 1200, vwap: 644.1 },
    { t: '2026-08-21T15:59:00-04:00', o: 649, h: 651, l: 648, c: 650.12, v: 900, vwap: 647 },
  ],
};

async function mockDesk(page: Page, environment = 'development') {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/ash/, '');
    if (path === '/api/status') return route.fulfill({ json: status(environment) });
    if (path === '/api/bootstrap') return route.fulfill({ json: { ...bootstrap, status: status(environment) } });
    if (path === '/api/live') return route.fulfill({ json: live });
    if (path === '/api/sleeve_history') return route.fulfill({ json: { strategies: [] } });
    if (path === '/api/workspace') return route.fulfill({ json: { playbook: [] } });
    if (path === '/api/trade_board') return route.fulfill({ json: { trades: [] } });
    if (path === '/api/dashboard') return route.fulfill({ json: bootstrap.dashboard });
    if (path.startsWith('/api/live_bars/')) return route.fulfill({ json: bars });
    if (path.startsWith('/api/market_chart/')) return route.fulfill({ json: { bars: bars.bars } });
    if (path === '/api/comments') return route.fulfill({ json: { comments: [] } });
    return route.fulfill({ json: {} });
  });
}

async function openDesk(page: Page, environment = 'development') {
  await mockDesk(page, environment);
  await page.addInitScript(() => {
    localStorage.setItem('ashIdle', 'pause');
  });
  await page.goto('/?from=vault');
  await page.waitForFunction(() => {
    const home = document.getElementById('home');
    return !document.body.classList.contains('needs-keys') &&
      home && home.classList.contains('active') &&
      !document.getElementById('terminal')?.classList.contains('hidden');
  });
}

test('phone Home is clock, book facts, one hero, then watched names', async ({ page }) => {
  await openDesk(page);
  await expect(page.locator('#sessionClock')).toBeVisible();
  await expect(page.locator('#sessionPnl')).toContainText('+');
  await expect(page.locator('#portfolioValue')).toContainText('$100,504');
  await expect(page.locator('#dailyMove')).toBeVisible();
  await expect(page.locator('#heroChart')).toBeVisible();
  await expect(page.locator('#heroTitle')).toBeVisible();
  await expect(page.getByRole('button', { name: /Largest win/i })).toContainText('ORB');
  await expect(page.getByRole('button', { name: /Largest loss/i })).toContainText('MVR');
  await expect(page.locator('#watchlist')).toContainText('SPY');
  await expect(page.locator('#homeKpis')).toBeHidden();
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
  const box = await page.locator('#charts .chartTall').boundingBox();
  expect(box?.height || 0).toBeGreaterThanOrEqual(300);
});

test('production monitor hides Connect, Lab, and mutation chrome', async ({ page }) => {
  await openDesk(page, 'production');
  await expect(page.locator('body')).toHaveClass(/monitor-lock/);
  await expect(page.locator('#setupLocalFields')).toBeHidden();
  await expect(page.getByRole('button', { name: 'Connect' })).toHaveCount(0);
  await expect(page.locator('.nav[data-page="research"]')).toBeHidden();
  await expect(page.getByRole('button', { name: 'RECONCILE' })).toBeHidden();
  await expect(page.getByRole('button', { name: 'Change local keys/settings' })).toBeHidden();
});
