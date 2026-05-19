import { expect, test } from '@playwright/test';

import {
  enqueue,
  getSignalCounts,
  resetSignalCounts,
  waitForTask,
  waitUntil,
} from '../helpers/api';

test.describe('django-q2 lifecycle signals', () => {
  test('pre_enqueue, pre_execute, and post_execute all fire per task', async ({
    request,
  }) => {
    const initial = await resetSignalCounts(request);
    expect(initial).toMatchObject({
      pre_enqueue: 0,
      pre_execute: 0,
      post_execute: 0,
    });

    // Enqueue three tasks serially and wait for each so the three signal
    // handlers have time to land before we assert. Counts are tracked as a
    // set of task ids, so even if another spec's leftover task fires after
    // us the count never double-increments for the same id.
    const enqueued = [
      await enqueue(request, { task: 'add', args: [1, 1] }),
      await enqueue(request, { task: 'noop', args: ['sig'] }),
      await enqueue(request, { task: 'concat', args: ['a', 'b'] }),
    ];

    for (const e of enqueued) {
      const done = await waitForTask(request, e.task_id, { timeoutMs: 30_000 });
      expect(done.success).toBe(true);
    }

    const counts = await waitUntil(
      () => getSignalCounts(request),
      state =>
        state.pre_enqueue >= 3 && state.pre_execute >= 3 && state.post_execute >= 3,
      { description: 'all three signal counters to reach 3', timeoutMs: 20_000 },
    );

    expect(counts.pre_enqueue).toBeGreaterThanOrEqual(3);
    expect(counts.pre_execute).toBeGreaterThanOrEqual(3);
    expect(counts.post_execute).toBeGreaterThanOrEqual(3);
  });
});
