import { expect, test, type Page } from '@playwright/test';

export const now = '2026-08-21T16:00:00-04:00';

const trades = [
  {
    id: 11,
    status: 'CLOSED',
    strategy_id: 'ORB',
    ticker: 'QQQ',
    pnl: 120,
    trade_date: '2026-08-21',
    direction: 'CALL',
    entry_fill: 2.4,
    exit_fill: 3.6,
    entry_filled_at: '2026-08-21T09:35:00-04:00',
    exit_filled_at: '2026-08-21T10:05:00-04:00',
    option_symbol: 'QQQ260821C00570000',
  },
  {
    id: 12,
    status: 'CLOSED',
    strategy_id: 'MVR',
    ticker: 'SPY',
    pnl: -40,
    trade_date: '2026-08-21',
    direction: 'CALL',
    entry_fill: 1.8,
    exit_fill: 1.4,
    entry_filled_at: '2026-08-21T09:35:00-04:00',
    exit_filled_at: '2026-08-21T15:59:00-04:00',
    option_symbol: 'SPY260821C00650000',
  },
  {
    id: 13,
    status: 'ENTRY_FAILED',
    strategy_id: 'OPN',
    ticker: 'IWM',
    pnl: null,
    trade_date: '2026-08-21',
    direction: 'PUT',
    entry_fill: null,
    option_symbol: 'IWM260821P00300000',
  },
];

export function status(environment = 'development') {
  return {
    configured: true,
    paper_only: true,
    broker_orders_enabled: false,
    broker_config_enabled: false,
    broker_runtime_armed: false,
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
    services: {
      market: 'CLOSED',
      strategies: 'IDLE',
      session_scan: 'HEALTHY',
      runner: 'HEALTHY',
      broker: 'PAPER',
      broker_quotes: 'HEALTHY',
    },
  };
}

