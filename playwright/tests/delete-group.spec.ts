import { expect, test } from '@playwright/test';

import { deleteGroup, enqueue, getGroup, getTask, waitForGroupCount } from '../helpers/api';
import { unique } from '../helpers/data';

test.describe('delete_group', () => {
  test('without tasks=true unsets the group label but keeps the Task rows', async ({
    request,
  }) => {
    const groupName = unique('delete-no-tasks');
    const enqueued = await Promise.all(
      Array.from({ length: 4 }).map((_, i) =>
        enqueue(request, { task: 'noop', args: [`m-${i}`], group: groupName }),
      ),
    );
    await waitForGroupCount(request, groupName, 4);

    const result = await deleteGroup(request, groupName);
    expect(result.deleted_tasks).toBe(false);

    const groupAfter = await getGroup(request, groupName);
    expect(groupAfter.count).toBe(0);

    // Task rows survive — just with group=NULL.
    for (const e of enqueued) {
      const task = await getTask(request, e.task_id);
      expect(task.found).toBe(true);
      expect(task.group).toBeNull();
    }
  });

  test('with tasks=true also deletes the underlying Task rows', async ({ request }) => {
    const groupName = unique('delete-with-tasks');
    const enqueued = await Promise.all(
      Array.from({ length: 3 }).map((_, i) =>
        enqueue(request, { task: 'noop', args: [`m-${i}`], group: groupName }),
      ),
    );
    await waitForGroupCount(request, groupName, 3);

    const result = await deleteGroup(request, groupName, { tasks: true });
    expect(result.deleted_tasks).toBe(true);

    for (const e of enqueued) {
      const task = await getTask(request, e.task_id);
      expect(task.found).toBe(false);
    }
  });
});
