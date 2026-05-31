# Signals

## Available signals

Django Q2 emits the following signals during its lifecycle.

### Before enqueuing a task

The `django_q.signals.pre_enqueue` signal is emitted before a task is
enqueued. The task dictionary is given as the `task` argument.

### After spawning a worker process

The `django_q.signals.post_spawn` signal is emitted after a worker process has
spawned. The process name is given as the `proc_name` argument (string).

### Before executing a task

The `django_q.signals.pre_execute` signal is emitted before a task is
executed by a worker. This signal provides two arguments:

- `task`: the task dictionary.
- `func`: the actual function that will be executed. If the task was created
  with a function path, this argument will be the callable function
  nonetheless.

The `task` dictionary carries a `task["attempt"]` key stamped by the
pusher: `1` on first delivery and `N+1` on each broker re-delivery (the
pusher reads `django_q.models.Task.attempt_count` written by the monitor on
the previous attempt). Receivers wanting retry-aware behavior can branch on
`task.get("attempt", 1) > 1` without making their own database query. The
key defaults to `1` in sync mode (`Q_CLUSTER["sync"] = True`), since sync
mode bypasses the pusher and never re-delivers.

### After executing a task

- The `django_q.signals.post_execute_in_worker` signal is emitted after a task
  is executed by a worker and processed by the **worker**. It included the `task`
  dictionary with the result. Note that this signal is **emitted from, and handled
  by, the worker process itself**, not the monitor, unlike the `post_execute`
  signal below. The receiver also receives an `exc_info` keyword argument:
  `None` when the task succeeded, or a `(type, value, traceback)` triple
  mirroring `sys.exc_info()` when it raised. This lets observability tooling
  (e.g. OpenTelemetry's `span.record_exception`, Sentry's
  `capture_exception`) operate on the live exception object instead of
  reparsing the formatted string stored in `task["result"]`.
- The `django_q.signals.post_execute` signal is emitted after a task is
  executed by a worker and processed by the **monitor**. It included the `task`
  dictionary with the result.

### Around chain progression

The `django_q.signals.pre_chain_progress` and
`django_q.signals.post_chain_progress` signals are paired and emitted in the
**monitor process** immediately before and after `async_chain` enqueues the
next link of a chain. Both receive the just-finished `task` dictionary.

Chain progression happens in the monitor process rather than the worker that
finished the task, so any cross-process state an observer set up earlier in
the lifecycle (notably an OpenTelemetry trace context restored from
`task["otel_carrier"]`) needs a hook to be re-applied before the new link's
`pre_enqueue` fires. `pre_chain_progress` is that hook;
`post_chain_progress` is the paired tear-down. The post signal is fired from
a `finally` block, so observers can rely on it firing even if the inner
`async_chain` call raises.

## Subscribing to a signal

Connecting to a Django Q2 signal is done the same as any other Django
signal:

```python
from django.dispatch import receiver
from django_q.signals import (
    post_chain_progress,
    post_execute,
    post_execute_in_worker,
    post_spawn,
    pre_chain_progress,
    pre_enqueue,
    pre_execute,
)

@receiver(pre_enqueue)
def my_pre_enqueue_callback(sender, task, **kwargs):
    print(f"Task {task['name']} will be queued")

@receiver(pre_execute)
def my_pre_execute_callback(sender, func, task, **kwargs):
    print(f"Task {task['name']} will be executed by calling {func}")

@receiver(post_execute)
def my_post_execute_callback(sender, task, **kwargs):
    print(f"Task {task['name']} was executed with result {task['result']}")

@receiver(post_execute_in_worker)
def my_post_execute_in_worker_callback(sender, func, task, exc_info=None, **kwargs):
    if exc_info is not None:
        exc_type, exc, _tb = exc_info
        print(f"Task {task['name']} raised {exc_type.__name__}: {exc}")
    else:
        print(f"Task {task['name']} was executed with result {task['result']}")

@receiver(pre_chain_progress)
def my_pre_chain_progress_callback(sender, task, **kwargs):
    print(f"Chain {task.get('group')} progressing past {task['name']}")

@receiver(post_chain_progress)
def my_post_chain_progress_callback(sender, task, **kwargs):
    print(f"Chain {task.get('group')} progression done for {task['name']}")

@receiver(post_spawn)
def my_post_spawn_callback(sender, proc_name, **kwargs):
    print(f"Process {proc_name} has spawned")
```
