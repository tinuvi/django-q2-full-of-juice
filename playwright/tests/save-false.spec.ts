import { expect, test } from '@playwright/test';

import {
  enqueue,
  getSignalCounts,
  getTask,
  resetSignalCounts,
  waitUntil,
} from '../helpers/api';

test.describe('save=False (fire-and-forget)', () => {
  test('Task row is not persisted, but the post_execute signal still fires', async ({
    request,
  }) => {
    // save=False short-circuits monitor.save_task() before any Task row is
    // created — and because the result-hook is dispatched via Task.post_save
    // (signals.py), hooks ALSO don't fire when save=False. The only
    // observation channel that still works is the post_execute signal, which
    // monitor.py emits regardless of whether the row was saved.
    // Read the baseline after reset (a prior spec's in-flight post_execute
    // may still trickle in *just* after the reset; we measure deltas to
    // sidestep that race entirely).
    await resetSignalCounts(request);
    const before = await getSignalCounts(request);

    const enqueued = await enqueue(request, {
      task: 'add',
      args: [100, 23],
      save: false,
    });

    // Wait for monitor.post_execute to fire — proves the task actually ran.
    await waitUntil(
      () => getSignalCounts(request),
      counts => counts.post_execute >= before.post_execute + 1,
      {
        description: 'post_execute signal to fire for save=False task',
        timeoutMs: 30_000,
      },
    );

    // Give django-q2 a moment longer in case a Task row is created on a
    // slight lag, then assert it really was skipped.
    await new Promise(resolve => setTimeout(resolve, 1_500));
    const lookup = await getTask(request, enqueued.task_id);
    expect(lookup.found).toBe(false);
  });
});
