import os
import unittest
from datetime import datetime, timedelta
from multiprocessing import Event, Value
from unittest import mock
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django.utils.timezone import is_naive

from django_q.brokers import Broker, get_broker
from django_q.conf import Conf
from django_q.monitor import monitor
from django_q.pusher import pusher
from django_q.queues import Queue
from django_q.scheduler import scheduler
from django_q.tasks import Schedule, fetch
from django_q.tasks import schedule as create_schedule
from django_q.utils import add_months, localtime
from django_q.worker import worker
from tests.settings import BASE_DIR
from tests.testing_utilities.multiple_database_routers import (
    TestingMultipleAppsDatabaseRouter,
    TestingReplicaDatabaseRouter,
)

REPLICA_DATABASE_ROUTERS = [
    f"{TestingReplicaDatabaseRouter.__module__}.{TestingReplicaDatabaseRouter.__name__}"
]
REPLICA_DATABASES = {
    "writable": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    },
    "replica": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    },
}

MULTIPLE_APPS_DATABASE_ROUTERS = [
    f"{TestingMultipleAppsDatabaseRouter.__module__}.{TestingMultipleAppsDatabaseRouter.__name__}"  # noqa: E501
]
MULTIPLE_APPS_DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    },
    "admin": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    },
}


class SchedulerTests(TransactionTestCase):
    def setUp(self):
        self.django_redis_patch = patch.object(Conf, "DJANGO_REDIS", "default")
        self.django_redis_patch.start()
        self.addCleanup(self.django_redis_patch.stop)
        self.broker: Broker = get_broker()

    def test_scheduler_daylight_saving_time_daily(self):
        # Set up a startdate in the Amsterdam timezone (without dst 1 hour ahead). The
        # 28th of March 2021 is the day when sunlight saving starts (at 2 am)
        broker = self.broker
        with patch.object(Conf, "TIME_ZONE", "Europe/Amsterdam"):
            tz = ZoneInfo("Europe/Amsterdam")
            broker.list_key = "scheduler_test:q"
            # Let's start a schedule at 1 am on the 27th of March (Amsterdam timezone)
            start_date = datetime(2021, 3, 27, 1, 0, 0)

            schedule = create_schedule(
                "math.copysign",
                1,
                -1,
                name="test math",
                schedule_type=Schedule.DAILY,
                next_run=start_date,
            )

            scheduler(broker=broker)
            schedule.refresh_from_db()

            next_run = schedule.next_run
            self.assertEqual(str(next_run), "2021-03-28 00:00:00+00:00")

            next_run = next_run.astimezone(tz)
            self.assertEqual(str(next_run), "2021-03-28 01:00:00+01:00")

            scheduler(broker=broker)
            schedule.refresh_from_db()

            next_run = schedule.next_run
            self.assertEqual(str(next_run), "2021-03-28 23:00:00+00:00")
            next_run = next_run.astimezone(tz)
            self.assertEqual(str(next_run), "2021-03-29 01:00:00+02:00")

            scheduler(broker=broker)
            schedule.refresh_from_db()

            next_run = schedule.next_run
            self.assertEqual(str(next_run), "2021-03-29 23:00:00+00:00")
            next_run = next_run.astimezone(tz)
            self.assertEqual(str(next_run), "2021-03-30 01:00:00+02:00")

            start_date = datetime(2021, 10, 29, 1, 0, 0)
            schedule = create_schedule(
                "tests.tasks.word_multiply",
                2,
                name="multiply",
                schedule_type=Schedule.DAILY,
                next_run=start_date,
            )

            scheduler(broker=broker)
            schedule.refresh_from_db()
            next_run = schedule.next_run
            self.assertEqual(str(next_run), "2021-10-29 23:00:00+00:00")
            next_run = next_run.astimezone(tz)
            self.assertEqual(str(next_run), "2021-10-30 01:00:00+02:00")

            scheduler(broker=broker)
            schedule.refresh_from_db()
            next_run = schedule.next_run
            self.assertEqual(str(next_run), "2021-10-30 23:00:00+00:00")
            next_run = next_run.astimezone(tz)
            self.assertEqual(str(next_run), "2021-10-31 01:00:00+02:00")

            scheduler(broker=broker)
            schedule.refresh_from_db()
            next_run = schedule.next_run
            self.assertEqual(str(next_run), "2021-11-01 00:00:00+00:00")
            next_run = next_run.astimezone(tz)
            self.assertEqual(str(next_run), "2021-11-01 01:00:00+01:00")

    def test_scheduler(self):
        broker = self.broker
        broker.list_key = "scheduler_test:q"
        broker.delete_queue()
        schedule = create_schedule(
            "math.copysign",
            1,
            -1,
            name="test math",
            hook="tests.tasks.result",
            schedule_type=Schedule.HOURLY,
            repeats=1,
        )
        self.assertIsNone(schedule.last_run())
        # check duplicate constraint
        with self.assertRaises(IntegrityError):
            create_schedule(
                "math.copysign",
                1,
                -1,
                name="test math",
                hook="tests.tasks.result",
                schedule_type=Schedule.HOURLY,
                repeats=1,
            )
        # run scheduler
        scheduler(broker=broker)
        # set up the workflow
        task_queue = Queue()
        stop_event = Event()
        stop_event.set()
        # push it
        pusher(task_queue, stop_event, broker=broker)
        self.assertEqual(task_queue.qsize(), 1)
        self.assertEqual(broker.queue_size(), 0)
        task_queue.put("STOP")
        # let a worker handle them
        result_queue = Queue()
        worker(task_queue, result_queue, Value("b", -1))
        self.assertEqual(result_queue.qsize(), 1)
        result_queue.put("STOP")
        # store the results
        monitor(result_queue)
        self.assertEqual(result_queue.qsize(), 0)
        schedule = Schedule.objects.get(pk=schedule.pk)
        self.assertEqual(schedule.repeats, 0)
        self.assertIsNotNone(schedule.last_run())
        self.assertTrue(schedule.success())
        self.assertLess(schedule.next_run, timezone.now() + timedelta(hours=1))
        task = fetch(schedule.task)
        self.assertIsNotNone(task)
        self.assertTrue(task.success)
        self.assertLess(task.result, 0)
        # Once schedule with delete
        once_schedule = create_schedule(
            "tests.tasks.word_multiply",
            2,
            word="django",
            schedule_type=Schedule.ONCE,
            repeats=-1,
            hook="tests.tasks.result",
        )
        self.assertTrue(hasattr(once_schedule, "pk"))
        # negative repeats
        always_schedule = create_schedule(
            "tests.tasks.word_multiply",
            2,
            word="django",
            schedule_type=Schedule.DAILY,
            repeats=-1,
            hook="tests.tasks.result",
        )
        self.assertTrue(hasattr(always_schedule, "pk"))
        # Minute schedule
        minute_schedule = create_schedule(
            "tests.tasks.word_multiply",
            2,
            word="django",
            schedule_type=Schedule.MINUTES,
            minutes=10,
        )
        self.assertTrue(hasattr(minute_schedule, "pk"))
        # Cron schedule
        cron_schedule = create_schedule(
            "tests.tasks.word_multiply",
            2,
            word="django",
            schedule_type=Schedule.CRON,
            cron="0 22 * * 1-5",
        )
        self.assertTrue(hasattr(cron_schedule, "pk"))
        self.assertIsNone(cron_schedule.full_clean())
        self.assertEqual(cron_schedule.__str__(), "tests.tasks.word_multiply")
        with self.assertRaises(ValidationError):
            create_schedule(
                "tests.tasks.word_multiply",
                2,
                word="django",
                schedule_type=Schedule.CRON,
                cron="0 22 * * 1-12",
            )
        # All other types
        for t in Schedule.TYPE:
            if t[0] == Schedule.CRON:
                continue
            schedule = create_schedule(
                "tests.tasks.word_multiply",
                2,
                word="django",
                schedule_type=t[0],
                repeats=1,
                hook="tests.tasks.result",
            )
            self.assertIsNotNone(schedule)
            self.assertIsNone(schedule.last_run())
            scheduler(broker=broker)
        # via model
        Schedule.objects.create(
            func="tests.tasks.word_multiply",
            args="2",
            kwargs='word="django"',
            schedule_type=Schedule.DAILY,
        )
        # scheduler
        scheduler(broker=broker)
        # ONCE schedule should be deleted
        self.assertFalse(Schedule.objects.filter(pk=once_schedule.pk).exists())
        # Catch up On
        with patch.object(Conf, "CATCH_UP", True):
            now = timezone.now()
            schedule = create_schedule(
                "tests.tasks.word_multiply",
                2,
                word="catch_up",
                schedule_type=Schedule.HOURLY,
                next_run=timezone.now() - timedelta(hours=12),
                repeats=-1,
            )
            scheduler(broker=broker)
            schedule = Schedule.objects.get(pk=schedule.pk)
            self.assertLess(schedule.next_run, now)
        # Catch up off
        with patch.object(Conf, "CATCH_UP", False):
            scheduler(broker=broker)
            schedule = Schedule.objects.get(pk=schedule.pk)
            self.assertGreater(schedule.next_run, now)
        broker.delete_queue()

        # test bimonthly
        schedule = create_schedule(
            "tests.tasks.word_multiply",
            2,
            word="catch_up",
            schedule_type=Schedule.BIMONTHLY,
        )
        scheduler(broker=broker)
        schedule = Schedule.objects.get(pk=schedule.pk)
        self.assertEqual(schedule.next_run.date(), add_months(timezone.now(), 2).date())

        # test biweekly
        schedule = create_schedule(
            "tests.tasks.word_multiply",
            2,
            word="catch_up",
            schedule_type=Schedule.BIWEEKLY,
        )
        scheduler(broker=broker)
        schedule = Schedule.objects.get(pk=schedule.pk)
        self.assertEqual(
            schedule.next_run.date(),
            (timezone.now() + timedelta(weeks=2)).date(),
        )
        broker.delete_queue()

        with patch.object(Conf, "CLUSTER_NAME", "some_cluster_name"):
            # create a schedule on another cluster
            create_schedule(
                "math.copysign",
                1,
                -1,
                name="test schedule on a another cluster",
                hook="tests.tasks.result",
                schedule_type=Schedule.HOURLY,
                cluster="some_other_cluster_name",
                repeats=1,
            )
            scheduler(broker=broker)
            task_queue = Queue()
            stop_event = Event()
            stop_event.set()
            pusher(task_queue, stop_event, broker=broker)
            self.assertEqual(task_queue.qsize(), 0)

        with patch.object(Conf, "CLUSTER_NAME", "default"):
            create_schedule(
                "math.copysign",
                1,
                -1,
                name="test schedule with no cluster",
                hook="tests.tasks.result",
                schedule_type=Schedule.HOURLY,
                cluster="default",
                repeats=1,
            )
            scheduler(broker=broker)
            task_queue = Queue()
            stop_event = Event()
            stop_event.set()
            pusher(task_queue, stop_event, broker=broker)
            self.assertEqual(task_queue.qsize(), 1)

    def test_intended_schedule_kwarg(self):
        broker = self.broker
        broker.list_key = "scheduler_test:q"
        broker.delete_queue()
        run_date = timezone.now() - timedelta(hours=1)
        schedule = create_schedule(
            "math.copysign",
            1,
            -1,
            name="test math",
            hook="tests.tasks.result",
            schedule_type=Schedule.HOURLY,
            repeats=1,
            next_run=run_date,
            intended_date_kwarg="intended_date",
        )
        self.assertIsNone(schedule.last_run())
        self.assertEqual(schedule.intended_date_kwarg, "intended_date")
        scheduler(broker=broker)
        task_queue = Queue()
        stop_event = Event()
        stop_event.set()
        pusher(task_queue, stop_event, broker=broker)
        self.assertEqual(task_queue.qsize(), 1)
        task = task_queue.get()
        self.assertIn("intended_date", task["kwargs"])
        self.assertEqual(task["kwargs"]["intended_date"], run_date.isoformat())


