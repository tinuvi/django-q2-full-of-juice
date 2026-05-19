import { expect, test } from '@playwright/test';

import { enqueueChain, waitForGroupCount } from '../helpers/api';

test.describe('async_chain', () => {
  test('all chained tasks run and land in the same group', async ({ request }) => {
    const enqueued = await enqueueChain(request, [
      { task: 'add', args: [1, 2] },
      { task: 'add', args: [10, 20] },
      { task: 'concat', args: ['a', 'b'] },
    ]);
    expect(enqueued.chain_length).toBe(3);

    const finalGroup = await waitForGroupCount(request, enqueued.group_id, 3);

    expect(finalGroup.count).toBe(3);
    expect(finalGroup.success_count).toBe(3);
    expect(finalGroup.failure_count).toBe(0);

    // The three results should be: 3, 30, "a-b" — but order is the order of
    // completion as stored by django-q2, not necessarily the chain order. We
    // assert by set membership.
    const results = finalGroup.tasks.map(t => t.result);
    expect(results).toEqual(expect.arrayContaining([3, 30, 'a-b']));
  });
});
