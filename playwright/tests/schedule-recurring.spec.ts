import { expect, test } from '@playwright/test';

import {
  getSchedule,
  scheduleRecurring,
  waitForGroupCount,
  waitUntil,
} from '../helpers/api';
import { unique } from '../helpers/data';

test.describe('Schedule.MINUTES recurring', () => {
  test('schedule with repeats=2 spawns exactly two tasks before going idle', async ({
    request,
  }) => {
    // Worst-case timing:
    //   - minutes=1 means consecutive fires are ~60s apart
    //   - scheduler tick is hardcoded ~30s
    //   - With next_run=now-1s, first fire is on the next tick (<=30s),
    //     then we wait at least 60s for the second to come due.
    test.setTimeout(240_000);

    const name = unique('recurring');
    const created = await scheduleRecurring(request, {
      task: 'add',
      args: [10, 5],
      name,
      minutes: 1,
      repeats: 2,
    });
    expect(created.repeats).toBe(2);

    // django-q2's scheduler stamps `group = name or schedule_id` on every
    // task it spawns from this schedule, so we can count by group.
    const group = await waitForGroupCount(request, name, 2, {
      timeoutMs: 210_000,
      pollMs: 2_000,
    });
    expect(group.count).toBe(2);
    expect(group.success_count).toBe(2);
    expect(group.tasks.every(t => t.result === 15)).toBe(true);

    const settled = await waitUntil(
      () => getSchedule(request, created.schedule_id),
      s => s.found === true && s.repeats === 0,
      {
        description: `schedule ${name} repeats counter to reach 0`,
        timeoutMs: 30_000,
        pollMs: 1_000,
      },
    );
    expect(settled.repeats).toBe(0);
  });
});
