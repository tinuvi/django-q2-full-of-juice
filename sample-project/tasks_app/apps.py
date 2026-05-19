from django.apps import AppConfig


class TasksAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tasks_app"

    def ready(self):
        # Connect django-q2 lifecycle signal handlers. Import lives here so
        # the app registry is fully initialised before signals fire.
        from tasks_app import signals

        signals.connect()
