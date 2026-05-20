import { defineConfig, devices } from '@playwright/test';

const SAMPLE_PROJECT_URL = process.env.SAMPLE_PROJECT_URL ?? 'http://localhost:8000';

// ─────────────────────────────────────────────────────────────────────────────
// PARALLELISM MODEL — read before adding a new spec.
//
// The suite is split into two execution tiers using Playwright projects:
//
//   1. `parallel` — runs first, with up to 4 spec files concurrently. Default
//      home for any new spec.
//   2. `serial-<name>` — chained dependencies that run one-by-one *after*
//      `parallel` finishes. Reserved for specs that read or reset shared
//      file-cache state in `sample-project/tasks_app/signals.py` and would
//      race under parallelism.
//
// Why the split exists
// ────────────────────
// The sample-project signal recorder uses Django's file-backed cache as a
// cross-process store (workers and the web container don't share memory).
// Some keys are inherently per-task-id (e.g. `task-attempt-ladder:<id>`,
// `exception-snapshot:<id>`) and need no isolation. Others are global and
// updated via non-atomic read-modify-write:
//
//   - `signal-seen:<signal>` — set of task ids seen by each signal. Reset by
//     /api/signal-counts/reset/. RMW in `_record()`.
//   - `chain-progress-log` — append-only list of (signal, task_id, group_id)
//     events. Reset by /api/chain-progress/reset/. RMW in
//     `_append_chain_event()`.
//
// Two readers/resetters running concurrently can clobber each other's
// observations. Three specs are affected:
//
//   - `signals.spec.ts` — resets signal-counts; concurrent reset wipes baseline.
//   - `save-false.spec.ts` — resets signal-counts and measures deltas.
//   - `chain-progress.spec.ts` — resets chain-progress-log; concurrent chain
//     enqueues from the same monitor process race on the list RMW.
//
// Where to put a new spec
// ───────────────────────
// If your spec ONLY uses per-task-id state (task lookups, exception snapshots
// by id, attempt ladders by id) or filters on a unique group_id, it is safe
// to leave in `parallel`. This is the common case.
//
// If your spec READS or RESETS one of these GLOBAL keys:
//   - signal-counts (the `signal-seen:<signal>` cache key)
//   - chain-progress-log
// then add it to a NEW `serial-<your-name>` project below, with `dependencies`
// pointing at the previously-last serial project so the chain stays
// strictly sequential. Update the comment above the `serial-` entries to
// note the new contamination surface you're protecting.
//
// Debugging unexpected failures
// ─────────────────────────────
// If specs that normally pass start timing out on `waitForTask` /
// `waitForGroupCount`, the sample-project's persistent SQLite volume
// (`sample-data`) is the first suspect. Orphan schedules with remaining
// repeats and retry-loop tasks from a previous *failed* run survive across
// `docker compose --force-recreate` and keep firing into subsequent runs,
// saturating the cluster. Wipe with:
//
//     cd sample-project && docker compose down -v && docker compose up -d
//
// A clean run from scratch should be the baseline before declaring a real
// regression.
// ─────────────────────────────────────────────────────────────────────────────

const SERIAL_SPEC_FILES = [
  'signals.spec.ts',
  'save-false.spec.ts',
  'chain-progress.spec.ts',
];

export default defineConfig({
  testDir: './tests',

  // Parallelize across spec files but keep tests within a file serial. The
  // sample stack runs a 4-worker django-q2 cluster sized to match the
  // playwright worker count; time-bound specs (schedule-*, max-attempts,
  // retry-attempt-stamping) overlap inside the 30s scheduler-tick windows
  // instead of running back-to-back. See the comment block above for the
  // parallelism contract.
  fullyParallel: false,
  workers: 4,
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
    // Tier 1: parallel. Every spec NOT in SERIAL_SPEC_FILES runs here.
    {
      name: 'parallel',
      testIgnore: SERIAL_SPEC_FILES.map(name => `**/${name}`),
      use: { ...devices['Desktop Chrome'] },
    },
    // Tier 2: serial chain. Each project holds one spec file and waits for
    // the previous project to finish, so only ONE contamination-sensitive
    // spec runs at a time and nothing else is running alongside it. Playwright
    // has no per-project `workers` setting, so isolation is enforced by
    // `dependencies` + having a single matching file per project.
    {
      name: 'serial-signals',
      testMatch: '**/signals.spec.ts',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['parallel'],
    },
    {
      name: 'serial-save-false',
      testMatch: '**/save-false.spec.ts',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['serial-signals'],
    },
    {
      name: 'serial-chain-progress',
      testMatch: '**/chain-progress.spec.ts',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['serial-save-false'],
    },
  ],
});
