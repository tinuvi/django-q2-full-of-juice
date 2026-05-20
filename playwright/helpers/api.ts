import { APIRequestContext, expect } from '@playwright/test';

/**
 * Thin wrappers over sample-project's HTTP surface. They exist so each
 * .spec.ts file reads as the behavior under test rather than HTTP plumbing.
 */

export interface EnqueueBody {
  task: string;
  args?: unknown[];
  kwargs?: Record<string, unknown>;
  group?: string;
  task_name?: string;
  hook?: string;
  timeout?: number;
  save?: boolean;
  ack_failure?: boolean;
}

export interface EnqueueResponse {
  task_id: string;
  task: string;
  group: string | null;
  task_name: string | null;
}

export async function enqueue(
  request: APIRequestContext,
  body: EnqueueBody,
): Promise<EnqueueResponse> {
  const response = await request.post('/api/enqueue/', { data: body });
  expect(response.ok(), `POST /api/enqueue/ failed: ${response.status()}`).toBeTruthy();
  return (await response.json()) as EnqueueResponse;
}

export interface ChainEntry {
  task: string;
  args?: unknown[];
  kwargs?: Record<string, unknown>;
}

export async function enqueueChain(
  request: APIRequestContext,
  chain: ChainEntry[],
): Promise<{ group_id: string; chain_length: number }> {
  const response = await request.post('/api/enqueue-chain/', { data: { chain } });
  expect(response.ok(), `POST /api/enqueue-chain/ failed: ${response.status()}`).toBeTruthy();
  return (await response.json()) as { group_id: string; chain_length: number };
}

export async function enqueueIter(
  request: APIRequestContext,
  task: string,
  args_iter: unknown[][],
): Promise<{ iter_group: string; iter_count: number }> {
  const response = await request.post('/api/enqueue-iter/', { data: { task, args_iter } });
  expect(response.ok(), `POST /api/enqueue-iter/ failed: ${response.status()}`).toBeTruthy();
  return (await response.json()) as { iter_group: string; iter_count: number };
}

export interface ScheduleOnceBody {
  task: string;
  args?: unknown[];
  kwargs?: Record<string, unknown>;
  name?: string;
  run_in_secs?: number;
  hook?: string;
  intended_date_kwarg?: string;
}

export async function scheduleOnce(
  request: APIRequestContext,
  body: ScheduleOnceBody,
): Promise<{ schedule_id: number; name: string | null; next_run: string }> {
  const response = await request.post('/api/schedule-once/', { data: body });
  expect(response.ok(), `POST /api/schedule-once/ failed: ${response.status()}`).toBeTruthy();
  return (await response.json()) as { schedule_id: number; name: string | null; next_run: string };
}

export interface ScheduleCronBody {
  task: string;
  cron: string;
  args?: unknown[];
  kwargs?: Record<string, unknown>;
  name?: string;
  hook?: string;
}

export async function scheduleCron(
  request: APIRequestContext,
  body: ScheduleCronBody,
): Promise<{ schedule_id: number; name: string | null; next_run: string | null; cron: string }> {
  const response = await request.post('/api/schedule-cron/', { data: body });
  expect(response.ok(), `POST /api/schedule-cron/ failed: ${response.status()}`).toBeTruthy();
  return (await response.json()) as {
    schedule_id: number;
    name: string | null;
    next_run: string | null;
    cron: string;
  };
}

export interface ScheduleRecurringBody {
  task: string;
  minutes: number;
  repeats: number;
  args?: unknown[];
  kwargs?: Record<string, unknown>;
  name?: string;
  hook?: string;
}

export async function scheduleRecurring(
  request: APIRequestContext,
  body: ScheduleRecurringBody,
): Promise<{
  schedule_id: number;
  name: string | null;
  next_run: string;
  minutes: number;
  repeats: number;
}> {
  const response = await request.post('/api/schedule-recurring/', { data: body });
  expect(
    response.ok(),
    `POST /api/schedule-recurring/ failed: ${response.status()}`,
  ).toBeTruthy();
  return (await response.json()) as {
    schedule_id: number;
    name: string | null;
    next_run: string;
    minutes: number;
    repeats: number;
  };
}

export interface TaskState {
  found: boolean;
  id?: string;
  name?: string;
  func?: string;
  group?: string | null;
  success?: boolean | null;
  attempt_count?: number;
  started?: string | null;
  stopped?: string | null;
  result?: unknown;
}

export interface GroupState {
  group: string;
  count: number;
  success_count: number;
  failure_count: number;
  tasks: TaskState[];
}

export interface ScheduleState {
  found: boolean;
  schedule_id?: number;
  name?: string | null;
  func?: string;
  schedule_type?: string;
  repeats?: number;
  next_run?: string | null;
  last_task_id?: string | null;
  cron?: string | null;
  minutes?: number | null;
  intended_date_kwarg?: string | null;
}

export interface HookAuditState {
  found: boolean;
  task_id?: string;
  name?: string;
  func?: string;
  success?: boolean | null;
  result?: unknown;
}

export interface SignalCounts {
  pre_enqueue: number;
  pre_execute: number;
  post_execute: number;
  post_execute_in_worker: number;
  pre_chain_progress: number;
  post_chain_progress: number;
}

export interface ExceptionSnapshot {
  found: boolean;
  task_id: string;
  task_name?: string;
  exception_type?: string;
  exception_module?: string;
  exception_message?: string;
  has_traceback?: boolean;
  exception_repr?: string;
}

