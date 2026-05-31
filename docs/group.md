# Groups

You can group together results by passing [`async_task`](tasks.md#async_task) the optional `group` keyword:

```python
# result group example
from django_q.tasks import async_task, result_group

for i in range(4):
    async_task('math.modf', i, group='modf')

# wait until the group has 4 results
result = result_group('modf', count=4)
print(result)
```

```python
[(0.0, 0.0), (0.0, 1.0), (0.0, 2.0), (0.0, 3.0)]
```

Note that this particular example can be achieved much faster with [iterable](iterable.md)

Take care to not limit your results database too much and call [`delete_group`](#delete_group) before each run, unless you want your results to keep adding up.
Instead of [`result_group`](#result_group) you can also use [`fetch_group`](#fetch_group) to return a queryset of `Task` objects.:

```python
# fetch group example
from django_q.tasks import fetch_group, count_group, result_group

# count the number of failures
failure_count = count_group('modf', failures=True)

# only use the successes
results = fetch_group('modf')
if failure_count:
    results = results.exclude(success=False)
results =  [task.result for task in successes]

# this is the same as
results = fetch_group('modf', failures=False)
results =  [task.result for task in successes]

# and the same as
results = result_group('modf') # filters failures by default
```

Getting results by using [`result_group`](#result_group) is of course much faster than using [`fetch_group`](#fetch_group), but it doesn't offer the benefits of Django's queryset functions.

You can also access group functions from a task result instance:

```python
from django_q.tasks import fetch

task = fetch('winter-speaker-alpha-ceiling')
if  task.group_count() > 100:
    print(task.group_result())
    task.group_delete()
    print('Deleted group {}'.format(task.group))
```

or call them directly on `AsyncTask` object:

```python
from django_q.tasks import AsyncTask

# add a task to the math group and run it cached
a = AsyncTask('math.floor', 2.5, group='math', cached=True)

# wait until this tasks group has 10 results
result = a.result_group(count=10)
```

## Reference

<a id="result_group"></a>
### result_group()

```python
result_group(group_id, failures=False, wait=0, count=None, cached=Conf.CACHED)
```

Returns the results of a task group

| Parameter | Type | Description |
|---|---|---|
| `group_id` | str | the group identifier |
| `failures` | bool | set this to `True` to include failed results |
| `wait` | int | optional milliseconds to wait for a result or count. -1 for indefinite |
| `count` | int | block until there are this many results in the group |
| `cached` | bool | run this against the cache backend |

**Returns:** a list of results (`list`).

<a id="fetch_group"></a>
### fetch_group()

```python
fetch_group(group_id, failures=True, wait=0, count=None, cached=Conf.CACHED)
```

Returns a list of tasks in a group

| Parameter | Type | Description |
|---|---|---|
| `group_id` | str | the group identifier |
| `failures` | bool | set this to `False` to exclude failed tasks |
| `wait` | int | optional milliseconds to wait for a task or count. -1 for indefinite |
| `count` | int | block until there are this many tasks in the group |
| `cached` | bool | run this against the cache backend. |

**Returns:** a list of `Task` (`list`).

<a id="count_group"></a>
### count_group()

```python
count_group(group_id, failures=False, cached=Conf.CACHED)
```

Counts the number of task results in a group.

| Parameter | Type | Description |
|---|---|---|
| `group_id` | str | the group identifier |
| `failures` | bool | counts the number of failures if `True` |
| `cached` | bool | run this against the cache backend. |

**Returns:** the number of tasks or failures in a group (`int`).

<a id="delete_group"></a>
### delete_group()

```python
delete_group(group_id, tasks=False, cached=Conf.CACHED)
```

Deletes a group label from the database.

| Parameter | Type | Description |
|---|---|---|
| `group_id` | str | the group identifier |
| `tasks` | bool | also deletes the associated tasks if `True` |
| `cached` | bool | run this against the cache backend. |

**Returns:** the numbers of tasks affected (`int`).
