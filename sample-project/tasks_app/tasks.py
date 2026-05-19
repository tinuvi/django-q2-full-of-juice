"""Task functions enqueued by the sample API. Kept thin on purpose."""

import logging
import time

from django_q.tasks import async_task

_logger = logging.getLogger("tasks_app")


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


TASK_REGISTRY = {
    "noop": "tasks_app.tasks.noop",
    "add": "tasks_app.tasks.add",
    "boom": "tasks_app.tasks.boom",
    "concat": "tasks_app.tasks.concat",
    "slow_noop": "tasks_app.tasks.slow_noop",
    "cascade": "tasks_app.tasks.cascade",
}
