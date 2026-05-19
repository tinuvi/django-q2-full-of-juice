import { expect, test } from '@playwright/test';

import { getSchedule, getTask, scheduleOnce, waitUntil } from '../helpers/api';
import { unique } from '../helpers/data';

test.describe('intended_date_kwarg', () => {
  test('the spawned task receives the schedule next_run as a kwarg', async ({
    request,
  }) => {
    // Same ~30s scheduler-tick reasoning as schedule.spec.ts; bump the
    // per-test timeout to keep the wait generous on cold runners.
    test.setTimeout(180_000);

    const name = unique('intended-date');
    const created = await scheduleOnce(request, {
      task: 'noop',
      args: [],
      name,
      run_in_secs: 1,
      // The scheduler will inject `kwargs["fire_time"] = s.next_run.isoformat()`
      // just before enqueueing — see scheduler.py:71-72.
      intended_date_kwarg: 'fire_time',
    });
    expect(created.schedule_id).toBeGreaterThan(0);

    const fired = await waitUntil(
      () => getSchedule(request, created.schedule_id),
      s => s.found === true && !!s.last_task_id,
      {
        description: `schedule ${name} to fire`,
        timeoutMs: 120_000,
        pollMs: 1_000,
      },
    );
    expect(fired.intended_date_kwarg).toBe('fire_time');

    const finished = await waitUntil(
      () => getTask(request, fired.last_task_id as string),
      state => state.found === true && state.stopped !== null,
      { description: `scheduled task ${fired.last_task_id} to finish` },
    );
    expect(finished.success).toBe(true);

    // noop returns {args, kwargs}; the kwargs dict should contain the
    // schedule's `next_run` as an ISO timestamp under our chosen key.
    const result = finished.result as { args: unknown[]; kwargs: Record<string, string> };
    expect(result.kwargs.fire_time).toBeTruthy();
    expect(typeof result.kwargs.fire_time).toBe('string');
    // ISO timestamps parse cleanly; reject anything that doesn't.
    expect(Number.isNaN(Date.parse(result.kwargs.fire_time))).toBe(false);
  });
});