class SchedulerOrmTests(TransactionTestCase):
    def setUp(self):
        self.orm_patch = patch.object(Conf, "ORM", "default")
        self.orm_patch.start()
        self.addCleanup(self.orm_patch.stop)

    @override_settings(
        DATABASE_ROUTERS=REPLICA_DATABASE_ROUTERS, DATABASES=REPLICA_DATABASES
    )
    def test_scheduler_atomic_must_specify_the_write_db(self):
        """
        GIVEN an environment with a read/write configured replica database
        WHEN the scheduler is called
        THEN the transaction must be called with the write database.
        """
        broker = get_broker(list_key="scheduler_test:q")
        with mock.patch("django_q.cluster.db.transaction") as mocked_db:
            scheduler(broker=broker)
            mocked_db.atomic.assert_called_with(using="writable")

    @override_settings(
        DATABASE_ROUTERS=MULTIPLE_APPS_DATABASE_ROUTERS,
        DATABASES=MULTIPLE_APPS_DATABASES,
    )
    def test_scheduler_atomic_must_specify_the_database_based_on_router_redirection(
        self,
    ):
        """
        GIVEN an environment without a read replica database
        WHEN the scheduler is called
        THEN the transaction atomic must be called using the default connection.
        """
        broker = get_broker(list_key="scheduler_test:q")
        with mock.patch("django_q.cluster.db.transaction") as mocked_db:
            scheduler(broker=broker)
            mocked_db.atomic.assert_called_with(using="default")


