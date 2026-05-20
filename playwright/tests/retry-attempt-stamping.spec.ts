import { expect, test } from '@playwright/test';

import {
  enqueue,
  getTask,
  getTaskAttempts,
  waitForTask,
  waitUntil,
} from '../helpers/api';

test.describe('pusher stamps task["attempt"] for pre_execute receivers', () => {
  test('a successful first delivery is observed at attempt=1', async ({
    request,
  }) => {
    // The pusher reads monitor.save_task's authoritative attempt_count
    // before queueing each task. On first delivery no Task row exists yet,
    // so attempt should be 1 and the ladder should contain a single entry.
    const enqueued = await enqueue(request, { task: 'add', args: [1, 2] });
    const finished = await waitForTask(request, enqueued.task_id);
    expect(finished.success).toBe(true);

    const attempts = await getTaskAttempts(request, enqueued.task_id);
    expect(attempts.found).toBe(true);
    expect(attempts.attempts_seen).toEqual([1]);
    expect(attempts.latest).toBe(1);
  });

  test('a forced-retry task is observed with an ascending attempt ladder', async ({
    request,
  }) => {
    // `boom` always raises. Passing `ack_failure: false` tells the worker
    // not to ack the OrmQ row on failure, so the broker re-delivers the
    // same payload once its lock (Conf.RETRY = 15s in sample-project)
    // expires. The pusher then sees a Task row with attempt_count>=1 and
    // stamps task["attempt"] = N+1 on the redelivered payload.
    test.setTimeout(120_000);

    const enqueued = await enqueue(request, {
      task: 'boom',
      ack_failure: false,
    });

    // Wait until pre_execute has fired at least twice for this task,
    // proving the broker re-delivered and the pusher re-stamped. The
    // sample-project's Q_CLUSTER caps the loop at max_attempts=3.
    const ladder = await waitUntil(
      () => getTaskAttempts(request, enqueued.task_id),
      state => state.found === true && (state.attempts_seen?.length ?? 0) >= 2,
      {
        description: `task ${enqueued.task_id} attempt ladder to reach length 2`,
        timeoutMs: 90_000,
        pollMs: 1_000,
      },
    );

    expect(ladder.found).toBe(true);
    const seen = ladder.attempts_seen ?? [];
    expect(seen.length).toBeGreaterThanOrEqual(2);

    // The ladder must be 1, 2, 3, ... — each retry stamps the next integer
    // because Task.attempt_count is incremented monotonically by the
    // monitor between attempts.
    seen.forEach((value, index) => {
      expect(value).toBe(index + 1);
    });
    expect(ladder.latest).toBe(seen[seen.length - 1]);

    // Sanity-check that the canonical Task.attempt_count tracks what the
    // pusher stamped — the next attempt's pusher pass would have stamped
    // attempt_count + 1, so the latest seen attempt is at most the
    // canonical count.
    const finalTask = await getTask(request, enqueued.task_id);
    expect(finalTask.found).toBe(true);
    expect(finalTask.attempt_count).toBeGreaterThanOrEqual(seen.length);
  });
});
