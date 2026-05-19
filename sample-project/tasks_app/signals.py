"""Wire django-q2 lifecycle signals to file-cache counters for E2E.

The three signals fire in different processes:

- pre_enqueue: web (producer)
- pre_execute: worker process (one of N)
- post_execute: monitor process (singleton)

Because the workers run in separate processes from the web container, we need
a cross-process counter. The file-backed Django cache (configured in
sample/settings.py) is the simplest shared store available; we store one set
of seen task ids per signal so the count is `len(set)` rather than a racy
read-modify-write integer.
"""

import logging

from django.core.cache import cache

from django_q.signals import post_execute, pre_enqueue, pre_execute

_logger = logging.getLogger("tasks_app")

SIGNAL_NAMES = ("pre_enqueue", "pre_execute", "post_execute")
SIGNAL_KEY_PREFIX = "signal-seen"
SIGNAL_KEY_TIMEOUT = 600


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


def _on_pre_enqueue(sender, task, **kwargs):
    _record("pre_enqueue", task.get("id"))


def _on_pre_execute(sender, func, task, **kwargs):
    _record("pre_execute", task.get("id"))


def _on_post_execute(sender, task, **kwargs):
    _record("post_execute", task.get("id"))


def connect():
    """Connect all handlers. Idempotent thanks to `dispatch_uid`."""
    pre_enqueue.connect(_on_pre_enqueue, dispatch_uid="tasks_app.pre_enqueue")
    pre_execute.connect(_on_pre_execute, dispatch_uid="tasks_app.pre_execute")
    post_execute.connect(_on_post_execute, dispatch_uid="tasks_app.post_execute")
    _logger.info("django-q2 lifecycle signals connected")


def signal_counts():
    """Return current per-signal counts. Used by the /api/signal-counts/ endpoint."""
    return {name: len(cache.get(_seen_key(name)) or set()) for name in SIGNAL_NAMES}


def reset_signal_counts():
    for name in SIGNAL_NAMES:
        cache.delete(_seen_key(name))
