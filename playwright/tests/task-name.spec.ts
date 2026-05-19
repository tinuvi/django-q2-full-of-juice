import { expect, test } from '@playwright/test';

import { enqueue, getTask, waitForTask } from '../helpers/api';
import { unique } from '../helpers/data';

test.describe('custom task_name', () => {
  test('Task is retrievable by both task_id and the human-readable name', async ({
    request,
  }) => {
    const taskName = unique('renamed');
    const enqueued = await enqueue(request, {
      task: 'add',
      args: [3, 4],
      task_name: taskName,
    });
    expect(enqueued.task_name).toBe(taskName);

    const finishedById = await waitForTask(request, enqueued.task_id);
    expect(finishedById.success).toBe(true);
    expect(finishedById.name).toBe(taskName);
    expect(finishedById.result).toBe(7);

    // Task.get_task() falls through to a name lookup if the 32-char id
    // doesn't match — that's the path being exercised here.
    const byName = await getTask(request, taskName);
    expect(byName.found).toBe(true);
    expect(byName.id).toBe(enqueued.task_id);
    expect(byName.result).toBe(7);
  });
});
