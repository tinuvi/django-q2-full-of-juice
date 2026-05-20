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
    // Counts are tracked as sets of task ids in the file cache, so duplicate
    // enqueues never double-count the same id. We use a delta baseline rather
    // than asserting the post-reset state is exactly zero: when this spec
    // runs in parallel with others, a foreign signal can fire between the
    // reset and the baseline read, leaving the baseline non-zero.
    const initial = await resetSignalCounts(request);

    // Enqueue three tasks serially and wait for each so the three signal
    // handlers have time to land before we assert.
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
        state.pre_enqueue - initial.pre_enqueue >= 3 &&
        state.pre_execute - initial.pre_execute >= 3 &&
        state.post_execute - initial.post_execute >= 3,
      {
        description: 'all three signal counters to advance by >= 3',
        timeoutMs: 20_000,
      },
    );

    expect(counts.pre_enqueue - initial.pre_enqueue).toBeGreaterThanOrEqual(3);
    expect(counts.pre_execute - initial.pre_execute).toBeGreaterThanOrEqual(3);
    expect(counts.post_execute - initial.post_execute).toBeGreaterThanOrEqual(3);
  });
});
