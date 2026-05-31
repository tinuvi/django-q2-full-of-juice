# Monitor

!!! warning
    Blessed needs to be installed to get this to work! See: https://pypi.org/project/blessed/

The cluster monitor shows live information about all the Q clusters connected to your project.

Start the monitor with Django's `manage.py` command:

```bash
python manage.py qmonitor
```

Pass `--run-once` to render a single snapshot and exit instead of refreshing continuously.

![](assets/monitor.png)

For all broker types except the Redis broker, the monitor utilizes Django's cache framework to store statistics of running clusters.
This can be any type of cache backend as long as it can be shared among Django instances. For this reason, the local memory backend will not work.

## Legend

### Host

Shows the hostname of the server this cluster is running on.

### Id

The cluster Id. Same as the cluster process ID or pid.

### State

Current state of the cluster:

- **Starting** The cluster is spawning workers and getting ready.
- **Idle** Everything is ok, but there are no tasks to process.
- **Working** Processing tasks like a good cluster should.
- **Stopping** The cluster does not take on any new tasks and is finishing.
- **Stopped** All tasks have been processed and the cluster is shutting down.

### Pool

The current number of workers in the cluster pool.

### TQ

**Task Queue** counts the number of tasks in the queue [^f1]

If this keeps rising it means you are taking on more tasks than your cluster can handle.
You can limit this by settings the [queue_limit](configure.md#queue_limit) in your cluster configuration, after which it will turn green when that limit has been reached.
If your task queue is always hitting its limit and your running out of resources, it may be time to add another cluster.

### RQ

**Result Queue** shows the number of results in the queue. [^f1]

Since results are only saved by a single process which has to access the database.
It's normal for the result queue to take slightly longer to clear than the task queue.

### RC

**Reincarnations** shows the amount of processes that have been reincarnated after a recycle, sudden death or timeout.
If this number is unusually high, you are either suffering from repeated task errors or severe timeouts and you should check your logs for details.

### Up

**Uptime** the amount of time that has passed since the cluster was started.

Press `q` to quit the monitor and return to your terminal.

## Info

If you just want to see a one-off summary of your cluster stats you can use the `qinfo` management command:

```bash
python manage.py qinfo
```

![](assets/info.png)

All stats are summed over all available clusters.

Task rate is calculated over the last 24 hours and will show the number of tasks per second, minute, hour or day depending on the amount.
Average execution time (`Avg time`) is calculated in seconds over the last 24 hours.

Since some of these numbers are based on what is available in your tasks database, limiting or disabling the result backend will skew them.

Like with the monitor, these statistics come from a Redis server or Django's cache framework. So make sure you have either one configured.

To print out the current configuration run:

```bash
python manage.py qinfo --config
```

To list the process IDs (PIDs) of the running clusters run:

```bash
python manage.py qinfo --ids
```

## Memory

To keep an eye on the memory footprint of your clusters, use the `qmemory` management command:

```bash
python manage.py qmemory
```

It shows the resident set size (RSS) of each cluster. Add `--workers` to break the usage down per worker process, and `--run-once` to print a single snapshot and exit instead of refreshing continuously:

```bash
python manage.py qmemory --workers --run-once
```

Combined with the `max_rss` setting (see [configure](configure.md)), this helps you spot and cap leaky tasks.

## Status

You can check the status of your clusters straight from your code with the `Stat` class:

```python
from django_q.status import Stat

for stat in Stat.get_all():
    print(stat.cluster_id, stat.status)

# or if you know the cluster id
cluster_id = 1234
stat = Stat.get(cluster_id)
print(stat.status, stat.workers)
```

## Reference

### Stat

Cluster status object.

**Attributes**

| Attribute | Description |
|---|---|
| `cluster_id` | Id of this cluster. Corresponds with the process id. |
| `tob` | Time Of Birth |
| `reincarnations` | The number of times the sentinel had to start a new worker process. |
| `status` | String representing the current cluster status. |
| `task_q_size` | The number of tasks currently in the task queue. [^f1] |
| `done_q_size` | The number of tasks currently in the result queue. [^f1] |
| `pusher` | The pid of the pusher process |
| `monitor` | The pid of the monitor process |
| `sentinel` | The pid of the sentinel process |
| `workers` | A list of process ids of the workers currently in the cluster pool. |

**Methods**

| Method | Description |
|---|---|
| `uptime` | Shows the number of seconds passed since the time of birth |
| `empty_queues` | Returns true or false depending on any tasks still present in the task or result queue. |

**Class methods**

| Method | Description |
|---|---|
| `get(cluster_id, broker=None)` | Gets the current `Stat` for the cluster id. Takes an optional broker connection. |
| `get_all(broker=None)` | Returns a list of `Stat` objects for all active clusters. Takes an optional broker connection. |

[^f1]: Uses `multiprocessing.Queue.qsize()` which is not implemented on OS X and always returns 0.
