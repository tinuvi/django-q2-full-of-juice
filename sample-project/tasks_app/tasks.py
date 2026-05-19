"""Task functions enqueued by the sample API. Kept thin on purpose."""

import logging
import time

from django.core.cache import cache

from django_q.tasks import async_task

_logger = logging.getLogger("tasks_app")

HOOK_AUDIT_PREFIX = "hook-audit"
HOOK_AUDIT_TIMEOUT = 600


def noop(*args, **kwargs):
    return {"args": list(args), "kwargs": kwargs}


def add(x, y):
    return x + y


def boom():
    raise RuntimeError("boom!")


def concat(*parts, separator="-"):
    return separator.join(str(p) for p in parts)


def slow_noop(payload, seconds):
    time.sleep(seconds)
    return payload


def cascade(payload):
    """Enqueue a child noop task while running. Useful to verify that a worker
    process can act as a producer for another task without deadlocking."""
    child_task_id = async_task("tasks_app.tasks.noop", payload, parent="cascade")
    return {"payload": payload, "child_task_id": child_task_id}


def record_hook(task):
    """Result hook invoked by django-q2 via the Task post_save signal.

    Receives the saved `django_q.models.Task` instance. We stash a small
    JSON-safe audit dict in the shared cache so the E2E suite can verify the
    hook actually fired with the expected task state.
    """
    audit = {
        "task_id": task.id,
        "name": task.name,
        "func": task.func,
        "success": task.success,
        "result": task.result,
    }
    cache.set(f"{HOOK_AUDIT_PREFIX}:{task.id}", audit, timeout=HOOK_AUDIT_TIMEOUT)
    _logger.info("record_hook fired for task %s success=%s", task.id, task.success)


TASK_REGISTRY = {
    "noop": "tasks_app.tasks.noop",
    "add": "tasks_app.tasks.add",
    "boom": "tasks_app.tasks.boom",
    "concat": "tasks_app.tasks.concat",
    "slow_noop": "tasks_app.tasks.slow_noop",
    "cascade": "tasks_app.tasks.cascade",
    # Intentionally points at a function that does not exist. The web layer
    # accepts it (it's a registered alias), but pydoc.locate returns None in
    # the worker, so django-q2 raises `ValueError("Function ... is not
    # defined")` (worker.py). `broken-func.spec.ts` relies on this.
    "missing": "tasks_app.tasks.does_not_exist",
}

HOOK_REGISTRY = {
    "record_hook": "tasks_app.tasks.record_hook",
}
