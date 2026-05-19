"""HTTP surface used by the Playwright E2E suite.

The endpoints stay deliberately thin — they just expose django-q2 primitives
(`async_task`, `async_iter`, `async_chain`, `schedule`) and a small set of
read-side helpers so playwright can poll for task/group/schedule/hook/signal
state.
"""

import datetime
import json
import logging

from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django_q.models import Schedule
from django_q.tasks import (
    async_chain,
    async_iter,
    async_task,
    delete_group,
    fetch,
    fetch_group,
    queue_size,
    schedule,
)
from tasks_app import signals as tasks_signals
from tasks_app.tasks import HOOK_AUDIT_PREFIX, HOOK_REGISTRY, TASK_REGISTRY

_logger = logging.getLogger("tasks_app")

_OPTIONAL_ASYNC_TASK_KEYS = ("timeout", "save", "ack_failure")


def health(_request):
    return JsonResponse({"status": "ok"})


def _resolve_task(name):
    """Return the dotted path for a registered task or None."""
    return TASK_REGISTRY.get(name)


def _resolve_hook(name):
    """Return the dotted path for a registered hook or None."""
    if name is None:
        return None
    return HOOK_REGISTRY.get(name)


def _task_payload(task):
    """Serialize a django_q.Task instance into a JSON-safe dict."""
    return {
        "id": task.id,
        "name": task.name,
        "func": task.func,
        "group": task.group,
        "success": task.success,
        "attempt_count": task.attempt_count,
        "started": task.started.isoformat() if task.started else None,
        "stopped": task.stopped.isoformat() if task.stopped else None,
        # `result` is unpickled to a Python object; coerce via repr for anything
        # that's not natively JSON-serializable (e.g. exceptions, datetimes).
        "result": _jsonify(task.result),
    }