class SchedulerSaveTests(TestCase):
    def test_schedule_save_sets_next_run_for_cron(self):
        """Ensure Schedule.save() sets next_run correctly for CRON schedules."""
        cron_expression = "0 12 * * *"  # Executes daily at 12pm
        schedule = Schedule(
            func="math.sqrt",
            schedule_type=Schedule.CRON,
            cron=cron_expression,
        )

        self.assertIsNotNone(schedule.next_run)
        self.assertIsNone(schedule.pk)

        initial_next_run = schedule.next_run
        schedule.save()

        # After save, next_run must be recalculated based on the CRON expression
        self.assertGreater(schedule.next_run, initial_next_run)


class SchedulerSaveDirectDBTests(TransactionTestCase):
    def setUp(self):
        self.django_redis_patch = patch.object(Conf, "DJANGO_REDIS", "default")
        self.django_redis_patch.start()
        self.addCleanup(self.django_redis_patch.stop)
        self.broker = get_broker()

    def test_schedule_save_direct_db(self):
        """Ensure Schedule.save() updates next_run correctly when created directly in DB."""
        cron_expression = "0 12 * * *"  # Executes daily at 12pm

        schedule = Schedule.objects.create(
            func="math.sqrt",
            schedule_type=Schedule.CRON,
            cron=cron_expression,
        )

        self.assertIsNotNone(schedule.next_run)
        self.assertGreater(schedule.next_run, timezone.now())

        scheduler(self.broker)

        self.assertEqual(self.broker.queue_size(), 0)


class LocaltimeTests(unittest.TestCase):
    def test_localtime(self):
        self.assertFalse(is_naive(localtime()))

    @override_settings(USE_TZ=False)
    def test_naive_localtime(self):
        self.assertTrue(is_naive(localtime()))
