import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: process.env.ASH_E2E_URL || 'http://127.0.0.1:8876',
    trace: 'retain-on-failure',
    reducedMotion: 'reduce',
  },
  webServer: {
    command: 'CEG_ENV=test CEG_PROCESS_ROLE=test CEG_ALLOW_BROKER_ORDERS=false CEG_DATA_DIR=/tmp/ceg-e2e-data CEG_CONFIG_FILE=/tmp/ceg-e2e-config.json /home/nix/.venvs/ceg/bin/python -c "from app import app; app.run(host=\'127.0.0.1\', port=8876, debug=False, threaded=True)"',
    cwd: '..',
    url: 'http://127.0.0.1:8876',
    reuseExistingServer: true,
    timeout: 30_000,
  },
  projects: [
    {
      name: 'phone',
      testIgnore: /live-audit\.spec\.ts/,
      use: {
        ...devices['iPhone 12'],
        browserName: 'chromium',
        defaultBrowserType: 'chromium',
      },
    },
    {
      name: 'live',
      testMatch: /live-audit\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
    {
      name: 'tablet',
      testMatch: /layout\.spec\.ts/,
      use: {
        ...devices['iPad Mini'],
        browserName: 'chromium',
        defaultBrowserType: 'chromium',
      },
    },
    {
      name: 'desktop',
      testMatch: /layout\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 800 },
      },
    },
    {
      name: 'zoom-200',
      testMatch: /layout\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 800 },
      },
    },
  ],
});
