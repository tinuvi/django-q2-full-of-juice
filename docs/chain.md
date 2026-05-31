# Chains

Sometimes you want to run tasks sequentially. For that you can use the [`async_chain`](#async_chain) function:

```python
# async a chain of tasks
from django_q.tasks import async_chain, result_group

# the chain must be in the format
# [(func,(args),{kwargs}),(func,(args),{kwargs}),..]
group_id = async_chain([('math.copysign', (1, -1)),
                          ('math.floor', (1,))])

# get group result
result_group(group_id, count=2)
```

A slightly more convenient way is to use a [`Chain`](#chain) instance:

```python
# Chain async
from django_q.tasks import Chain

# create a chain that uses the cache backend
chain = Chain(cached=True)

# add some tasks
chain.append('math.copysign', 1, -1)
chain.append('math.floor', 1)

# run it
chain.run()

print(chain.result())
```

```python
[-1.0, 1]
```

## Reference

<a id="async_chain"></a>
### async_chain()

```python
async_chain(chain, group=None, cached=Conf.CACHED, sync=Conf.SYNC, broker=None)
```

Async a chain of tasks. See also the [`Chain`](#chain) class.

| Parameter | Type | Description |
|---|---|---|
| `chain` | list | a list of tasks in the format [(func,(args),{kwargs}), (func,(args),{kwargs})] |
| `group` | str | an optional group name. |
| `cached` | bool | run this against the cache backend |
| `sync` | bool | execute this inline instead of asynchronous |
| `broker` | | an optional broker instance |

<a id="chain"></a>
### Chain

```python
Chain(chain=None, group=None, cached=Conf.CACHED, sync=Conf.SYNC, broker=None)
```

A sequential chain of tasks. Acts as a convenient wrapper for [`async_chain`](#async_chain)
You can pass the task chain at construction or you can append individual tasks before running them.

| Parameter | Type | Description |
|---|---|---|
| `chain` | list | a list of task in the format [(func,(args),{kwargs}), (func,(args),{kwargs})] |
| `group` | str | an optional group name. |
| `cached` | bool | run this against the cache backend |
| `sync` | bool | execute this inline instead of asynchronous |
| `broker` | | an optional broker instance |

**Methods**

#### append()

```python
append(func, *args, **kwargs)
```

Append a task to the chain. Takes the same arguments as [`async_task`](tasks.md#async_task)

**Returns:** the current number of tasks in the chain (`int`).

#### run()

```python
run()
```

Start queueing the chain to the worker cluster.

**Returns:** the chains group id

#### result()

```python
result(wait=0)
```

return the full list of results from the chain when it finishes. Blocks until timeout or result.

| Parameter | Type | Description |
|---|---|---|
| `wait` | int | how many milliseconds to wait for a result |

**Returns:** an unsorted list of results

#### fetch()

```python
fetch(failures=True, wait=0)
```

get the task result objects from the chain when it finishes. Blocks until timeout or result.

| Parameter | Type | Description |
|---|---|---|
| `failures` | | include failed tasks |
| `wait` | int | how many milliseconds to wait for a result |

**Returns:** an unsorted list of task objects

#### current()

```python
current()
```

get the index of the currently executing chain element

**Returns:** current chain index (`int`).

#### length()

```python
length()
```

get the length of the chain

**Returns:** length of the chain (`int`).
