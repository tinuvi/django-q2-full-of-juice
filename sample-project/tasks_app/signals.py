"""Wire django-q2 lifecycle signals to file-cache counters for E2E.

The signals fire in different processes:

- pre_enqueue: web (producer)
- pre_execute: worker process (one of N)
- post_execute: monitor process (singleton)
- post_execute_in_worker: worker process (one of N)
- pre_chain_progress / post_chain_progress: monitor process (singleton)

Because the workers run in separate processes from the web container, we need
a cross-process counter. The file-backed Django cache (configured in
sample/settings.py) is the simplest shared store available; we store one set
of seen task ids per signal so the count is `len(set)` rather than a racy
read-modify-write integer.

Two further artifacts pertain to the new signals added in this branch:

- A per-task **exception snapshot** captured from the live `exc_info` triple
  passed to `post_execute_in_worker`. We can't pickle the exception object
  across the file cache reliably, so we store the structured pieces — the
  class name, message, and a boolean for "did we receive a traceback object"
  — proving the kwarg flowed through with a live exception (not just the
  formatted string from ``task["result"]``).
- A **chain progress log** of `(signal_name, task_id, group_id)` tuples
  appended in order each time pre/post_chain_progress fires. The E2E suite
  asserts the pre/post pairs straddle each link transition of a chain.
"""

import logging

from django.core.cache import cache

from django_q.signals import (
    post_chain_progress,
    post_execute,
    post_execute_in_worker,
    pre_chain_progress,
    pre_enqueue,
    pre_execute,
)

_logger = logging.getLogger("tasks_app")

SIGNAL_NAMES = (
    "pre_enqueue",
    "pre_execute",
    "post_execute",
    "post_execute_in_worker",
    "pre_chain_progress",
    "post_chain_progress",
)
SIGNAL_KEY_PREFIX = "signal-seen"
SIGNAL_KEY_TIMEOUT = 600
EXCEPTION_KEY_PREFIX = "exception-snapshot"
EXCEPTION_KEY_TIMEOUT = 600
CHAIN_LOG_KEY = "chain-progress-log"
CHAIN_LOG_TIMEOUT = 600


def _seen_key(signal_name):
    return f"{SIGNAL_KEY_PREFIX}:{signal_name}"


def _record(signal_name, task_id):
    if not task_id:
        return
    key = _seen_key(signal_name)
    # Single read-write per handler invocation. Per-signal contention is low:
    # pre_enqueue runs in one process, post_execute in one process, and
    # pre_execute is per-worker but worker callbacks are serialized per
    # process. The E2E test waits for each task to finish before enqueueing
    # the next, so worker concurrency does not collide here.
    seen = cache.get(key) or set()
    if task_id in seen:
        return
    seen.add(task_id)
    cache.set(key, seen, timeout=SIGNAL_KEY_TIMEOUT)


def _exception_key(task_id):
    return f"{EXCEPTION_KEY_PREFIX}:{task_id}"


def _record_exception_snapshot(task, exc_info):
    """Persist a JSON-safe summary of a live exc_info triple keyed by task id."""
    task_id = task.get("id")
    if not task_id or not exc_info:
        return
    exc_type, exc_value, exc_tb = exc_info
    snapshot = {
        "task_id": task_id,
        "task_name": task.get("name"),
        "exception_type": getattr(exc_type, "__name__", repr(exc_type)),
        "exception_module": getattr(exc_type, "__module__", None),
        "exception_message": str(exc_value) if exc_value is not None else None,
        "has_traceback": exc_tb is not None,
        "exception_repr": repr(exc_value),
    }
    cache.set(_exception_key(task_id), snapshot, timeout=EXCEPTION_KEY_TIMEOUT)


def _append_chain_event(signal_name, task):
    """Append an event tuple to the chain progress log.

    We use a small list rather than a set because order matters — the E2E
    suite asserts pre/post pairing. The list is read-modify-write but the
    monitor process is a singleton, so contention is impossible here.
    """
    log = cache.get(CHAIN_LOG_KEY) or []
    log.append(
        {
            "signal": signal_name,
            "task_id": task.get("id"),
            "task_name": task.get("name"),
            "group": task.get("group"),
            "remaining_chain_length": len(task.get("chain") or []),
        }
    )
    cache.set(CHAIN_LOG_KEY, log, timeout=CHAIN_LOG_TIMEOUT)


def _on_pre_enqueue(sender, task, **kwargs):
    _record("pre_enqueue", task.get("id"))


def _on_pre_execute(sender, func, task, **kwargs):
    _record("pre_execute", task.get("id"))


def _on_post_execute(sender, task, **kwargs):
    _record("post_execute", task.get("id"))


def _on_post_execute_in_worker(sender, func, task, exc_info=None, **kwargs):
    _record("post_execute_in_worker", task.get("id"))
    if exc_info is not None:
        _record_exception_snapshot(task, exc_info)


def _on_pre_chain_progress(sender, task, **kwargs):
    _record("pre_chain_progress", task.get("id"))
    _append_chain_event("pre_chain_progress", task)


def _on_post_chain_progress(sender, task, **kwargs):
    _record("post_chain_progress", task.get("id"))
    _append_chain_event("post_chain_progress", task)


def connect():
    """Connect all handlers. Idempotent thanks to `dispatch_uid`."""
    pre_enqueue.connect(_on_pre_enqueue, dispatch_uid="tasks_app.pre_enqueue")
    pre_execute.connect(_on_pre_execute, dispatch_uid="tasks_app.pre_execute")
    post_execute.connect(_on_post_execute, dispatch_uid="tasks_app.post_execute")
    post_execute_in_worker.connect(
        _on_post_execute_in_worker,
        dispatch_uid="tasks_app.post_execute_in_worker",
    )
    pre_chain_progress.connect(
        _on_pre_chain_progress,
        dispatch_uid="tasks_app.pre_chain_progress",
    )
    post_chain_progress.connect(
        _on_post_chain_progress,
        dispatch_uid="tasks_app.post_chain_progress",
    )
    _logger.info("django-q2 lifecycle signals connected")


def signal_counts():
    """Return current per-signal counts. Used by the /api/signal-counts/ endpoint."""
    return {name: len(cache.get(_seen_key(name)) or set()) for name in SIGNAL_NAMES}


def reset_signal_counts():
    for name in SIGNAL_NAMES:
        cache.delete(_seen_key(name))
    cache.delete(CHAIN_LOG_KEY)


def exception_snapshot(task_id):
    """Return the stored exc_info snapshot for a task, or None."""
    return cache.get(_exception_key(task_id))


def chain_progress_log():
    """Return the ordered list of chain progress events."""
    return cache.get(CHAIN_LOG_KEY) or []


def reset_chain_progress_log():
    cache.delete(CHAIN_LOG_KEY)
