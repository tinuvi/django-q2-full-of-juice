"""HTTP surface used by the Playwright E2E suite.

The endpoints stay deliberately thin — they just expose django-q2 primitives
(`async_task`, `async_iter`, `async_chain`, `schedule`) and a small set of
read-side helpers so playwright can poll for task/group/schedule state.
"""

import datetime
import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django_q.models import Schedule
from django_q.tasks import (
    async_chain,
    async_iter,
    async_task,
    fetch,
    fetch_group,
    schedule,
)
from tasks_app.tasks import TASK_REGISTRY

_logger = logging.getLogger("tasks_app")


def health(_request):
    return JsonResponse({"status": "ok"})


def _resolve_task(name):
    """Return the dotted path for a registered task or None."""
    return TASK_REGISTRY.get(name)


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

    args = body.get("args", [])
    kwargs = body.get("kwargs", {})
    group = body.get("group")
    if group:
        kwargs = {**kwargs, "group": group}

    task_id = async_task(func, *args, **kwargs)
    return JsonResponse({"task_id": task_id, "task": body["task"], "group": group})


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


@csrf_exempt
@require_http_methods(["POST"])
def schedule_once(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    func = _resolve_task(body.get("task"))
    if not func:
        return JsonResponse(
            {"error": "unknown_task", "available": sorted(TASK_REGISTRY)}, status=400
        )

    args = body.get("args", [])
    kwargs = body.get("kwargs", {})
    name = body.get("name")
    run_in_secs = body.get("run_in_secs", 0)
    next_run = timezone.now() + datetime.timedelta(seconds=float(run_in_secs))

    # `repeats=1` ensures django-q2 keeps the Schedule row around after firing
    # (`repeats < 0` would cause the scheduler to delete it). Tests need to
    # read `Schedule.task` to correlate the spawned task back to the schedule.
    obj = schedule(
        func,
        *args,
        name=name,
        schedule_type=Schedule.ONCE,
        repeats=1,
        next_run=next_run,
        **kwargs,
    )
    return JsonResponse(
        {
            "schedule_id": obj.id,
            "name": obj.name,
            "next_run": obj.next_run.isoformat(),
        }
    )


def get_task(_request, task_id):
    task = fetch(task_id)
    if not task:
        return JsonResponse({"found": False, "task_id": task_id})
    return JsonResponse({"found": True, **_task_payload(task)})


def get_group(_request, group_name):
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
        }
    )