export interface ChainProgressEvent {
  signal: 'pre_chain_progress' | 'post_chain_progress';
  task_id: string;
  task_name: string | null;
  group: string | null;
  remaining_chain_length: number;
}

export interface ChainProgressLog {
  events: ChainProgressEvent[];
}

export interface TaskAttemptLadder {
  found: boolean;
  task_id: string;
  attempts_seen?: number[];
  latest?: number;
}

async function getJson<T>(request: APIRequestContext, url: string, expectOk = true): Promise<T> {
  const response = await request.get(url);
  if (expectOk) {
    expect(response.ok(), `GET ${url} failed: ${response.status()}`).toBeTruthy();
  }
  return (await response.json()) as T;
}

export function getTask(request: APIRequestContext, taskId: string): Promise<TaskState> {
  return getJson<TaskState>(request, `/api/task/${taskId}/`);
}

export function getGroup(request: APIRequestContext, groupName: string): Promise<GroupState> {
  return getJson<GroupState>(request, `/api/group/${groupName}/`);
}

export async function getSchedule(
  request: APIRequestContext,
  scheduleId: number,
): Promise<ScheduleState> {
  // The endpoint returns 404 if the schedule was deleted (one-shot schedules
  // get cleaned up after firing when repeats==0), so we can't unconditionally
  // assert .ok() here.
  const response = await request.get(`/api/schedule/${scheduleId}/`);
  return (await response.json()) as ScheduleState;
}

export function getHookAudit(
  request: APIRequestContext,
  taskId: string,
): Promise<HookAuditState> {
  return getJson<HookAuditState>(request, `/api/hook-audit/${taskId}/`);
}

export function getSignalCounts(request: APIRequestContext): Promise<SignalCounts> {
  return getJson<SignalCounts>(request, '/api/signal-counts/');
}

export function getExceptionSnapshot(
  request: APIRequestContext,
  taskId: string,
): Promise<ExceptionSnapshot> {
  return getJson<ExceptionSnapshot>(request, `/api/exception-snapshot/${taskId}/`);
}

export function getChainProgressLog(
  request: APIRequestContext,
): Promise<ChainProgressLog> {
  return getJson<ChainProgressLog>(request, '/api/chain-progress/');
}

export function getTaskAttempts(
  request: APIRequestContext,
  taskId: string,
): Promise<TaskAttemptLadder> {
  return getJson<TaskAttemptLadder>(request, `/api/task-attempts/${taskId}/`);
}

export async function resetChainProgressLog(
  request: APIRequestContext,
): Promise<ChainProgressLog & { reset: boolean }> {
  const response = await request.post('/api/chain-progress/reset/');
  expect(
    response.ok(),
    `POST /api/chain-progress/reset/ failed: ${response.status()}`,
  ).toBeTruthy();
  return (await response.json()) as ChainProgressLog & { reset: boolean };
}

export async function deleteGroup(
  request: APIRequestContext,
  groupName: string,
  { tasks = false }: { tasks?: boolean } = {},
): Promise<{ group: string; deleted_tasks: boolean }> {
  const url = `/api/group/${groupName}/${tasks ? '?tasks=true' : ''}`;
  const response = await request.delete(url);
  expect(response.ok(), `DELETE ${url} failed: ${response.status()}`).toBeTruthy();
  return (await response.json()) as { group: string; deleted_tasks: boolean };
}

export function getQueueSize(request: APIRequestContext): Promise<{ size: number }> {
  return getJson<{ size: number }>(request, '/api/queue-size/');
}

export async function resetSignalCounts(
  request: APIRequestContext,
): Promise<SignalCounts & { reset: boolean }> {
  const response = await request.post('/api/signal-counts/reset/');
  expect(
    response.ok(),
    `POST /api/signal-counts/reset/ failed: ${response.status()}`,
  ).toBeTruthy();
  return (await response.json()) as SignalCounts & { reset: boolean };
}

interface WaitOptions {
  timeoutMs?: number;
  pollMs?: number;
  description?: string;
}

/**
 * Poll a thunk until it returns a truthy value or the timeout elapses.
 * The last polled value is included in the assertion message on timeout so
 * test failures show *what* state the system was stuck in.
 */
export async function waitUntil<T>(
  probe: () => Promise<T | null | undefined>,
  predicate: (value: T) => boolean,
  { timeoutMs = 60_000, pollMs = 500, description = 'waitUntil' }: WaitOptions = {},
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  let last: T | null | undefined;
  while (Date.now() < deadline) {
    last = await probe();
    if (last && predicate(last)) {
      return last;
    }
    await new Promise(resolve => setTimeout(resolve, pollMs));
  }
  throw new Error(`${description} timed out after ${timeoutMs}ms — last value: ${JSON.stringify(last)}`);
}

export function waitForTask(
  request: APIRequestContext,
  taskId: string,
  options: WaitOptions = {},
): Promise<TaskState> {
  return waitUntil(
    () => getTask(request, taskId),
    state => state.found === true && state.stopped !== null,
    { description: `task ${taskId} to finish`, ...options },
  );
}

export function waitForGroupCount(
  request: APIRequestContext,
  groupName: string,
  expectedCount: number,
  options: WaitOptions = {},
): Promise<GroupState> {
  return waitUntil(
    () => getGroup(request, groupName),
    state => state.count >= expectedCount,
    { description: `group ${groupName} to reach ${expectedCount} tasks`, ...options },
  );
}
