# Schedules

## Schedule

Schedules are regular Django models.
You can manage them through the [admin page](admin.md#admin_page) or directly from your code with the [`schedule`](#schedule) function or the [`Schedule`](#schedule-model) model:

```python
# Use the schedule wrapper
from django_q.tasks import schedule

schedule('math.copysign',
         2, -2,
         hook='hooks.print_result',
         schedule_type='D')

# Or create the object directly
from django_q.models import Schedule

Schedule.objects.create(func='math.copysign',
                        hook='hooks.print_result',
                        args='2,-2',
                        schedule_type=Schedule.DAILY
                        )

# In case you want to use q_options
# Specify the broker by using the property broker_name in q_options
schedule('math.sqrt',
         9,
         hook='hooks.print_result',
         q_options={'timeout': 30, 'broker_name': 'broker_1'},
         schedule_type=Schedule.HOURLY)

# Run a schedule every 5 minutes, starting at 6 today
# for 2 hours
from datetime import datetime

schedule('math.hypot',
         3, 4,
         schedule_type=Schedule.MINUTES,
         minutes=5,
         repeats=24,
         next_run=datetime.utcnow().replace(hour=18, minute=0))

# Use a cron expression
schedule('math.hypot',
         3, 4,
         schedule_type=Schedule.CRON,
         cron = '0 22 * * 1-5')


# Restrain a schedule to a specific cluster
schedule('math.hypot',
         3, 4,
         schedule_type=Schedule.DAILY,
         cluster='my_cluster')
```

## Missed schedules

If your cluster has not run for a while, the default behavior for the scheduler is to play catch up with the schedules and keep executing them until they are up to date.
In practical terms this means the scheduler will execute tasks in the past, reschedule them in the past and immediately execute them again until the schedule is set in the future.
This default behavior is intended to facilitate schedules that poll or gather statistics, but might not be suitable to your particular situation.
You can change this by setting the [catch_up](configure.md#catch_up) configuration setting to `False`.
The scheduler will then skip execution of scheduled events in the past.
Instead those tasks will run once when the cluster starts again and the scheduler will find the next available slot in the future according to original schedule parameters.

When [catch_up](configure.md#catch_up) is to `True` it may be useful for the task to know what was the date and time it was originally intended to run at.
To achieve this, pass an identifier name to parameter `intended_date_kwarg` when creating the schedule. The intended datetime will then be passed - in isoformat string - as
a kwarg with that identifier name to the task that has been created.

## Management Commands

If you want to schedule regular Django management commands, you can use the `django.core.management` module to call them directly:

```python
from django_q.tasks import schedule

# run `manage.py clearsession` every hour
schedule('django.core.management.call_command',
         'clearsessions',
         schedule_type='H')
```

Or you can make a wrapper function which you can then schedule in Django Q:

```python
# tasks.py
from django.core import management

# wrapping `manage.py clearsessions`
def clear_sessions_command():
    return management.call_command('clearsessions')

# now you can schedule it to run every hour
from django_q.tasks import schedule

schedule('tasks.clear_sessions_command', schedule_type='H')
```

Check out the [shell](examples.md#shell) examples if you want to schedule regular shell commands

!!! note
    Schedules needs the optional [Croniter](install.md#croniter_package) package installed to parse cron expressions.

## Reference

<a id="schedule"></a>
### schedule()

```python
schedule(func, *args, name=None, hook=None, schedule_type='O', minutes=None,
         cron=None, repeats=-1, next_run=now(), cluster=None,
         intended_date_kwarg=None, q_options=None, **kwargs)
```

Creates a schedule

| Parameter | Type | Description |
|---|---|---|
| `func` | str | the function to schedule. Dotted strings only. |
| `args` | | arguments for the scheduled function. |
| `name` | str | An optional name for your schedule. |
| `hook` | str | optional result hook function. Dotted strings only. |
| `schedule_type` | str | (O)nce, M(I)nutes, (H)ourly, (D)aily, (W)eekly, (BW) Biweekly, (M)onthly, (BM) Bimonthly, (Q)uarterly, (Y)early or (C)ron [`Schedule.TYPE`](#schedule-type) |
| `minutes` | int | Number of minutes for the Minutes type. |
| `cron` | str | Cron expression for the Cron type. |
| `repeats` | int | Number of times to repeat schedule. -1=Always, 0=Never, n =n. |
| `next_run` | datetime | Next or first scheduled execution datetime. |
| `cluster` | str | optional cluster name. Task will be executed only on a cluster with a matching [name](configure.md#name). |
| `intended_date_kwarg` | str | optional identifier to pass intended schedule date. |
| `q_options` | dict | options passed to async_task for this schedule |
| `kwargs` | | optional keyword arguments for the scheduled function. |

!!! note
    q_options does not accept the 'broker' key with a broker instance but accepts a 'broker_name' key instead. This can be used to specify the broker connection name to assign the task. If a broker with the specified name does not exist or is not running at the moment of placing the task in queue it fallbacks to the random broker/queue that handled the schedule.

<a id="schedule-model"></a>
### Schedule

A database model for task schedules.

**Attributes**

| Attribute | Description |
|---|---|
| `id` | Primary key |
| `name` | A name for your schedule. Tasks created by this schedule will assume this or the primary key as their group id. |
| `func` | The function to be scheduled |
| `hook` | Optional hook function to be called after execution. |
| `args` | Positional arguments for the function. |
| `kwargs` | Keyword arguments for the function |
| `schedule_type` | The type of schedule. Follows [`Schedule.TYPE`](#schedule-type) |
| <a id="schedule-type"></a>`TYPE` | [`ONCE`](#schedule-once), [`MINUTES`](#schedule-minutes), [`HOURLY`](#schedule-hourly), [`DAILY`](#schedule-daily), [`WEEKLY`](#schedule-weekly), [`BIWEEKLY`](#schedule-biweekly), [`MONTHLY`](#schedule-monthly), [`BIMONTHLY`](#schedule-bimonthly), [`QUARTERLY`](#schedule-quarterly), [`YEARLY`](#schedule-yearly), [`CRON`](#schedule-cron) |
| `minutes` | The number of minutes the [`MINUTES`](#schedule-minutes) schedule should use. Is ignored for other schedule types. |
| `cron` | A cron string describing the schedule. You need the optional `croniter` package installed for this. |
| `repeats` | Number of times to repeat the schedule. -1=Always, 0=Never, n =n. When set to -1, this will keep counting down. |
| `cluster` | Task will be executed only on a cluster with a matching [name](configure.md#name). |
| `intended_date_kwarg` | Name of kwarg to pass intended schedule date. |
| `next_run` | Datetime of the next scheduled execution. |
| `task` | Id of the last task generated by this schedule. |

**Methods**

| Method | Description |
|---|---|
| `last_run()` | Admin link to the last executed task. |
| `success()` | Returns the success status of the last executed task. |

**Schedule type constants**

| Constant | Description |
|---|---|
| <a id="schedule-once"></a>`ONCE` | `'O'` the schedule will only run once. If it has a negative `repeats` it will be deleted after it has run. If you want to keep the result, set `repeats` to a positive number. |
| <a id="schedule-minutes"></a>`MINUTES` | `'I'` will run every `minutes` after its first run. |
| <a id="schedule-hourly"></a>`HOURLY` | `'H'` the scheduled task will run every hour after its first run. |
| <a id="schedule-daily"></a>`DAILY` | `'D'` the scheduled task will run every day at the time of its first run. |
| <a id="schedule-weekly"></a>`WEEKLY` | `'W'` the task will run every week on they day and time of the first run. |
| <a id="schedule-biweekly"></a>`BIWEEKLY` | `'BW'` the task will run once every two weeks on they day and time of the first run. |
| <a id="schedule-monthly"></a>`MONTHLY` | `'M'` the tasks runs every month on they day and time of the last run. |
| <a id="schedule-bimonthly"></a>`BIMONTHLY` | `'BM'` the tasks runs once every two months on they day and time of the last run. |
| <a id="schedule-quarterly"></a>`QUARTERLY` | `'Q'` this task runs once every 3 months on the day and time of the last run. |
| <a id="schedule-yearly"></a>`YEARLY` | `'Y'` only runs once a year. The same caution as with months apply; If you set this to february 29th, it will run on february 28th in the following years. |
| <a id="schedule-cron"></a>`CRON` | `'C'` uses the optional `croniter` package to determine a schedule based on a cron expression. |

!!! note
    Months are tricky. If you schedule something on the 31st of the month and the next month has only 30 days or less, the task will run on the last day of the next month.
    It will however continue to run on that day, e.g. the 28th, in subsequent months.

!!! note
    Months are tricky. If you schedule something on the 31st of the month and the next month has only 30 days or less, the task will run on the last day of the next month.
    It will however continue to run on that day, e.g. the 28th, in subsequent months.
