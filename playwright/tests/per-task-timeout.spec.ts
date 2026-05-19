import { expect, test } from '@playwright/test';

import { enqueue, waitForTask } from '../helpers/api';

test.describe('per-task timeout', () => {
  test('TimeoutHandler kills the worker mid-task and the pool recovers', async ({
    request,
  }) => {
    // slow_noop(5s) will hit the 2s per-task timeout, raising
    // TimeoutException. django-q2 force-recycles the worker in that case
    // (worker.py:122-126), so we also verify a follow-up task succeeds —
    // proves the cluster brought a replacement worker online.
    const offender = await enqueue(request, {
      task: 'slow_noop',
      args: ['will-time-out', 5],
      timeout: 2,
    });

    const failed = await waitForTask(request, offender.task_id, {
      timeoutMs: 30_000,
    });
    expect(failed.success).toBe(false);
    // django-q2 stores `f"{exc} : {traceback}"` as Task.result on failure.
    expect(typeof failed.result).toBe('string');
    expect(failed.result as string).toContain('TimeoutException');

    const followUp = await enqueue(request, { task: 'add', args: [1, 1] });
    const followUpDone = await waitForTask(request, followUp.task_id, {
      timeoutMs: 30_000,
    });
    expect(followUpDone.success).toBe(true);
    expect(followUpDone.result).toBe(2);
  });
});
