import { expect, test } from '@playwright/test';

import {
  enqueueChain,
  getChainProgressLog,
  resetChainProgressLog,
  waitForGroupCount,
  waitUntil,
} from '../helpers/api';

test.describe('pre/post_chain_progress signals', () => {
  test('paired pre/post events straddle each link transition of a chain', async ({
    request,
  }) => {
    // The chain-progress log is process-shared (file cache) and append-only.
    // Reset it before this spec so unrelated chains from other specs don't
    // bleed into our assertions.
    await resetChainProgressLog(request);

    const enqueued = await enqueueChain(request, [
      { task: 'add', args: [1, 2] },
      { task: 'add', args: [10, 20] },
      { task: 'concat', args: ['a', 'b'] },
    ]);
    expect(enqueued.chain_length).toBe(3);

    const finalGroup = await waitForGroupCount(request, enqueued.group_id, 3, {
      timeoutMs: 60_000,
    });
    expect(finalGroup.success_count).toBe(3);

    // The monitor fires pre_chain_progress + post_chain_progress around each
    // call to async_chain(). For a chain of length 3 the monitor advances
    // the chain twice — after link 1 (queues link 2) and after link 2
    // (queues link 3). The final link has no chain to progress, so no third
    // pair fires.
    const log = await waitUntil(
      () => getChainProgressLog(request),
      state =>
        state.events.filter(e => e.group === enqueued.group_id).length >= 4,
      {
        description: `pre/post_chain_progress to fire for group ${enqueued.group_id}`,
        timeoutMs: 30_000,
      },
    );

    const events = log.events.filter(e => e.group === enqueued.group_id);
    expect(events).toHaveLength(4);

    // Each pre must be immediately followed by a post for the same task id.
    expect(events[0].signal).toBe('pre_chain_progress');
    expect(events[1].signal).toBe('post_chain_progress');
    expect(events[1].task_id).toBe(events[0].task_id);

    expect(events[2].signal).toBe('pre_chain_progress');
    expect(events[3].signal).toBe('post_chain_progress');
    expect(events[3].task_id).toBe(events[2].task_id);

    // The two transitions correspond to two different completed tasks.
    expect(events[0].task_id).not.toBe(events[2].task_id);

    // The remaining_chain_length is read from `task["chain"]`, which
    // `async_chain` mutates in place via `chain.pop(0)`. So within a single
    // pair the length decreases by 1 between pre (before the pop) and post
    // (after the pop). Across the two transitions: link 1 starts with [L2,
    // L3] (len 2) and post-progression has [L3] (len 1); link 2 starts with
    // [L3] (len 1) and ends with [] (len 0).
    expect(events[0].remaining_chain_length).toBe(2);
    expect(events[1].remaining_chain_length).toBe(1);
    expect(events[2].remaining_chain_length).toBe(1);
    expect(events[3].remaining_chain_length).toBe(0);
  });

  test('a non-chain task does not fire pre/post_chain_progress', async ({
    request,
  }) => {
    // Reset, enqueue a plain task, ensure no chain-progress events ever land
    // for it. The OTel use case relies on this: we only want the hook on
    // chain transitions, not on every monitor.save_task() call.
    await resetChainProgressLog(request);

    const enqueued = await enqueueChain(request, [
      { task: 'add', args: [3, 4] },
    ]);
    expect(enqueued.chain_length).toBe(1);
    await waitForGroupCount(request, enqueued.group_id, 1);

    // Give the monitor a beat to write any chain-progress events it might
    // (incorrectly) emit, then read the log once. We do *not* poll for a
    // condition here — we want the assertion to fail loudly if the signal
    // fires when it shouldn't.
    await new Promise(resolve => setTimeout(resolve, 1500));
    const log = await getChainProgressLog(request);
    const events = log.events.filter(e => e.group === enqueued.group_id);
    expect(events).toHaveLength(0);
  });
});
