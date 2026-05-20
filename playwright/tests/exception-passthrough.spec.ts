import { expect, test } from '@playwright/test';

import {
  enqueue,
  getExceptionSnapshot,
  waitForTask,
  waitUntil,
} from '../helpers/api';

test.describe('post_execute_in_worker exc_info kwarg', () => {
  test('a failing task surfaces the live exception via exc_info', async ({
    request,
  }) => {
    // The legacy contract — formatted-string only — is already covered by
    // `failure.spec.ts`. This spec pins the new contract: a worker-process
    // receiver of post_execute_in_worker can call e.g.
    // `span.record_exception(exc_info[1])` and get structured data without
    // reparsing task["result"].
    const enqueued = await enqueue(request, { task: 'boom' });
    const finished = await waitForTask(request, enqueued.task_id);
    expect(finished.success).toBe(false);

    // The signal fires from the worker process; the snapshot is written to
    // the file-backed cache. Poll briefly so we don't race the writer.
    const snapshot = await waitUntil(
      () => getExceptionSnapshot(request, enqueued.task_id),
      state => state.found === true,
      {
        description: `exception snapshot for ${enqueued.task_id} to land`,
        timeoutMs: 15_000,
      },
    );

    expect(snapshot.task_id).toBe(enqueued.task_id);
    // Type and message come straight from the live exception object — not
    // parsed out of the traceback string.
    expect(snapshot.exception_type).toBe('RuntimeError');
    expect(snapshot.exception_message).toBe('boom!');
    expect(snapshot.has_traceback).toBe(true);
    expect(snapshot.exception_repr).toContain('RuntimeError');
    expect(snapshot.exception_repr).toContain('boom!');
  });

  test('a successful task records no exception snapshot', async ({ request }) => {
    // exc_info defaults to None on success, so the handler shouldn't write
    // anything. The endpoint returns found=false for an unknown task id.
    const enqueued = await enqueue(request, { task: 'add', args: [1, 2] });
    const finished = await waitForTask(request, enqueued.task_id);
    expect(finished.success).toBe(true);

    const snapshot = await getExceptionSnapshot(request, enqueued.task_id);
    expect(snapshot.found).toBe(false);
  });
});
