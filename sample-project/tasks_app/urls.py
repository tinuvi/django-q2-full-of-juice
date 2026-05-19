from django.urls import path

from tasks_app import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("api/enqueue/", views.enqueue, name="enqueue"),
    path("api/enqueue-chain/", views.enqueue_chain, name="enqueue_chain"),
    path("api/enqueue-iter/", views.enqueue_iter, name="enqueue_iter"),
    path("api/schedule-once/", views.schedule_once, name="schedule_once"),
    path("api/task/<str:task_id>/", views.get_task, name="get_task"),
    path("api/group/<str:group_name>/", views.get_group, name="get_group"),
    path("api/schedule/<int:schedule_id>/", views.get_schedule, name="get_schedule"),
]
