import { expect, test } from '@playwright/test';

import { enqueue, getHookAudit, waitForTask, waitUntil } from '../helpers/api';

test.describe('result hook callback', () => {
  test('hook fires with the saved Task and sees the final result', async ({ request }) => {
    const enqueued = await enqueue(request, {
      task: 'add',
      args: [19, 23],
      hook: 'record_hook',
    });

    const finished = await waitForTask(request, enqueued.task_id);
    expect(finished.success).toBe(true);
    expect(finished.result).toBe(42);

    // The hook runs via Task.post_save in the monitor process. Polling for the
    // audit record decouples the test from the few-ms ordering between
    // monitor.save_task() and the post_save handler.
    const audit = await waitUntil(
      () => getHookAudit(request, enqueued.task_id),
      state => state.found === true,
      { description: `hook audit for ${enqueued.task_id}`, timeoutMs: 30_000 },
    );

    expect(audit.task_id).toBe(enqueued.task_id);
    expect(audit.func).toBe('tasks_app.tasks.add');
    expect(audit.success).toBe(true);
    expect(audit.result).toBe(42);
  });
});
