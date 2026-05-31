# Iterable

If you have an iterable object with arguments for a function, you can use [`async_iter`](#async_iter) to async them with a single command:

```python
# Async Iterable example
from django_q.tasks import async_iter, result

# set up a list of arguments for math.floor
iter = [i for i in range(100)]

# async_task iter them
id=async_iter('math.floor',iter)

# wait for the collated result for 1 second
result_list = result(id, wait=1000)
```

This will individually queue 100 tasks to the worker cluster, which will save their results in the cache backend for speed.
Once all the 100 results are in the cache, they are collated into a list and saved as a single result in the database. The cache results are then cleared.

You can also use an [`Iter`](#iter) instance which can sometimes be more convenient:

```python
from django_q.tasks import Iter

i = Iter('math.copysign')

# add some arguments
i.append(1, -1)
i.append(2, -1)
i.append(3, -1)

# run it
i.run()

# get the results
print(i.result())
```

```python
[-1.0, -2.0, -3.0]
```

## Reference

<a id="async_iter"></a>
### async_iter()

```python
async_iter(func, args_iter, **kwargs)
```

Runs iterable arguments against the cache backend and returns a single collated result.
Accepts the same options as [`async_task`](tasks.md#async_task) except `hook`. Note that results are always routed through the cache backend (`cached` is forced on) so they can be collated. See also the [`Iter`](#iter) class.

| Parameter | Type | Description |
|---|---|---|
| `func` | object | The task function to execute |
| `args` | | An iterable containing arguments for the task function |
| `kwargs` | dict | Keyword arguments for the task function. Ignores `hook`. |

**Returns:** The uuid of the task (`str`).

<a id="iter"></a>
### Iter

```python
Iter(func=None, args=None, kwargs=None, cached=Conf.CACHED, sync=Conf.SYNC, broker=None)
```

An async task with iterable arguments. Serves as a convenient wrapper for [`async_iter`](#async_iter)
You can pass the iterable arguments at construction or you can append individual argument tuples.

| Parameter | Type | Description |
|---|---|---|
| `func` | | the function to execute |
| `args` | | an iterable of arguments. |
| `kwargs` | | the keyword arguments |
| `cached` | bool | run this against the cache backend |
| `sync` | bool | execute this inline instead of asynchronous |
| `broker` | | optional broker instance |

**Methods**

#### append()

```python
append(*args)
```

Append arguments to the iter set. Returns the current set count.

| Parameter | Type | Description |
|---|---|---|
| `args` | | the arguments for a single execution |

**Returns:** the current set count (`int`).

#### run()

```python
run()
```

Start queueing the tasks to the worker cluster.

**Returns:** the task result id

#### result()

```python
result(wait=0)
```

return the full list of results.

| Parameter | Type | Description |
|---|---|---|
| `wait` | int | how many milliseconds to wait for a result |

**Returns:** an unsorted list of results

#### fetch()

```python
fetch(wait=0)
```

get the task result objects.

| Parameter | Type | Description |
|---|---|---|
| `wait` | int | how many milliseconds to wait for a result |

**Returns:** an unsorted list of task objects

#### length()

```python
length()
```

get the length of the arguments list

**Returns:** length of the argument list (`int`).
