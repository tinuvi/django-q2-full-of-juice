from django.urls import path

from tasks_app import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("api/enqueue/", views.enqueue, name="enqueue"),
    path("api/enqueue-chain/", views.enqueue_chain, name="enqueue_chain"),
    path("api/enqueue-iter/", views.enqueue_iter, name="enqueue_iter"),
    path("api/schedule-once/", views.schedule_once, name="schedule_once"),
    path("api/schedule-cron/", views.schedule_cron, name="schedule_cron"),
    path(
        "api/schedule-recurring/",
        views.schedule_recurring,
        name="schedule_recurring",
    ),
    path("api/task/<str:task_id>/", views.get_task, name="get_task"),
    path("api/group/<str:group_name>/", views.group_view, name="group_view"),
    path("api/schedule/<int:schedule_id>/", views.get_schedule, name="get_schedule"),
    path("api/queue-size/", views.get_queue_size, name="get_queue_size"),
    path(
        "api/hook-audit/<str:task_id>/",
        views.get_hook_audit,
        name="get_hook_audit",
    ),
    path("api/signal-counts/", views.get_signal_counts, name="get_signal_counts"),
    path(
        "api/signal-counts/reset/",
        views.reset_signal_counts,
        name="reset_signal_counts",
    ),
    path(
        "api/exception-snapshot/<str:task_id>/",
        views.get_exception_snapshot,
        name="get_exception_snapshot",
    ),
    path(
        "api/chain-progress/",
        views.get_chain_progress_log,
        name="get_chain_progress_log",
    ),
    path(
        "api/chain-progress/reset/",
        views.reset_chain_progress_log,
        name="reset_chain_progress_log",
    ),
]
