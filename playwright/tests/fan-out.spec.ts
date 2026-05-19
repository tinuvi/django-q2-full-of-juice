import { expect, test } from '@playwright/test';

import { enqueue, waitForGroupCount } from '../helpers/api';
import { unique } from '../helpers/data';

test.describe('fan-out via shared group', () => {
  test('many tasks under the same group all complete successfully', async ({ request }) => {
    const groupName = unique('fanout');
    const fanOut = 6;

    await Promise.all(
      Array.from({ length: fanOut }).map((_, i) =>
        enqueue(request, {
          task: 'noop',
          args: [`payload-${i}`],
          group: groupName,
        }),
      ),
    );

    const group = await waitForGroupCount(request, groupName, fanOut, { timeoutMs: 90_000 });
    expect(group.count).toBe(fanOut);
    expect(group.success_count).toBe(fanOut);
    expect(group.failure_count).toBe(0);

    const payloads = group.tasks
      .map(t => (t.result as { args: string[] }).args[0])
      .sort();
    expect(payloads).toEqual(
      Array.from({ length: fanOut }, (_, i) => `payload-${i}`).sort(),
    );
  });
});
