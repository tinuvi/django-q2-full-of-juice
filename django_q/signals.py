import importlib

from django.db.models.signals import post_save
from django.dispatch import Signal, receiver
from django.utils.translation import gettext_lazy as _

from django_q.conf import logger
from django_q.models import Task


@receiver(post_save, sender=Task)
def call_hook(sender, instance, **kwargs):
    if instance.hook:
        f = instance.hook
        if not callable(f):
            try:
                module, func = f.rsplit(".", 1)
                m = importlib.import_module(module)
                f = getattr(m, func)
            except (ValueError, ImportError, AttributeError):
                logger.error(
                    _("malformed return hook '%(hook)s' for [%(name)s]")
                    % {"hook": instance.hook, "name": instance.name}
                )
                return
        try:
            f(instance)
        except Exception as e:
            logger.error(
                _("return hook %(hook)s failed on [%(name)s] because %(error)s")
                % {"hook": instance.hook, "name": instance.name, "error": str(e)}
            )


# args: proc_name
post_spawn = Signal()

# args: task
pre_enqueue = Signal()

# args: func, task
pre_execute = Signal()

# args: task
post_execute = Signal()

# args: func, task, exc_info
# `exc_info` mirrors `sys.exc_info()`: a `(type, value, traceback)` triple when
# the task raised, otherwise `None`. It lets observers (tracing/error reporters)
# capture the live exception object instead of re-parsing the formatted string
# stored in `task["result"]`.
post_execute_in_worker = Signal()

# args: task
# Fired in the monitor process immediately before `async_chain` enqueues the
# next link in a chain. Lets observers attach cross-process state (e.g.
# OpenTelemetry trace context restored from the just-finished task) so the
# `pre_enqueue` signal emitted by the new link sees the right context.
pre_chain_progress = Signal()

# args: task
# Paired with `pre_chain_progress`. Fires in the monitor process after the
# chain progression `async_chain` call returns, so observers can detach the
# context attached on `pre_chain_progress`.
post_chain_progress = Signal()
