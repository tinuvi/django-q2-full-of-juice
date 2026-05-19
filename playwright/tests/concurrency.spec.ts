import { expect, test } from '@playwright/test';

import { enqueue, waitForGroupCount } from '../helpers/api';
import { unique } from '../helpers/data';

test.describe('worker pool concurrency', () => {
  test('4 × slow_noop(2s) with workers=2 finishes in roughly 4s, not 8s', async ({
    request,
  }) => {
    // The sample cluster is started with Q_CLUSTER_WORKERS=2. If the pool
    // actually runs tasks in parallel, four 2-second tasks complete in two
    // batches (~4s). A serial regression would take ~8s. We bound at <7s to
    // give CI plenty of margin while still catching the regression.
    const groupName = unique('concurrency');
    const fanOut = 4;
    const seconds = 2;

    const start = Date.now();
    await Promise.all(
      Array.from({ length: fanOut }).map((_, i) =>
        enqueue(request, {
          task: 'slow_noop',
          args: [`payload-${i}`, seconds],
          group: groupName,
        }),
      ),
    );
    const group = await waitForGroupCount(request, groupName, fanOut, {
      timeoutMs: 30_000,
    });
    const elapsedMs = Date.now() - start;

    expect(group.success_count).toBe(fanOut);
    // Hard upper bound: strictly less than the serial worst-case (8s).
    expect(elapsedMs).toBeLessThan(8_000);
    // Tighter bound that fails the regression where workers serialize.
    expect(elapsedMs).toBeLessThan(7_000);
  });
});
