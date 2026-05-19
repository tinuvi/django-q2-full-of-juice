import { expect, test } from '@playwright/test';

import { enqueue, waitForTask } from '../helpers/api';

test.describe('task failure', () => {
  test('boom() lands with success=false and traceback as result', async ({ request }) => {
    const enqueued = await enqueue(request, { task: 'boom' });
    const finished = await waitForTask(request, enqueued.task_id);

    expect(finished.success).toBe(false);
    expect(finished.attempt_count).toBeGreaterThanOrEqual(1);
    // django-q2 stores the formatted traceback string as Task.result on failure.
    expect(typeof finished.result).toBe('string');
    expect(finished.result as string).toContain('RuntimeError');
    expect(finished.result as string).toContain('boom!');
  });
});
