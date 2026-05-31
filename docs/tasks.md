# Creating Tasks

## async_task()

Use `async_task()` from your code to quickly offload tasks to the [Cluster](cluster.md):

```python
from django_q.tasks import async_task, result

# create the task
async_task('math.copysign', 2, -2)

# or with import and storing the id
import math.copysign

task_id = async_task(copysign, 2, -2)

# get the result
task_result = result(task_id)

# result returns None if the task has not been executed yet
# you can wait for it
task_result = result(task_id, 200)

# but in most cases you will want to use a hook:

async_task('math.modf', 2.5, hook='hooks.print_result')

# hooks.py
def print_result(task):
    print(task.result)
```

`async_task()` can take the following optional keyword arguments:

| Option | Description |
|---|---|
| `hook` | The function to call after the task has been executed. This function gets passed the complete [Task](#task) object as its argument. |
| `group` | A group label. Check [Groups](group.md) for group functions. |
| `save` | Overrides the result backend's save setting for this task. |
| `timeout` | Overrides the cluster's timeout setting for this task. See [retry](configure.md#retry) for details on how to set timeout values. |
| `ack_failure` | Overrides the cluster's [ack_failures](configure.md#ack_failures) setting for this task. |
| `sync` | Simulates a task execution synchronously. Useful for testing. Can also be forced globally via the [sync](configure.md#sync) configuration option. |
| `cached` | Redirects the result to the cache backend instead of the database if set to `True` or to an integer indicating the cache timeout in seconds, e.g. `cached=60`. Especially useful with large and group operations. |
| `broker` | A broker instance, in case you want to control your own connections. |
| `cluster` | The name of the cluster. Only useful if you are using [alternative queues](cluster.md#multiple-queues). |
| `task_name` | Optionally overwrites the auto-generated task name. |

### q_options

None of the option keywords get passed on to the task function. As an alternative you can also put them in a single keyword dict named `q_options`. This enables you to use these keywords for your function call:

```python
# Async options in a dict
opts = {'hook': 'hooks.print_result',
        'group': 'math',
        'timeout': 30}

async_task('math.modf', 2.5, q_options=opts)
```

Please note that this will override any other option keywords.

!!! note
    For tasks to be processed you will need to have a worker cluster running in the background using `python manage.py qcluster`, or you need to configure Django Q2 to run in synchronous mode for testing using the [sync](configure.md#sync) option.

## AsyncTask

Optionally you can use the `AsyncTask` class to instantiate a task and keep everything in a single object:

```python
# AsyncTask class instance example
from django_q.tasks import AsyncTask

# instantiate an async task
a = AsyncTask('math.floor', 1.5, group='math')

# you can set or change keywords afterwards
a.cached = True

# run it
a.run()

# wait indefinitely for the result and print it
# don't let the task return `None` or it will wait indefinitely
print(a.result(wait=-1))

# change the args
a.args = (2.5,)

# run it again
a.run()

# wait max 10 seconds for the result and print it
print(a.result(wait=10))
```

Once you change any of the parameters of the task after it has run, the result is invalidated and you will have to `run()` it again to retrieve a new result.

## Cached operations

You can run your task results against the Django cache backend instead of the database backend by either using the global [cached](configure.md#cached) setting or by supplying the `cached` keyword to individual functions.
This can be useful if you are not interested in persistent results or if you run large group tasks where you only want the final result.
By using a cache backend like Redis or Memcached you can speed up access to your task results significantly compared to a relational database.

When you set `cached=True`, results will be saved permanently in the cache and you will have to rely on your backend's cleanup strategies (like LRU) to manage stale results.
You can also opt to set a manual timeout on the results, by setting e.g. `cached=60`, meaning the result will be evicted from the cache after 60 seconds.
This works both globally or on individual async executions.

```python
# simple cached example
from django_q.tasks import async_task, result

# cache the result for 10 seconds
id = async_task('math.floor', 100, cached=10)

# wait max 50ms for the result to appear in the cache
result(id, wait=50, cached=True)

# or fetch the task object
task = fetch(id, cached=True)

# and then save it to the database
task.save()
```

As you can see you can easily turn a cached result into a permanent database result by calling `save()` on it.

This also works for group actions:

```python
# cached group example
from django_q.tasks import async_task, result_group
from django_q.brokers import get_broker

# set up a broker instance for better performance
broker = get_broker()

# Async a hundred functions under a group label
for i in range(100):
    async_task('math.frexp',
               i,
               group='frexp',
               cached=True,
               broker=broker)

# wait max 50ms for one hundred results to return
result_group('frexp', wait=50, count=100, cached=True)
```

If you don't need hooks, that exact same result can be achieved by using the more convenient [`async_iter()`](iterable.md).

## Synchronous testing

`async_task()` can be instructed to execute a task immediately by setting the optional keyword `sync=True`.
The task will then be injected straight into a worker and the result saved by a monitor instance:

```python
from django_q.tasks import async_task, fetch

# create a synchronous task
task_id = async_task('my.buggy.code', sync=True)

# the task will then be available immediately
task = fetch(task_id)

# and can be examined
if not task.success:
    print('An error occurred: {}'.format(task.result))
```

```bash
An error occurred: ImportError("No module named 'my'",)
```

Note that `async_task()` will block until the task is executed and saved. This feature bypasses the broker and is intended for debugging and development.
Instead of setting `sync` on each individual `async_task()` you can also configure [sync](configure.md#sync) as a global override.

## Connection pooling

Django Q2 tries to pass broker instances around its parts as much as possible to save you from running out of connections.
When you are making individual calls to `async_task()` a lot though, it can help to set up a broker to reuse:

```python
# broker connection economy example
from django_q.tasks import async_task
from django_q.brokers import get_broker

broker = get_broker()
for i in range(50):
    async_task('math.modf', 2.5, broker=broker)
```

If you are using [django-redis](https://github.com/niwinz/django-redis) and the Redis broker, you can [configure](configure.md#django_redis) Django Q2 to use its connection pool.

## Reference

### async_task()

```python
async_task(func, *args, hook=None, group=None, timeout=None, save=None,
           ack_failure=None, sync=False, cached=False, broker=None,
           cluster=None, task_name=None, q_options=None, **kwargs)
```

Puts a task in the cluster queue.

| Parameter | Type | Description |
|---|---|---|
| `func` | object | The task function to execute. |
| `*args` | tuple | The arguments for the task function. |
| `hook` | object | Optional function to call after execution. |
| `group` | str | An optional group identifier. |
| `timeout` | int | Overrides the global cluster [timeout](configure.md#timeout). |
| `save` | bool | Overrides the global save setting for this task. |
| `ack_failure` | bool | Overrides the global [ack_failures](configure.md#ack_failures) setting for this task. |
| `sync` | bool | If `True`, `async_task` will simulate a task execution. |
| `cached` | bool / int | Output the result to the cache backend. Bool or timeout in seconds. Defaults to the global [cached](configure.md#cached) setting. |
| `broker` | object | Optional broker connection from `brokers.get_broker()`. |
| `cluster` | str | Optional cluster name if using alternative queues. |
| `task_name` | str | Optional custom name for the task instead of the generated humanized name. |
| `q_options` | dict | Options dict, overrides option keywords. |
| `**kwargs` | dict | Keyword arguments for the task function. |

**Returns:** the uuid of the task (`str`).

### result()

```python
result(task_id, wait=0, cached=Conf.CACHED)
```

Gets the result of a previously executed task.

| Parameter | Type | Description |
|---|---|---|
| `task_id` | str | The uuid or name of the task. |
| `wait` | int | Optional milliseconds to wait for a result. `-1` for indefinite, but be sure the result will not be `None`, otherwise it will wait indefinitely! |
| `cached` | bool | Run this against the cache backend. Defaults to the global [cached](configure.md#cached) setting. |

**Returns:** the result of the executed task.

### fetch()

```python
fetch(task_id, wait=0, cached=Conf.CACHED)
```

Returns a previously executed task.

| Parameter | Type | Description |
|---|---|---|
| `task_id` | str | The uuid or name of the task. |
| `wait` | int | Optional milliseconds to wait for a result. `-1` for indefinite. |
| `cached` | bool | Run this against the cache backend. Defaults to the global [cached](configure.md#cached) setting. |

**Returns:** a [Task](#task) object.

### queue_size()

```python
queue_size()
```

Returns the size of the broker queue. Note that this does not count tasks currently being processed.

**Returns:** the amount of task packages in the broker (`int`).

### delete_cached()

```python
delete_cached(task_id, broker=None)
```

Deletes a task from the cache backend.

| Parameter | Type | Description |
|---|---|---|
| `task_id` | str | The uuid of the task. |
| `broker` | object | An optional broker instance. |

### Task

Database model describing an executed task.

| Attribute | Description |
|---|---|
| `id` | A `uuid.uuid4()` identifier. |
| `name` | The name of the task as a humanized version of the `id`. Can be used as a `task_id` in most functions, but is not guaranteed unique for very large amounts of stored tasks. |
| `func` | The function or reference that was executed. |
| `hook` | The function to call after execution. |
| `args` | Positional arguments for the function. |
| `kwargs` | Keyword arguments for the function. |
| `result` | The result object. Contains the error if any occurred. |
| `started` | The moment the task was created by an async command. |
| `stopped` | The moment a worker finished this task. |
| `success` | Was the task executed without problems? |
| `cluster` | The name of the cluster that executed this task. |
| `attempt_count` | The number of times this task has been attempted. Incremented by the monitor on each (re)delivery; see [max_attempts](configure.md#max_attempts). |

**Methods**

| Method | Description |
|---|---|
| `time_taken()` | Calculates the difference in seconds between `started` and `stopped`. Includes any time the task waited in the queue. |
| `group_result(failures=False)` | Returns a list of results from this task's group. Set `failures=True` to include failed results. |
| `group_count(failures=False)` | Returns a count of the task results in this task's group. Returns failures when `failures=True`. |
| `group_delete(tasks=False)` | Resets the group label on all tasks in this task's group. With `tasks=True` also deletes the tasks from the database. |

**Class methods**

| Method | Description |
|---|---|
| `get_result(task_id)` | Gets a result directly by task uuid or name. |
| `get_result_group(group_id, failures=False)` | Returns a list of results from a task group. |
| `get_task(task_id)` | Fetches a single task object by uuid or name. |
| `get_task_group(group_id, failures=True)` | Gets a queryset of tasks with this group id. |
| `get_group_count(group_id, failures=False)` | Returns a count of the task results in a group. |
| `delete_group(group_id, objects=False)` | Deletes a group label only, by default. With `objects=True` also deletes the tasks from the database. |

### Success

A proxy model of [Task](#task) with the queryset filtered on `Task.success` is `True`.

### Failure

A proxy model of [Task](#task) with the queryset filtered on `Task.success` is `False`.

### AsyncTask

```python
AsyncTask(func, *args, **kwargs)
```

A class wrapper for the `async_task()` function.

| Parameter | Type | Description |
|---|---|---|
| `func` | object | The task function to execute. |
| `*args` | tuple | The arguments for the task function. |
| `**kwargs` | dict | Keyword arguments for the task function, including `async_task` options. |

Provides `run()`, `result()` and `fetch()` methods mirroring the module-level functions, plus `result_group()` and `fetch_group()` when a `group` is set.
