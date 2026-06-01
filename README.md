# A multiprocessing distributed task queue for Django

[![PyPI version](https://img.shields.io/pypi/v/django-q2-full-of-juice.svg)](https://pypi.org/project/django-q2-full-of-juice/) [![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=tinuvi_django-q2-full-of-juice&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=tinuvi_django-q2-full-of-juice) [![Coverage](https://sonarcloud.io/api/project_badges/measure?project=tinuvi_django-q2-full-of-juice&metric=coverage)](https://sonarcloud.io/summary/new_code?id=tinuvi_django-q2-full-of-juice)

Django Q2 is a fork of Django Q. Big thanks to Ilan Steemers for starting this project. Unfortunately, development has stalled since June 2021. Django Q2 is the new updated version of Django Q, with dependencies updates, docs updates and several bug fixes. Original repository: https://github.com/Koed00/django-q

## Capabilities

Everything the library provides, at a glance. **How you get it** points at the API call or `Q_CLUSTER` setting that activates each capability.

**Legend:** ✅ supported · ⚙️ built-in / on by default · ⚠️ supported, with a caveat · 🧩 optional (extra setting or dependency)

### Dispatch & execution

| Capability | Status | How you get it |
|---|---|---|
| Fire-and-forget async tasks (callable or `"module.func"` path) | ✅ | `async_task("app.tasks.fn", *args, **kwargs)` |
| Synchronous/inline run for tests & debugging | ⚙️ | `async_task(..., sync=True)` or `Q_CLUSTER={"sync": True}` |
| Per-task & global timeouts | ✅ | `async_task(..., timeout=30)` / `Q_CLUSTER={"timeout": 60}` |
| Multiprocessing worker pool | ⚙️ | `python manage.py qcluster` (workers default to CPU count) |
| Worker recycling & memory cap (RSS) | ✅ | `Q_CLUSTER={"recycle": 500, "max_rss": 100000}` |
| CPU-affinity pinning | 🧩 | `Q_CLUSTER={"cpu_affinity": 1}` (needs `psutil`) |

### Results & state

| Capability | Status | How you get it |
|---|---|---|
| Result retrieval / blocking wait | ✅ | `result(id, wait=2000)` / `fetch(id)` |
| Result hooks (post-run callback) | ✅ | `async_task(..., hook="app.hooks.cb")` |
| Success/Failure persisted to the database | ⚙️ | `Task` / `Success` / `Failure` models in the Admin |
| Cache result backend (skip the database) | 🧩 | `cached=True` / `Q_CLUSTER={"cached": 60}` |
| Save-limit trimming (per group/name/func) | ✅ | `Q_CLUSTER={"save_limit": 250, "save_limit_per": "func"}` |

### Composition

| Capability | Status | How you get it |
|---|---|---|
| Task groups + group results/counts | ✅ | `async_task(..., group="g")` then `result_group("g")` |
| Sequential chains | ✅ | `Chain().append(...).run()` / `async_chain([...])` |
| Iterable fan-out | ✅ | `Iter()` / `async_iter(fn, [args, ...])` |

### Scheduling

| Capability | Status | How you get it |
|---|---|---|
| Scheduled & repeating tasks (minutes → yearly) | ✅ | `schedule(..., schedule_type=Schedule.DAILY, repeats=-1)` |
| Cron expressions | 🧩 | `schedule_type=Schedule.CRON, cron="0 22 * * 1-5"` (needs `croniter`) |
| `ONCE` auto-cleanup & repeat countdown | ⚙️ | automatic once `repeats` reaches 0 |
| Catch-up vs. skip missed runs | ⚙️ | `Q_CLUSTER={"catch_up": False}` |
| Manage schedules via Admin or ORM | ✅ | `Schedule` is a regular Django model |

### Reliability & security

| Capability | Status | How you get it |
|---|---|---|
| Retry of un-acked tasks | ⚠️ | `Q_CLUSTER={"retry": 90, "timeout": 60}` — `retry` must exceed `timeout` |
| Max attempts + attempt tracking | ✅ | `Q_CLUSTER={"max_attempts": 3}`; observers read `task["attempt"]` |
| Acknowledge failures (drop from the queue) | ✅ | `ack_failure=True` / `Q_CLUSTER={"ack_failures": True}` |
| Signed (HMAC) task packages | ⚙️ | automatic, uses Django's `SECRET_KEY` |
| Compressed payloads | 🧩 | `Q_CLUSTER={"compress": True}` |

### Brokers

| Capability | Status | How you get it |
|---|---|---|
| Redis · IronMQ · Amazon SQS · MongoDB · Django ORM | ✅ | `Q_CLUSTER={"redis": {...}}` (or `orm` / `sqs` / `mongo` / `iron_mq`) |
| Custom broker class | ✅ | `Q_CLUSTER={"broker_class": "path.to.Broker"}` |
| Multiple clusters / queues on one backend | ✅ | `async_task(..., cluster="x")` / `ALT_CLUSTERS` |

### Operations & observability

| Capability | Status | How you get it |
|---|---|---|
| Management CLI: `qcluster` / `qmonitor` / `qmemory` / `qinfo` | ✅ | `python manage.py qmonitor` |
| Django Admin integration | ⚙️ | tasks & schedules visible in the Admin |
| Pluggable error reporters (Sentry / Rollbar) | 🧩 | `Q_CLUSTER={"error_reporter": {...}}` + reporter plugin |
| Lifecycle signals (`post_spawn`, `pre_enqueue`, `pre_execute`, `post_execute`, `post_execute_in_worker`) | ✅ | connect Django signals from `django_q.signals` |
| Chain-progress signals (`pre_chain_progress` / `post_chain_progress`) | ✅ | carry cross-process context (e.g. OpenTelemetry) across chain links |
| OpenTelemetry-style instrumentation | 🧩 | built on the signals above — see [`opentelemetry-instrumentation-django-q2-full-of-juice`](https://github.com/tinuvi/opentelemetry-instrumentation-django-q2-full-of-juice) |
| Localized UI (English / German / Turkish / French) | ✅ | automatic via Django i18n |

## OpenTelemetry

Need distributed tracing that survives the queue boundary? The companion package [`opentelemetry-instrumentation-django-q2-full-of-juice`](https://github.com/tinuvi/opentelemetry-instrumentation-django-q2-full-of-juice) turns the lifecycle signals this fork ships into real OpenTelemetry spans. An `HTTP request → task A → task B → task C` graph then shows up as **one continuous distributed trace**.

It propagates trace context (and W3C Baggage) producer → broker → worker — the carrier rides inside the signed task payload — and emits producer/consumer spans, duration histograms, and messaging semantic-convention attributes. The chain-progress signals (`pre_chain_progress` / `post_chain_progress`) are unique to this fork: they let every link of an `async_chain` land on the same trace.

Install it alongside django-q2:

```bash
pip install opentelemetry-instrumentation-django-q2-full-of-juice
```

Turn it on once, before any worker forks (your `AppConfig.ready()` is the canonical spot):

```python
from opentelemetry_instrumentation_django_q2 import DjangoQ2Instrumentor

DjangoQ2Instrumentor().instrument()
```

Or activate it with zero code via the OpenTelemetry bootstrap CLI:

```bash
opentelemetry-instrument python manage.py qcluster
```

See the [package documentation](https://github.com/tinuvi/opentelemetry-instrumentation-django-q2-full-of-juice) for the full capability matrix, bring-your-own-provider setup, and caveats.

## Changes compared to the original Django-Q

- Dropped support for Disque (hasn't been updated in a long time)
- Dropped Redis, Arrow and Blessed dependencies
- Updated all current dependencies
- Added tests for Django 4.x and 5.x
- Added Turkish language
- Improved admin area
- Fixed a lot of issues

See the [changelog](https://github.com/tinuvi/django-q2-full-of-juice/blob/master/CHANGELOG.md) for all changes.

## Requirements

- [Django](https://www.djangoproject.com) >= 5.0
- [Django-picklefield](https://github.com/gintas/django-picklefield)

Tested with:

- Python 3.12 to 3.13.
- Django 5.0 to 6.0.

## Brokers

- [Redis](https://tinuvi.github.io/django-q2-full-of-juice/brokers/#redis)
- [IronMQ](https://tinuvi.github.io/django-q2-full-of-juice/brokers/#ironmq)
- [Amazon SQS](https://tinuvi.github.io/django-q2-full-of-juice/brokers/#amazon-sqs)
- [MongoDB](https://tinuvi.github.io/django-q2-full-of-juice/brokers/#mongodb)
- [Django ORM](https://tinuvi.github.io/django-q2-full-of-juice/brokers/#django-orm)

## Installation

- Install the latest version with pip:

  ```bash
  pip install django-q2-full-of-juice
  ```

- Add `django_q` to your `INSTALLED_APPS` in your project's `settings.py`:

  ```python
  INSTALLED_APPS = (
      # other apps
      'django_q',
  )
  ```

- Run Django migrations to create the database tables:

  ```bash
  python manage.py migrate
  ```

- Choose a message [broker](https://tinuvi.github.io/django-q2-full-of-juice/brokers/), configure and install the appropriate client library.

Read the full documentation at [https://tinuvi.github.io/django-q2-full-of-juice/](https://tinuvi.github.io/django-q2-full-of-juice/)

## Configuration

All configuration settings are optional. e.g:

```python
# settings.py example
Q_CLUSTER = {
    'name': 'myproject',
    'workers': 8,
    'recycle': 500,
    'timeout': 60,
    'compress': True,
    'cpu_affinity': 1,
    'save_limit': 250,
    'queue_limit': 500,
    'label': 'Django Q',
    'redis': {
        'host': '127.0.0.1',
        'port': 6379,
        'db': 0,
    }
}
```

For full configuration options, see the [configuration documentation](https://tinuvi.github.io/django-q2-full-of-juice/configure/).

## Management Commands

For the management commands to work, you will need to install Blessed: https://github.com/jquast/blessed

Start a cluster with:

```bash
python manage.py qcluster
```

Monitor your clusters with:

```bash
python manage.py qmonitor
```

Monitor your clusters' memory usage with:

```bash
python manage.py qmemory
```

Check overall statistics with:

```bash
python manage.py qinfo
```

## Creating Tasks

Use `async_task` from your code to quickly offload tasks:

```python
from django_q.tasks import async_task, result

# create the task
async_task('math.copysign', 2, -2)

# or with a reference
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

For more info see [Tasks](https://tinuvi.github.io/django-q2-full-of-juice/tasks/)

## Schedule

Schedules are regular Django models. You can manage them through the Admin page or directly from your code:

```python
# Use the schedule function
from django_q.tasks import schedule

schedule('math.copysign',
         2, -2,
         hook='hooks.print_result',
         schedule_type=Schedule.DAILY)

# Or create the object directly
from django_q.models import Schedule

Schedule.objects.create(func='math.copysign',
                        hook='hooks.print_result',
                        args='2,-2',
                        schedule_type=Schedule.DAILY
                        )

# Run a task every 5 minutes, starting at 6 today
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
         cron='0 22 * * 1-5')
```

For more info check the [Schedules](https://tinuvi.github.io/django-q2-full-of-juice/schedules/) documentation.

## Development

There is an example project that you can use to develop with. Docker (compose) is being used to set everything up.
Please note that you will have to restart the django-q container when changes have been made to tasks or django-q.
You can start the example project with:

```bash
make dev
```

Create a superuser with:

```bash
make createsuperuser
```

## Testing

Running tests is easy with docker compose, it will also start the necessary databases. Just run:

```bash
make test
```

## Locale

Currently available in English, German, Turkish, and French.
Translation pull requests are always welcome.

## Acknowledgements

- Django Q was inspired by working with [Django-RQ](https://github.com/ui/django-rq) and [RQ](https://github.com/ui/django-rq)
- Human readable hashes by [HumanHash](https://github.com/zacharyvoase/humanhash)
- Redditors feedback at [r/django](https://www.reddit.com/r/django/)
- JetBrains for their [Open Source Support Program](https://www.jetbrains.com/community/opensource)
</content>
</invoke>
