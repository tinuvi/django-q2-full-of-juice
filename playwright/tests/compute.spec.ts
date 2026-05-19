import { expect, test } from '@playwright/test';

import { enqueue, waitForTask } from '../helpers/api';

test.describe('task return values', () => {
  test('add(x, y) returns the sum', async ({ request }) => {
    const enqueued = await enqueue(request, { task: 'add', args: [40, 2] });
    const finished = await waitForTask(request, enqueued.task_id);

    expect(finished.success).toBe(true);
    expect(finished.result).toBe(42);
  });

  test('concat joins positional parts with the kwarg separator', async ({ request }) => {
    const enqueued = await enqueue(request, {
      task: 'concat',
      args: ['a', 'b', 'c'],
      kwargs: { separator: '::' },
    });
    const finished = await waitForTask(request, enqueued.task_id);

    expect(finished.success).toBe(true);
    expect(finished.result).toBe('a::b::c');
  });
});
