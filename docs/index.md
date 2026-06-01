# Django Q2 (full of juice)

[![PyPI version](https://img.shields.io/pypi/v/django-q2-full-of-juice.svg)](https://pypi.org/project/django-q2-full-of-juice/)

Django Q2 is a native Django task queue, scheduler and worker application using Python multiprocessing.

!!! note
    Django Q2 is a fork of Django Q. Big thanks to Ilan Steemers for starting this project. Unfortunately, development of Django Q has stalled since June 2021. Django Q2 is the new updated version of Django Q, with dependencies updates, docs updates and several bug fixes. Original repository: <https://github.com/Koed00/django-q>

## Features

- Multiprocessing worker pools
- Asynchronous tasks
- Scheduled, cron and repeated tasks
- Signed and compressed packages
- Failure and success database or cache
- Result hooks, groups and chains
- Django Admin integration
- PaaS compatible with multiple instances
- Multi cluster monitor
- Redis, IronMQ, SQS, MongoDB or ORM
- Rollbar and Sentry support

Django Q2 is tested with Python 3.12 and 3.13, and works with Django 5.0.x and 6.0.x.

Currently available in English, German, Turkish and French.

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
| Redis · IronMQ · Amazon SQS · MongoDB · Django ORM | ✅ | `Q_CLUSTER={"redis": {...}}` (or `orm` / `sqs` / `mongo` / `iron_mq`) — see [Brokers](brokers.md) |
| Custom broker class | ✅ | `Q_CLUSTER={"broker_class": "path.to.Broker"}` |
| Multiple clusters / queues on one backend | ✅ | `async_task(..., cluster="x")` / `ALT_CLUSTERS` |

### Operations & observability

| Capability | Status | How you get it |
|---|---|---|
| Management CLI: `qcluster` / `qmonitor` / `qmemory` / `qinfo` | ✅ | `python manage.py qmonitor` |
| Django Admin integration | ⚙️ | tasks & schedules visible in the Admin |
| Pluggable error reporters (Sentry / Rollbar) | 🧩 | `Q_CLUSTER={"error_reporter": {...}}` + reporter plugin |
| Lifecycle signals (`post_spawn`, `pre_enqueue`, `pre_execute`, `post_execute`, `post_execute_in_worker`) | ✅ | connect Django signals from [`django_q.signals`](signals.md) |
| Chain-progress signals (`pre_chain_progress` / `post_chain_progress`) | ✅ | carry cross-process context (e.g. OpenTelemetry) across chain links — see [Signals](signals.md) |
| OpenTelemetry-style instrumentation | 🧩 | built on the signals above — see [OpenTelemetry](opentelemetry.md) |
| Localized UI (English / German / Turkish / French) | ✅ | automatic via Django i18n |

## Contents

- [Installation](install.md)
- [Creating Tasks](tasks.md)
- [OpenTelemetry](opentelemetry.md)
