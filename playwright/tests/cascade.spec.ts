import { expect, test } from '@playwright/test';

import { enqueue, waitForTask } from '../helpers/api';

test.describe('cascade', () => {
  test('a task that enqueues a child completes and the child runs too', async ({ request }) => {
    const enqueued = await enqueue(request, { task: 'cascade', args: ['parent-payload'] });

    const parent = await waitForTask(request, enqueued.task_id);
    expect(parent.success).toBe(true);

    const parentResult = parent.result as { payload: string; child_task_id: string };
    expect(parentResult.payload).toBe('parent-payload');
    expect(parentResult.child_task_id).toBeTruthy();

    const child = await waitForTask(request, parentResult.child_task_id);
    expect(child.success).toBe(true);
    // cascade enqueues `noop("parent-payload", parent="cascade")`.
    expect(child.result).toMatchObject({
      args: ['parent-payload'],
      kwargs: { parent: 'cascade' },
    });
  });
});
