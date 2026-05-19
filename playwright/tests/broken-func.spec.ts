import { expect, test } from '@playwright/test';

import { enqueue, waitForTask } from '../helpers/api';

test.describe('broken function dotted path', () => {
  test('an unresolvable dotted path lands as a failure with the expected error', async ({
    request,
  }) => {
    // The `missing` task alias in TASK_REGISTRY points at
    // `tasks_app.tasks.does_not_exist` — `pydoc.locate` returns None in the
    // worker, and worker.py raises ValueError("Function ... is not
    // defined"). Verifies the un-importable-callable path end-to-end.
    const enqueued = await enqueue(request, { task: 'missing' });
    const finished = await waitForTask(request, enqueued.task_id);

    expect(finished.success).toBe(false);
    expect(typeof finished.result).toBe('string');
    expect(finished.result as string).toContain('is not defined');
    expect(finished.result as string).toContain('tasks_app.tasks.does_not_exist');
  });
});
