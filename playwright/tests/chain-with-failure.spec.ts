import { expect, test } from '@playwright/test';

import { enqueueChain, waitForGroupCount } from '../helpers/api';

test.describe('async_chain with a failing middle task', () => {
  test('the chain continues past the failure; all three tasks land in the same group', async ({
    request,
  }) => {
    // monitor.save_task() enqueues the next link in the chain unconditionally
    // — regardless of whether the current task succeeded. This spec pins
    // that contract: a chain of [add, boom, add] yields three Task rows in
    // the same group with success=[true, false, true].
    const enqueued = await enqueueChain(request, [
      { task: 'add', args: [1, 2] },
      { task: 'boom' },
      { task: 'add', args: [10, 20] },
    ]);
    expect(enqueued.chain_length).toBe(3);

    const finalGroup = await waitForGroupCount(request, enqueued.group_id, 3, {
      timeoutMs: 60_000,
    });
    expect(finalGroup.count).toBe(3);
    expect(finalGroup.success_count).toBe(2);
    expect(finalGroup.failure_count).toBe(1);

    const adds = finalGroup.tasks.filter(t => t.success === true);
    const booms = finalGroup.tasks.filter(t => t.success === false);
    expect(adds.map(t => t.result).sort()).toEqual([3, 30]);
    expect(booms).toHaveLength(1);
    expect(typeof booms[0].result).toBe('string');
    expect(booms[0].result as string).toContain('RuntimeError');
  });
});
