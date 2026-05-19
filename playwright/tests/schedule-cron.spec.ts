import { expect, test } from '@playwright/test';

import { getSchedule, getTask, scheduleCron, waitUntil } from '../helpers/api';
import { unique } from '../helpers/data';

test.describe('Schedule.CRON', () => {
  test('cron schedule with every-minute expression fires and the spawned task succeeds', async ({
    request,
  }) => {
    // Worst-case timing:
    //   - cron `* * * * *` aligns next_run to the next minute boundary (up to ~60s away)
    //   - scheduler tick interval is hardcoded to ~30s in cluster.py
    //   - then the task runs and we poll for completion
    // 180s headroom keeps the test reliable even on a cold-start CI runner.
    test.setTimeout(180_000);

    const name = unique('cron-once');
    const created = await scheduleCron(request, {
      task: 'add',
      args: [11, 31],
      name,
      cron: '* * * * *',
    });
    expect(created.schedule_id).toBeGreaterThan(0);
    expect(created.cron).toBe('* * * * *');

    const fired = await waitUntil(
      () => getSchedule(request, created.schedule_id),
      s => s.found === true && !!s.last_task_id,
      { description: `cron schedule ${name} to fire`, timeoutMs: 150_000, pollMs: 2_000 },
    );
    expect(fired.last_task_id).toBeTruthy();
    // With repeats=1 and a successful fire, django-q2's scheduler decrements
    // to 0 and persists the row (it does *not* delete CRON schedules on fire).
    expect(fired.repeats).toBe(0);

    const finished = await waitUntil(
      () => getTask(request, fired.last_task_id as string),
      state => state.found === true && state.stopped !== null,
      { description: `cron task ${fired.last_task_id} to finish`, timeoutMs: 30_000 },
    );
    expect(finished.success).toBe(true);
    expect(finished.result).toBe(42);
  });
});
