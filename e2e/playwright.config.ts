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
  projects: [
    {
      name: 'phone',
      use: {
        ...devices['iPhone 12'],
        browserName: 'chromium',
        defaultBrowserType: 'chromium',
      },
    },
  ],
});