def _jsonify(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


def _build_async_task_kwargs(body):
    """Translate the JSON request body into kwargs accepted by `async_task`.

    Returns (extra_kwargs, error_response). If error_response is not None,
    the caller should return it directly.
    """
    kwargs = dict(body.get("kwargs", {}))

    # `task_name` becomes the `name` field on the Task; exposing it lets the
    # E2E suite fetch by human-readable name (Task.get_task accepts name too).
    task_name = body.get("task_name")
    if task_name:
        kwargs["task_name"] = task_name

    # Hooks are referenced by short alias and resolved here, so the HTTP API
    # never accepts an arbitrary dotted path from clients.
    hook_alias = body.get("hook")
    if hook_alias is not None:
        hook_path = _resolve_hook(hook_alias)
        if not hook_path:
            return None, JsonResponse(
                {"error": "unknown_hook", "available": sorted(HOOK_REGISTRY)},
                status=400,
            )
        kwargs["hook"] = hook_path

    for key in _OPTIONAL_ASYNC_TASK_KEYS:
        if key in body:
            kwargs[key] = body[key]

    group = body.get("group")
    if group:
        kwargs["group"] = group

    return kwargs, None


@csrf_exempt
@require_http_methods(["POST"])
def enqueue(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    func = _resolve_task(body.get("task"))
    if not func:
        return JsonResponse(
            {"error": "unknown_task", "available": sorted(TASK_REGISTRY)}, status=400
        )

    kwargs, error = _build_async_task_kwargs(body)
    if error:
        return error

    args = body.get("args", [])

    task_id = async_task(func, *args, **kwargs)
    return JsonResponse(
        {
            "task_id": task_id,
            "task": body["task"],
            "group": kwargs.get("group"),
            "task_name": kwargs.get("task_name"),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def enqueue_chain(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    raw_chain = body.get("chain", [])
    if not isinstance(raw_chain, list) or not raw_chain:
        return JsonResponse({"error": "chain_must_be_non_empty_list"}, status=400)

    chain = []
    for entry in raw_chain:
        func = _resolve_task(entry.get("task"))
        if not func:
            return JsonResponse(
                {
                    "error": "unknown_task",
                    "name": entry.get("task"),
                    "available": sorted(TASK_REGISTRY),
                },
                status=400,
            )
        chain.append((func, tuple(entry.get("args", [])), entry.get("kwargs", {})))

    # Capture length BEFORE calling async_chain — its implementation pops entries
    # off the list as it enqueues, so a post-call `len(chain)` is misleading.
    chain_length = len(chain)
    group_id = async_chain(chain)
    return JsonResponse({"group_id": group_id, "chain_length": chain_length})


@csrf_exempt
@require_http_methods(["POST"])
def enqueue_iter(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    func = _resolve_task(body.get("task"))
    if not func:
        return JsonResponse(
            {"error": "unknown_task", "available": sorted(TASK_REGISTRY)}, status=400
        )

    args_iter = body.get("args_iter", [])
    if not isinstance(args_iter, list) or not args_iter:
        return JsonResponse({"error": "args_iter_must_be_non_empty_list"}, status=400)

    arg_tuples = [tuple(entry) for entry in args_iter]
    # async_iter returns the iter_group; once all N sub-tasks finish, django-q2
    # coalesces their results into a single Task whose id == iter_group.
    iter_group = async_iter(func, arg_tuples)
    return JsonResponse({"iter_group": iter_group, "iter_count": len(arg_tuples)})


def _schedule_kwargs_from_body(body):
    """Common kwargs extraction for the schedule-* endpoints."""
    func = _resolve_task(body.get("task"))
    if not func:
        return None, JsonResponse(
            {"error": "unknown_task", "available": sorted(TASK_REGISTRY)}, status=400
        )

    hook_alias = body.get("hook")
    hook_path = None
    if hook_alias is not None:
        hook_path = _resolve_hook(hook_alias)
        if not hook_path:
            return None, JsonResponse(
                {"error": "unknown_hook", "available": sorted(HOOK_REGISTRY)},
                status=400,
            )

    return (
        {
            "func": func,
            "args": body.get("args", []),
            "kwargs": dict(body.get("kwargs", {})),
            "name": body.get("name"),
            "hook": hook_path,
            "intended_date_kwarg": body.get("intended_date_kwarg"),
        },
        None,
    )


@csrf_exempt
@require_http_methods(["POST"])
def schedule_once(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    parsed, error = _schedule_kwargs_from_body(body)
    if error:
        return error

    run_in_secs = body.get("run_in_secs", 0)
    next_run = timezone.now() + datetime.timedelta(seconds=float(run_in_secs))

    # `repeats=1` ensures django-q2 keeps the Schedule row around after firing
    # (`repeats < 0` would cause the scheduler to delete it). Tests need to
    # read `Schedule.task` to correlate the spawned task back to the schedule.
    obj = schedule(
        parsed["func"],
        *parsed["args"],
        name=parsed["name"],
        hook=parsed["hook"],
        intended_date_kwarg=parsed["intended_date_kwarg"],
        schedule_type=Schedule.ONCE,
        repeats=1,
        next_run=next_run,
        **parsed["kwargs"],
    )
    return JsonResponse(
        {
            "schedule_id": obj.id,
            "name": obj.name,
            "next_run": obj.next_run.isoformat(),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def schedule_cron(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    parsed, error = _schedule_kwargs_from_body(body)
    if error:
        return error

    cron = body.get("cron")
    if not cron:
        return JsonResponse({"error": "cron_required"}, status=400)

    # `repeats=1` makes the schedule fire exactly once and then stay around
    # (instead of recurring forever), which keeps the E2E deterministic.
    obj = schedule(
        parsed["func"],
        *parsed["args"],
        name=parsed["name"],
        hook=parsed["hook"],
        schedule_type=Schedule.CRON,
        cron=cron,
        repeats=1,
        **parsed["kwargs"],
    )
    return JsonResponse(
        {
            "schedule_id": obj.id,
            "name": obj.name,
            "next_run": obj.next_run.isoformat() if obj.next_run else None,
            "cron": obj.cron,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def schedule_recurring(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    parsed, error = _schedule_kwargs_from_body(body)
    if error:
        return error

    minutes = int(body.get("minutes", 1))
    repeats = int(body.get("repeats", 2))
    # `next_run` is set just slightly in the past so the very next scheduler
    # tick picks it up — we want fast feedback in E2E.
    next_run = timezone.now() - datetime.timedelta(seconds=1)

    obj = schedule(
        parsed["func"],
        *parsed["args"],
        name=parsed["name"],
        hook=parsed["hook"],
        schedule_type=Schedule.MINUTES,
        minutes=minutes,
        repeats=repeats,
        next_run=next_run,
        **parsed["kwargs"],
    )
    return JsonResponse(
        {
            "schedule_id": obj.id,
            "name": obj.name,
            "next_run": obj.next_run.isoformat(),
            "minutes": obj.minutes,
            "repeats": obj.repeats,
        }
    )


def get_task(_request, task_id):
    task = fetch(task_id)
    if not task:
        return JsonResponse({"found": False, "task_id": task_id})
    return JsonResponse({"found": True, **_task_payload(task)})


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
def group_view(request, group_name):
    if request.method == "DELETE":
        # `?tasks=true` deletes the underlying Task rows; otherwise only the
        # group label is unset (Task.group → NULL) and rows survive.
        delete_tasks = request.GET.get("tasks", "").lower() in ("1", "true", "yes")
        delete_group(group_name, tasks=delete_tasks)
        return JsonResponse({"group": group_name, "deleted_tasks": delete_tasks})

    # fetch_group with failures=True so we can introspect both successful and
    # failed members of a chain/group/iter.
    tasks = fetch_group(group_name, failures=True) or []
    serialized = [_task_payload(t) for t in tasks]
    success_count = sum(1 for t in serialized if t["success"])
    failure_count = sum(1 for t in serialized if t["success"] is False)
    return JsonResponse(
        {
            "group": group_name,
            "count": len(serialized),
            "success_count": success_count,
            "failure_count": failure_count,
            "tasks": serialized,
        }
    )


def get_queue_size(_request):
    return JsonResponse({"size": queue_size()})


def get_schedule(_request, schedule_id):
    try:
        obj = Schedule.objects.get(pk=schedule_id)
    except Schedule.DoesNotExist:
        return JsonResponse({"found": False, "schedule_id": schedule_id}, status=404)
    return JsonResponse(
        {
            "found": True,
            "schedule_id": obj.id,
            "name": obj.name,
            "func": obj.func,
            "schedule_type": obj.schedule_type,
            "repeats": obj.repeats,
            "next_run": obj.next_run.isoformat() if obj.next_run else None,
            "last_task_id": obj.task,
            "cron": obj.cron,
            "minutes": obj.minutes,
            "intended_date_kwarg": obj.intended_date_kwarg,
        }
    )


def get_hook_audit(_request, task_id):
    audit = cache.get(f"{HOOK_AUDIT_PREFIX}:{task_id}")
    if not audit:
        return JsonResponse({"found": False, "task_id": task_id})
    return JsonResponse({"found": True, **audit, "result": _jsonify(audit["result"])})


def get_signal_counts(_request):
    return JsonResponse(tasks_signals.signal_counts())


@csrf_exempt
@require_http_methods(["POST"])
def reset_signal_counts(_request):
    tasks_signals.reset_signal_counts()
    return JsonResponse({"reset": True, **tasks_signals.signal_counts()})
