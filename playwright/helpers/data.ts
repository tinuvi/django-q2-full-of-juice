import { randomUUID } from 'node:crypto';

/**
 * Generate a unique correlation id for a scenario. Pass to /api/enqueue/ as
 * the `group` field when you need to query the group later by name.
 */
export function unique(prefix: string): string {
  return `${prefix}-${randomUUID()}`;
}
