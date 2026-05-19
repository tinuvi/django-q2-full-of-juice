import { expect, test } from '@playwright/test';

import { getSchedule, getTask, scheduleOnce, waitUntil } from '../helpers/api';
import { unique } from '../helpers/data';

test.describe('Schedule', () => {
  test('one-shot schedule fires and the spawned task succeeds', async ({ request }) => {
    // django-q2's scheduler tick runs every ~30s (hardcoded in cluster.py), so
    // a one-shot Schedule may take up to 30s to fire even with next_run in the
    // past. Bump the per-test timeout above the global default so we don't
    // race the tick on a cold sample stack.
    test.setTimeout(180_000);
    const name = unique('schedule-once');
    const created = await scheduleOnce(request, {
      task: 'add',
      args: [7, 35],
      name,
      // ~1s in the future so the scheduler tick (default 30s) might not catch
      // it immediately; the wait below is generous enough for the next tick.
      run_in_secs: 1,
    });
    expect(created.schedule_id).toBeGreaterThan(0);

    // Poll the schedule endpoint until `last_task_id` is populated. With repeats==-1
    // and schedule_type=ONCE, django-q2 keeps the Schedule row around after firing
    // and stamps the spawned task_id onto Schedule.task.
    const fired = await waitUntil(
      () => getSchedule(request, created.schedule_id),
      s => s.found === true && !!s.last_task_id,
      { description: `schedule ${name} to fire`, timeoutMs: 120_000, pollMs: 1_000 },
    );
    expect(fired.last_task_id).toBeTruthy();

    const finished = await waitUntil(
      () => getTask(request, fired.last_task_id as string),
      state => state.found === true && state.stopped !== null,
      { description: `scheduled task ${fired.last_task_id} to finish` },
    );
    expect(finished.success).toBe(true);
    expect(finished.result).toBe(42);
  });
});
