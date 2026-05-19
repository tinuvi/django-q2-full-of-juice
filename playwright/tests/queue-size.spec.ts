import { expect, test } from '@playwright/test';

import { enqueue, getQueueSize, waitForGroupCount } from '../helpers/api';
import { unique } from '../helpers/data';

test.describe('queue_size', () => {
  test('reports a positive backlog while tasks are in flight, then drains to 0', async ({
    request,
  }) => {
    // Sample-cluster runs with workers=2, so 6 × slow_noop(2) leaves at least
    // 4 tasks queued behind the in-flight pair. We measure the OrmQ backlog
    // immediately after enqueueing — `broker.queue_size()` counts rows whose
    // lock has expired (i.e. visible to the next dequeue), which is also the
    // count exercised by the django-q2 admin's Queued-Tasks page.
    const groupName = unique('queue-size');
    const fanOut = 6;

    await Promise.all(
      Array.from({ length: fanOut }).map((_, i) =>
        enqueue(request, {
          task: 'slow_noop',
          args: [`payload-${i}`, 2],
          group: groupName,
        }),
      ),
    );

    const immediate = await getQueueSize(request);
    // Loose lower bound to absorb the small race window between enqueue and
    // the first pusher tick: we only require *some* visible backlog.
    expect(immediate.size).toBeGreaterThanOrEqual(1);

    // Wait for every task to land so the queue drains, then sanity-check 0.
    await waitForGroupCount(request, groupName, fanOut, { timeoutMs: 60_000 });
    const drained = await getQueueSize(request);
    expect(drained.size).toBe(0);
  });
});
