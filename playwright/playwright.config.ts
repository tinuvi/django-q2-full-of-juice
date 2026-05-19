import { defineConfig, devices } from '@playwright/test';

const SAMPLE_PROJECT_URL = process.env.SAMPLE_PROJECT_URL ?? 'http://localhost:8000';

export default defineConfig({
  testDir: './tests',

  // The sample stack runs a single django-q2 cluster with a small worker pool.
  // Running specs sequentially keeps the worker queue depth predictable so a
  // single slow scenario can't starve the others.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: process.env.CI
    ? [['html', { open: 'never' }], ['github']]
    : [['html', { open: 'on-failure' }], ['list']],
  use: {
    baseURL: SAMPLE_PROJECT_URL,
    extraHTTPHeaders: { Accept: 'application/json' },
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
