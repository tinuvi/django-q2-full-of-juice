import { expect, test } from '@playwright/test';

import { enqueueIter, waitForTask } from '../helpers/api';

test.describe('async_iter', () => {
  test('coalesces N sub-task results into a single Task whose id equals the iter_group', async ({
    request,
  }) => {
    const batch = [['iter-a'], ['iter-b'], ['iter-c'], ['iter-d']];
    const enqueued = await enqueueIter(request, 'noop', batch);
    expect(enqueued.iter_count).toBe(4);

    // django-q2's async_iter coalescer stores the combined task under id==iter_group.
    const finished = await waitForTask(request, enqueued.iter_group);
    expect(finished.success).toBe(true);

    // Result is a list of the 4 sub-task results. Each sub-task is noop, which
    // returns {args, kwargs}. The list order is the worker completion order so
    // we assert by set membership instead.
    expect(Array.isArray(finished.result)).toBe(true);
    const result = finished.result as Array<{ args: string[] }>;
    expect(result).toHaveLength(4);
    const flatArgs = result.flatMap(entry => entry.args);
    expect(flatArgs.sort()).toEqual(['iter-a', 'iter-b', 'iter-c', 'iter-d']);
  });
});
