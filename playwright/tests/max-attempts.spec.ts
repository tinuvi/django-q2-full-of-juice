import { expect, test } from '@playwright/test';

import { enqueue, getTask, waitUntil } from '../helpers/api';

test.describe('max_attempts retry loop', () => {
  test('a failing task is retried up to max_attempts then acknowledged', async ({
    request,
  }) => {
    // The project-wide Q_CLUSTER defaults to `ack_failures: True` so most
    // specs don't pay the retry cost. Here we opt back into the retry loop
    // by passing `ack_failure: false` per-task. With `max_attempts: 3` and
    // `retry: 15` the loop bounds at roughly 3 × retry seconds.
    test.setTimeout(120_000);

    const enqueued = await enqueue(request, {
      task: 'boom',
      ack_failure: false,
    });

    // Each retry pass updates `attempt_count` on the same Task row, so we
    // can watch the counter climb without racing the broker.
    const retried = await waitUntil(
      () => getTask(request, enqueued.task_id),
      state => state.found === true && (state.attempt_count ?? 0) >= 3,
      {
        description: `task ${enqueued.task_id} to reach attempt_count >= 3`,
        timeoutMs: 90_000,
        pollMs: 1_000,
      },
    );
    expect(retried.success).toBe(false);
    expect(retried.attempt_count).toBeGreaterThanOrEqual(3);

    // Once attempt_count >= MAX_ATTEMPTS the broker acks the OrmQ row, so
    // attempt_count should NOT climb further. Sample again after >1 retry
    // window (retry=15s) to prove the loop actually stopped.
    await new Promise(resolve => setTimeout(resolve, 17_000));
    const settled = await getTask(request, enqueued.task_id);
    expect(settled.attempt_count).toBe(retried.attempt_count);
  });
});