export const live = {
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

export const bootstrap = {
  as_of: now,
  window_days: 30,
  cutoff: '2026-07-22',
  status: status(),
  account: { equity: 100504, portfolio_value: 100504, cash: 98000, last_equity: 100000 },
  trades: { trades },
  dashboard: {
    curve: [{ date: '2026-08-21', cumPnl: 80 }],
    balanceCurve: [
      { t: '2026-08-21T09:30:00-04:00', equity: 100000, portfolio_value: 100000 },
      { t: now, equity: 100504, portfolio_value: 100504 },
    ],
    totals: { realizedToday: 80, open: 0, sessionDate: '2026-08-21' },
    openTrades: [],
    strategies: [
      { id: 'OPN', name: 'Opening continuation', plain: 'Trade only after the opening tape confirms direction.', session: '09:35–09:55', horizon: 'EOD', fires: 2, opportunities: 10, fireRate: 0.2, nDays: 8, sample: 'COLLECTING', expectancy: 12 },
    ],
    tickerStats: { SPY: { closed: 1, winRate: 0, pnl: -40 } },
  },
};

export const bars = {
  ticker: 'SPY',
  date: '2026-08-21',
  state: { or_high: 648, or_low: 646, prev_close: 642.5, vwap: 647 },
  bars: [
    { t: '2026-08-21T09:30:00-04:00', o: 643, h: 644, l: 642, c: 643.5, v: 1000, vwap: 643.2 },
    { t: '2026-08-21T09:35:00-04:00', o: 643.5, h: 646, l: 643, c: 645, v: 1200, vwap: 644.1 },
    { t: '2026-08-21T15:59:00-04:00', o: 649, h: 651, l: 648, c: 650.12, v: 900, vwap: 647 },
  ],
};
const replayBars = Array.from({ length: 60 }, (_, i) => ({
  t: new Date(new Date('2026-08-21T09:30:00-04:00').getTime() + i * 60_000).toISOString(),
  o: 643 + i * 0.05,
  h: 643.4 + i * 0.05,
  l: 642.8 + i * 0.05,
  c: 643.2 + i * 0.05,
  v: 1000 + i * 10,
  vwap: 643 + i * 0.03,
}));

export function canonicalTrade(id = 12) {
  const raw = trades.find((t) => t.id === id) || trades[1];
  return {
    id: raw.id,
    status: raw.status,
    identity: {
      ticker: raw.ticker,
      type: raw.direction,
      arrow: '↑',
      strike: 650,
      expiry: '2026-08-21',
      occ_symbol: raw.option_symbol,
    },
    strategy: { id: raw.strategy_id, version: '1.0.0' },
    raw_trade: raw,
    option: {
      entry: { bid: 1.75, ask: 1.85, spread_pct: 0.055, quote_age_sec: 2, moneyness: 'ATM', distance_pct: 0.002 },
      current: {},
      exit: {},
      candidates: [{ selected: true, dte: 0, grade: 'B' }],
      break_even: 651.8,
    },
    prediction: {
      entry: {
        direction: raw.direction,
        confidence: 0.61,
        horizon: 'session',
        underlying_lo: -0.006,
        underlying_hi: 0.012,
        option_return_lo: -0.4,
        option_return_hi: 0.8,
        invalidation: 'Close back inside the opening range',
      },
      error: {
        actual_option_return: -0.222,
        direction_correct: false,
        magnitude_error: 0.18,
        timing_error_seconds: 21000,
        premium_error: 0.22,
      },
    },
    execution: {
      entry_fill: raw.entry_fill,
      fees: 0.65,
      modeled_slippage: 0.05,
      actual_slippage: 0.05,
      latency_sec: 1,
      fill_quality: { would_fill_at_ask: true },
    },
    position: {
      quantity: raw.qty,
      delta_equivalent_shares: 42,
      underlying_beta: { value: 1, source: 'local_spy_ols', as_of: '2026-08-21' },
      beta_adjusted_equivalent_shares: 42,
    },
    risk: { premium_at_risk: 180, exit_due_date: '2026-08-21' },
    outcome: {
      realized_pnl: raw.pnl,
      hold_seconds: 23040,
      exit_kind: 'EOD',
      return_pct: -0.222,
    },
    availability: { mark: 'CAPTURED' },
    comments: [],
    tape: { bars: bars.bars, entryIndex: 1, exitIndex: 2 },
  };
}

export async function mockDesk(page: Page, environment = 'development') {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/ash/, '');
    if (path === '/api/status') return route.fulfill({ json: status(environment) });
    if (path === '/api/bootstrap') return route.fulfill({ json: { ...bootstrap, status: status(environment) } });
    if (path === '/api/live') return route.fulfill({ json: live });
    if (path === '/api/news') return route.fulfill({ json: { source: 'alpaca', news: { SPY: { headline: 'Market opens with a measured tone', source: 'wire' } } } });
    if (path === '/api/sleeve_history') return route.fulfill({ json: { strategies: [] } });
    if (path === '/api/workspace') return route.fulfill({ json: { playbook: [] } });
    if (path === '/api/trade_board') return route.fulfill({ json: { trades } });
    if (path === '/api/dashboard') return route.fulfill({ json: bootstrap.dashboard });
    if (path === '/api/overlap') return route.fulfill({ json: { ids: ['OPN'], matrix: { OPN: { OPN: 2 } } } });
    if (path === '/api/model_drift') return route.fulfill({ json: { rows: [{ id: 'OPN', n: 2, live_win_rate: 0.5, live_avg_pnl: 12 }] } });
    if (path === '/api/research_metrics') return route.fulfill({ json: { strategies: bootstrap.dashboard.strategies, coverage: {}, reasons: [], stretch_bins: [], sample: 'COLLECTING' } });
    if (path === '/api/near_misses') return route.fulfill({ json: { rows: [] } });
    if (path === '/api/research_surface') return route.fulfill({ json: { points: [] } });
    if (path === '/api/lab_snapshots') return route.fulfill({ json: { rows: [] } });
    if (path === '/api/notes') return route.fulfill({ json: { text: '' } });
    if (path === '/api/backups') return route.fulfill({ json: { files: [{ name: 'arena-20260821.db' }] } });
    if (path.startsWith('/api/replay/')) return route.fulfill({ json: { bars: replayBars, signals: [], context: {} } });
    if (path.startsWith('/api/replay_live/')) return route.fulfill({ json: { bars: replayBars, evals: [] } });
    if (path === '/api/trades') return route.fulfill({ json: { trades } });
    if (path.startsWith('/api/trades/')) {
      const id = Number(path.split('/').pop());
      return route.fulfill({ json: canonicalTrade(id) });
    }
    if (path.startsWith('/api/live_bars/')) return route.fulfill({ json: bars });
    if (path.startsWith('/api/market_chart/')) return route.fulfill({ json: { bars: bars.bars } });
    if (path === '/api/comments') return route.fulfill({ json: { comments: [] } });
    if (path === '/api/signals') return route.fulfill({ json: { signals: [] } });
    if (path === '/api/events') return route.fulfill({ json: { events: [] } });
    return route.fulfill({ json: {} });
  });
}

export async function applyZoom(page: Page) {
  if (test.info().project.name !== 'zoom-200') return;
  await page.addStyleTag({ content: 'html{font-size:200%!important}' });
}

export async function openDesk(page: Page, environment = 'development') {
  await mockDesk(page, environment);
  await page.addInitScript(() => {
    localStorage.setItem('ashIdle', 'pause');
  });
  await page.goto('/?intro=skip');
  await page.waitForFunction(() => {
    const home = document.getElementById('home');
    return !document.body.classList.contains('needs-keys') &&
      home && home.classList.contains('active') &&
      !document.getElementById('terminal')?.classList.contains('hidden');
  });
  await applyZoom(page);
}

export async function boxOf(page: Page, selector: string) {
  const box = await page.locator(selector).first().boundingBox();
  expect(box, selector).toBeTruthy();
  return box!;
}

export async function expectMinHit(page: Page, selector: string, size = 44) {
  const box = await boxOf(page, selector);
  expect(box.height, `${selector} height`).toBeGreaterThanOrEqual(size);
  expect(box.width, `${selector} width`).toBeGreaterThanOrEqual(size);
}
