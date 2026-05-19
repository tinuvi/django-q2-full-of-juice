import os
import sys
import threading
import unittest
import uuid as uuidlib
from datetime import datetime
from math import copysign
from multiprocessing import Event, Value
from time import sleep
from typing import Optional
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone

from django_q.brokers import Broker, get_broker
from django_q.cluster import Cluster, Sentinel
from django_q.conf import Conf
from django_q.humanhash import DEFAULT_WORDLIST, uuid
from django_q.models import Success, Task
from django_q.monitor import monitor, save_task
from django_q.pusher import pusher
from django_q.queues import Queue
from django_q.signals import (
    post_chain_progress,
    post_execute,
    post_execute_in_worker,
    pre_chain_progress,
    pre_enqueue,
    pre_execute,
)
from django_q.status import Stat
from django_q.tasks import (
    async_task,
    count_group,
    delete_group,
    fetch,
    fetch_group,
    queue_size,
    result,
    result_group,
)
from django_q.utils import add_months, add_years
from django_q.worker import worker
from tests.tasks import TaskError, multiply

myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + "/../")


class WordClass:
    def __init__(self):
        self.word_list = DEFAULT_WORDLIST

    def get_words(self):
        return self.word_list


def assert_result(task):
    assert task is not None
    assert task.success is True
    assert task.result == 1506


def assert_bad_result(task):
    assert task is not None
    assert task.success is False


class _BrokerFixtureMixin:
    """Common setUp that patches DJANGO_REDIS and exposes a default broker."""

    def setUp(self):
        super().setUp()
        self.django_redis_patch = patch.object(Conf, "DJANGO_REDIS", "default")
        self.django_redis_patch.start()
        self.addCleanup(self.django_redis_patch.stop)
        self.broker = get_broker()


class RedisConnectionTests(_BrokerFixtureMixin, unittest.TestCase):
    def test_redis_connection(self):
        self.assertTrue(self.broker.ping())


class SyncTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_sync(self):
        task = async_task(
            "tests.tasks.count_letters",
            DEFAULT_WORDLIST,
            broker=self.broker,
            sync=True,
        )
        self.assertEqual(result(task), 1506)

    def test_sync_raise_exception(self):
        with self.assertRaises(TaskError):
            async_task(
                "tests.tasks.raise_exception",
                broker=self.broker,
                sync=True,
            )


class ClusterInitialTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_cluster_initial(self):
        broker = self.broker
        broker.list_key = "initial_test:q"
        broker.delete_queue()
        c = Cluster(broker=broker)
        self.assertIsNone(c.sentinel)
        self.assertEqual(c.stat.status, Conf.STOPPED)
        self.assertGreater(c.start(), 0)
        self.assertTrue(c.sentinel.is_alive())
        self.assertTrue(c.is_running)
        self.assertFalse(c.is_stopping)
        self.assertFalse(c.is_starting)
        sleep(0.5)
        stat = c.stat
        self.assertEqual(stat.status, Conf.IDLE)
        self.assertTrue(c.stop())
        self.assertFalse(c.sentinel.is_alive())
        self.assertTrue(c.has_stopped)
        self.assertFalse(c.stop())
        broker.delete_queue()


class SentinelTests(TransactionTestCase):
    def test_sentinel(self):
        start_event = Event()
        stop_event = Event()
        stop_event.set()
        cluster_id = uuidlib.uuid4()
        s = Sentinel(
            stop_event,
            start_event,
            cluster_id=cluster_id,
            broker=get_broker("sentinel_test:q"),
        )
        self.assertTrue(start_event.is_set())
        self.assertEqual(s.status(), Conf.STOPPED)


class ClusterTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_cluster(self):
        broker = self.broker
        broker.list_key = "cluster_test:q"
        broker.delete_queue()
        task = async_task("tests.tasks.count_letters", DEFAULT_WORDLIST, broker=broker)
        self.assertEqual(broker.queue_size(), 1)
        task_queue = Queue()
        self.assertEqual(task_queue.qsize(), 0)
        result_queue = Queue()
        self.assertEqual(result_queue.qsize(), 0)
        event = Event()
        event.set()
        # Test push
        pusher(task_queue, event, broker=broker)
        self.assertEqual(task_queue.qsize(), 1)
        self.assertEqual(queue_size(broker=broker), 0)
        # Test work
        task_queue.put("STOP")
        worker(task_queue, result_queue, Value("f", -1))
        self.assertEqual(task_queue.qsize(), 0)
        self.assertEqual(result_queue.qsize(), 1)
        # Test monitor
        result_queue.put("STOP")
        monitor(result_queue)
        self.assertEqual(result_queue.qsize(), 0)
        # check result
        self.assertEqual(result(task), 1506)
        broker.delete_queue()

    def test_results(self):
        broker = self.broker
        broker.list_key = "cluster_test:q"
        broker.delete_queue()
        a = async_task(
            "tests.tasks.return_falsy_value",
            broker=broker,
        )

        task_queue = Queue()
        stop_event = Event()
        stop_event.set()
        pusher(task_queue, stop_event, broker=broker)
        task_queue.put("STOP")
        result_queue = Queue()
        worker(task_queue, result_queue, Value("f", -1))
        result_queue.put("STOP")
        monitor(result_queue)

        # should not loop indefinitely when a real value is returned
        value = result(a, wait=-1)
        self.assertEqual(value, [])


class EnqueueTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_enqueue(self):
        broker = self.broker
        admin_user = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="password"
        )
        broker.list_key = "cluster_test:q"
        broker.delete_queue()
        a = async_task(
            "tests.tasks.count_letters",
            DEFAULT_WORDLIST,
            hook="tests.test_cluster.assert_result",
            broker=broker,
        )
        b = async_task(
            "tests.tasks.count_letters2",
            WordClass(),
            hook="tests.test_cluster.assert_result",
            broker=broker,
        )
        # unknown argument
        c = async_task(
            "tests.tasks.count_letters",
            DEFAULT_WORDLIST,
            "oneargumentoomany",
            hook="tests.test_cluster.assert_bad_result",
            broker=broker,
        )
        # unknown function
        d = async_task(
            "tests.tasks.does_not_exist",
            WordClass(),
            hook="tests.test_cluster.assert_bad_result",
            broker=broker,
        )
        # function without result
        e = async_task("tests.tasks.countdown", 100000, broker=broker)
        # function as instance
        f = async_task(multiply, 753, 2, hook=assert_result, broker=broker)
        # model as argument
        g = async_task("tests.tasks.get_task_name", Task(name="John"), broker=broker)
        # args,kwargs, group and broken hook
        h = async_task(
            "tests.tasks.word_multiply",
            2,
            word="django",
            hook="fail.me",
            broker=broker,
        )
        # args unpickle test
        j = async_task(
            "tests.tasks.get_user_id",
            admin_user,
            broker=broker,
            group="test_j",
        )
        # q_options and save opt_out test
        k = async_task(
            "tests.tasks.get_user_id",
            admin_user,
            q_options={
                "broker": broker,
                "group": "test_k",
                "save": False,
                "timeout": 90,
            },
        )
        # test unicode
        self.assertEqual(Task(name="Amalia").__str__(), "Amalia")
        # check if everything has a task id
        for tid in (a, b, c, d, e, f, g, h, j, k):
            self.assertIsInstance(tid, str)
        # run the cluster to execute the tasks
        task_count = 10
        self.assertEqual(broker.queue_size(), task_count)
        task_queue = Queue()
        stop_event = Event()
        stop_event.set()
        # push the tasks
        for _ in range(task_count):
            pusher(task_queue, stop_event, broker=broker)
        self.assertEqual(broker.queue_size(), 0)
        self.assertEqual(task_queue.qsize(), task_count)
        task_queue.put("STOP")
        # test wait timeout
        self.assertIsNone(result(j, wait=10))
        self.assertIsNone(fetch(j, wait=10))
        self.assertIsNone(result_group("test_j", wait=10))
        self.assertIsNone(result_group("test_j", count=2, wait=10))
        self.assertIsNone(fetch_group("test_j", wait=10))
        self.assertIsNone(fetch_group("test_j", count=2, wait=10))
        # let a worker handle them
        result_queue = Queue()
        worker(task_queue, result_queue, Value("f", -1))
        self.assertEqual(result_queue.qsize(), task_count)
        result_queue.put("STOP")
        # store the results
        monitor(result_queue)
        self.assertEqual(result_queue.qsize(), 0)
        # Check the results
        # task a
        result_a = fetch(a)
        self.assertIsNotNone(result_a)
        self.assertTrue(result_a.success)
        self.assertEqual(result(a), 1506)
        # task b
        result_b = fetch(b)
        self.assertIsNotNone(result_b)
        self.assertTrue(result_b.success)
        self.assertEqual(result(b), 1506)
        # task c
        result_c = fetch(c)
        self.assertIsNotNone(result_c)
        self.assertFalse(result_c.success)
        # task d
        result_d = fetch(d)
        self.assertIsNotNone(result_d)
        self.assertFalse(result_d.success)
        # task e
        result_e = fetch(e)
        self.assertIsNotNone(result_e)
        self.assertTrue(result_e.success)
        self.assertIsNone(result(e))
        # task f
        result_f = fetch(f)
        self.assertIsNotNone(result_f)
        self.assertTrue(result_f.success)
        self.assertEqual(result(f), 1506)
        # task g
        result_g = fetch(g)
        self.assertIsNotNone(result_g)
        self.assertTrue(result_g.success)
        self.assertEqual(result(g), "John")
        # task h
        result_h = fetch(h)
        self.assertIsNotNone(result_h)
        self.assertTrue(result_h.success)
        self.assertEqual(result(h), 12)
        # task j
        result_j = fetch(j)
        self.assertIsNotNone(result_j)
        self.assertTrue(result_j.success)
        self.assertEqual(result_j.result, result_j.args[0].id)
        # check fetch, result by name
        self.assertEqual(fetch(result_j.name), result_j)
        self.assertEqual(result(result_j.name), result_j.result)
        # groups
        self.assertEqual(result_group("test_j")[0], result_j.result)
        self.assertEqual(result_j.group_result()[0], result_j.result)
        self.assertEqual(result_group("test_j", failures=True)[0], result_j.result)
        self.assertEqual(result_j.group_result(failures=True)[0], result_j.result)
        self.assertEqual(fetch_group("test_j")[0].id, [result_j][0].id)
        self.assertEqual(fetch_group("test_j", failures=False)[0].id, [result_j][0].id)
        self.assertEqual(count_group("test_j"), 1)
        self.assertEqual(result_j.group_count(), 1)
        self.assertEqual(count_group("test_j", failures=True), 0)
        self.assertEqual(result_j.group_count(failures=True), 0)
        self.assertEqual(delete_group("test_j"), 1)
        self.assertEqual(result_j.group_delete(), 0)
        deleted_group = delete_group("test_j", tasks=True)
        self.assertTrue(deleted_group is None or deleted_group[0] == 0)
        deleted_group = result_j.group_delete(tasks=True)
        self.assertTrue(deleted_group is None or deleted_group[0] == 0)
        # task k should not have been saved
        self.assertIsNone(fetch(k))
        self.assertIsNone(fetch(k, 100))
        self.assertIsNone(result(k, 100))
        broker.delete_queue()


class TimeoutTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_timeout(self):
        cases = (
            (1, {}),
            (10, {"timeout": 1}),
            (None, {"timeout": 1}),
        )
        for cluster_config_timeout, async_task_kwargs in cases:
            with self.subTest(
                cluster_config_timeout=cluster_config_timeout,
                async_task_kwargs=async_task_kwargs,
            ):
                broker = self.broker
                broker.list_key = "timeout_test:q"
                broker.purge_queue()
                async_task("time.sleep", 5, broker=broker, **async_task_kwargs)
                start_event = Event()
                stop_event = Event()
                cluster_id = uuidlib.uuid4()
                threading.Timer(3, stop_event.set).start()
                s = Sentinel(
                    stop_event,
                    start_event,
                    cluster_id=cluster_id,
                    broker=broker,
                    timeout=cluster_config_timeout,
                )
                self.assertTrue(start_event.is_set())
                self.assertEqual(s.status(), Conf.STOPPED)
                self.assertEqual(s.reincarnations, 1)
                broker.delete_queue()

    def test_timeout_task_finishes(self):
        cases = (
            (5, {}),
            (10, {"timeout": 5}),
            (1, {"timeout": 5}),
            (None, {"timeout": 5}),
        )
        for cluster_config_timeout, async_task_kwargs in cases:
            with self.subTest(
                cluster_config_timeout=cluster_config_timeout,
                async_task_kwargs=async_task_kwargs,
            ):
                broker = self.broker
                broker.list_key = "timeout_test:q"
                broker.purge_queue()
                async_task("time.sleep", 3, broker=broker, **async_task_kwargs)
                start_event = Event()
                stop_event = Event()
                cluster_id = uuidlib.uuid4()
                threading.Timer(6, stop_event.set).start()
                s = Sentinel(
                    stop_event,
                    start_event,
                    cluster_id=cluster_id,
                    broker=broker,
                    timeout=cluster_config_timeout,
                )
                self.assertTrue(start_event.is_set())
                self.assertEqual(s.status(), Conf.STOPPED)
                self.assertEqual(s.reincarnations, 0)
                broker.delete_queue()


class RecycleTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_recycle(self):
        broker = self.broker
        broker.list_key = "test_recycle_test:q"
        async_task("tests.tasks.multiply", 2, 2, broker=broker)
        async_task("tests.tasks.multiply", 2, 2, broker=broker)
        async_task("tests.tasks.multiply", 2, 2, broker=broker)
        start_event = Event()
        stop_event = Event()
        cluster_id = uuidlib.uuid4()
        with patch.object(Conf, "RECYCLE", 2), patch.object(Conf, "WORKERS", 1):
            threading.Timer(3, stop_event.set).start()
            s = Sentinel(stop_event, start_event, cluster_id=cluster_id, broker=broker)
            self.assertTrue(start_event.is_set())
            self.assertEqual(s.status(), Conf.STOPPED)
            self.assertEqual(s.reincarnations, 1)
            async_task("tests.tasks.multiply", 2, 2, broker=broker)
            async_task("tests.tasks.multiply", 2, 2, broker=broker)
            task_queue = Queue()
            result_queue = Queue()
            # push two tasks
            pusher(task_queue, stop_event, broker=broker)
            pusher(task_queue, stop_event, broker=broker)
            # worker should exit on recycle
            worker(task_queue, result_queue, Value("f", -1))
            # check if the work has been done
            self.assertEqual(result_queue.qsize(), 2)
            # save_limit test
            with patch.object(Conf, "SAVE_LIMIT", 1):
                result_queue.put("STOP")
                monitor(result_queue)
                self.assertEqual(Success.objects.count(), Conf.SAVE_LIMIT)
        broker.delete_queue()

    def test_save_limit_per_func(self):
        broker = self.broker
        broker.list_key = "test_recycle_test:q"
        async_task("tests.tasks.hello", broker=broker)
        async_task("tests.tasks.countdown", 2, broker=broker)
        async_task("tests.tasks.multiply", 2, 2, broker=broker)
        start_event = Event()
        stop_event = Event()
        cluster_id = uuidlib.uuid4()
        task_queue = Queue()
        result_queue = Queue()
        with patch.object(Conf, "RECYCLE", 3), patch.object(Conf, "WORKERS", 1):
            threading.Timer(3, stop_event.set).start()
            for _ in range(3):
                pusher(task_queue, stop_event, broker=broker)
            worker(task_queue, result_queue, Value("f", -1))
            s = Sentinel(stop_event, start_event, cluster_id=cluster_id, broker=broker)
            self.assertTrue(start_event.is_set())
            self.assertEqual(s.status(), Conf.STOPPED)
            self.assertEqual(result_queue.qsize(), 3)
            with (
                patch.object(Conf, "SAVE_LIMIT", 1),
                patch.object(Conf, "SAVE_LIMIT_PER", "func"),
            ):
                result_queue.put("STOP")
                monitor(result_queue)
        self.assertEqual(Success.objects.count(), 3)
        self.assertEqual(
            set(Success.objects.filter().values_list("func", flat=True)),
            {
                "tests.tasks.countdown",
                "tests.tasks.hello",
                "tests.tasks.multiply",
            },
        )
        broker.delete_queue()


class MaxRssTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_max_rss(self):
        broker = self.broker
        broker.list_key = "test_max_rss_test:q"
        async_task("tests.tasks.multiply", 2, 2, broker=broker)
        start_event = Event()
        stop_event = Event()
        cluster_id = uuidlib.uuid4()
        with patch.object(Conf, "MAX_RSS", 20000), patch.object(Conf, "WORKERS", 1):
            threading.Timer(3, stop_event.set).start()
            s = Sentinel(stop_event, start_event, cluster_id=cluster_id, broker=broker)
            self.assertTrue(start_event.is_set())
            self.assertEqual(s.status(), Conf.STOPPED)
            self.assertEqual(s.reincarnations, 1)
            async_task("tests.tasks.multiply", 2, 2, broker=broker)
            task_queue = Queue()
            result_queue = Queue()
            pusher(task_queue, stop_event, broker=broker)
            worker(task_queue, result_queue, Value("f", -1))
            self.assertEqual(result_queue.qsize(), 1)
            with patch.object(Conf, "SAVE_LIMIT", 1):
                result_queue.put("STOP")
                monitor(result_queue)
                self.assertEqual(Success.objects.count(), Conf.SAVE_LIMIT)
        broker.delete_queue()


class BadSecretTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_bad_secret(self):
        broker = self.broker
        broker.list_key = "test_bad_secret:q"
        async_task("math.copysign", 1, -1, broker=broker)
        stop_event = Event()
        stop_event.set()
        start_event = Event()
        cluster_id = uuidlib.uuid4()
        s = Sentinel(
            stop_event,
            start_event,
            cluster_id=cluster_id,
            broker=broker,
            start=False,
        )
        Stat(s).save()
        with patch.object(Conf, "SECRET_KEY", "OOPS"):
            stat = Stat.get_all()
            self.assertEqual(len(stat), 0)
            self.assertIsNone(Stat.get(pid=s.parent_pid, cluster_id=cluster_id))
            task_queue = Queue()
            pusher(task_queue, stop_event, broker=broker)
            result_queue = Queue()
            task_queue.put("STOP")
            worker(
                task_queue,
                result_queue,
                Value("f", -1),
            )
            self.assertEqual(result_queue.qsize(), 0)
        broker.delete_queue()


class AttemptCountTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_attempt_count(self):
        broker = self.broker
        with patch.object(Conf, "MAX_ATTEMPTS", 3):
            tag = uuid()
            task = {
                "id": tag[1],
                "name": tag[0],
                "func": "math.copysign",
                "args": (1, -1),
                "kwargs": {},
                "started": timezone.now(),
                "stopped": timezone.now(),
                "success": False,
                "result": None,
            }
            # initial save - no success
            save_task(task, broker)
            self.assertTrue(Task.objects.filter(id=task["id"]).exists())
            saved_task = Task.objects.get(id=task["id"])
            self.assertEqual(saved_task.attempt_count, 1)
            sleep(0.5)
            # second save
            task["stopped"] = timezone.now()
            save_task(task, broker)
            saved_task = Task.objects.get(id=task["id"])
            self.assertEqual(saved_task.attempt_count, 2)
            # third save
            task["stopped"] = timezone.now()
            save_task(task, broker)
            saved_task = Task.objects.get(id=task["id"])
            self.assertEqual(saved_task.attempt_count, 3)
            # task should be removed from queue
            self.assertEqual(broker.queue_size(), 0)


class UpdateFailedTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_update_failed(self):
        broker = self.broker
        tag = uuid()
        task = {
            "id": tag[1],
            "name": tag[0],
            "func": "math.copysign",
            "args": (1, -1),
            "kwargs": {},
            "started": timezone.now(),
            "stopped": timezone.now(),
            "success": False,
            "result": None,
        }
        # initial save - no success
        save_task(task, broker)
        self.assertTrue(Task.objects.filter(id=task["id"]).exists())
        saved_task = Task.objects.get(id=task["id"])
        self.assertFalse(saved_task.success)
        sleep(0.5)
        # second save - no success
        old_stopped = task["stopped"]
        task["stopped"] = timezone.now()
        save_task(task, broker)
        saved_task = Task.objects.get(id=task["id"])
        self.assertGreater(saved_task.stopped, old_stopped)
        # third save - success
        task["stopped"] = timezone.now()
        task["result"] = "result"
        task["success"] = True
        save_task(task, broker)
        saved_task = Task.objects.get(id=task["id"])
        self.assertTrue(saved_task.success)
        # fourth save - no success
        task["result"] = None
        task["success"] = False
        task["stopped"] = old_stopped
        save_task(task, broker)
        # should not overwrite success
        saved_task = Task.objects.get(id=task["id"])
        self.assertTrue(saved_task.success)
        self.assertEqual(saved_task.result, "result")


class AcknowledgeFailureOverrideTests(TransactionTestCase):
    def test_acknowledge_failure_override(self):
        class VerifyAckMockBroker(Broker):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.acknowledgements = {}

            def acknowledge(self, task_id):
                count = self.acknowledgements.get(task_id, 0)
                self.acknowledgements[task_id] = count + 1

        tag = uuid()
        task_fail_ack = {
            "id": tag[1],
            "name": tag[0],
            "ack_id": "test_fail_ack_id",
            "ack_failure": True,
            "func": "math.copysign",
            "args": (1, -1),
            "kwargs": {},
            "started": timezone.now(),
            "stopped": timezone.now(),
            "success": False,
            "result": None,
        }

        tag = uuid()
        task_fail_no_ack = task_fail_ack.copy()
        task_fail_no_ack.update(
            {"id": tag[1], "name": tag[0], "ack_id": "test_fail_no_ack_id"}
        )
        del task_fail_no_ack["ack_failure"]

        tag = uuid()
        task_success_ack = task_fail_ack.copy()
        task_success_ack.update(
            {
                "id": tag[1],
                "name": tag[0],
                "ack_id": "test_success_ack_id",
                "success": True,
            }
        )
        del task_success_ack["ack_failure"]

        result_queue = Queue()
        result_queue.put(task_fail_ack)
        result_queue.put(task_fail_no_ack)
        result_queue.put(task_success_ack)
        result_queue.put("STOP")
        broker = VerifyAckMockBroker(list_key="key")

        monitor(result_queue, broker)

        self.assertEqual(broker.acknowledgements.get("test_fail_ack_id"), 1)
        self.assertIsNone(broker.acknowledgements.get("test_fail_no_ack_id"))
        self.assertEqual(broker.acknowledgements.get("test_success_ack_id"), 1)


class SignalsTests(_BrokerFixtureMixin, TransactionTestCase):
    def test_pre_enqueue_signal(self):
        broker = self.broker
        broker.list_key = "pre_enqueue_test:q"
        broker.delete_queue()
        self.signal_was_called: bool = False
        self.task: Optional[dict] = None

        def handler(sender, task, **kwargs):
            self.signal_was_called = True
            self.task = task

        pre_enqueue.connect(handler)
        task_id = async_task("math.copysign", 1, -1, broker=broker)
        self.assertTrue(self.signal_was_called)
        self.assertEqual(self.task.get("id"), task_id)
        pre_enqueue.disconnect(handler)
        broker.delete_queue()

    def test_pre_execute_signal(self):
        broker = self.broker
        broker.list_key = "pre_execute_test:q"
        broker.delete_queue()
        self.signal_was_called: bool = False
        self.task: Optional[dict] = None
        self.func = None

        def handler(sender, task, func, **kwargs):
            self.signal_was_called = True
            self.task = task
            self.func = func

        pre_execute.connect(handler)
        task_id = async_task("math.copysign", 1, -1, broker=broker)
        task_queue = Queue()
        result_queue = Queue()
        event = Event()
        event.set()
        pusher(task_queue, event, broker=broker)
        task_queue.put("STOP")
        worker(task_queue, result_queue, Value("f", -1))
        result_queue.put("STOP")
        monitor(result_queue, broker)
        broker.delete_queue()
        self.assertTrue(self.signal_was_called)
        self.assertEqual(self.task.get("id"), task_id)
        self.assertEqual(self.func, copysign)
        pre_execute.disconnect(handler)

    def test_post_execute_signal(self):
        broker = self.broker
        broker.list_key = "post_execute_test:q"
        broker.delete_queue()
        self.signal_was_called: bool = False
        self.task: Optional[dict] = None
        self.func = None

        def handler(sender, task, **kwargs):
            self.signal_was_called = True
            self.task = task

        post_execute.connect(handler)
        task_id = async_task("math.copysign", 1, -1, broker=broker)
        task_queue = Queue()
        result_queue = Queue()
        event = Event()
        event.set()
        pusher(task_queue, event, broker=broker)
        task_queue.put("STOP")
        worker(task_queue, result_queue, Value("f", -1))
        result_queue.put("STOP")
        monitor(result_queue, broker)
        broker.delete_queue()
        self.assertTrue(self.signal_was_called)
        self.assertEqual(self.task.get("id"), task_id)
        self.assertEqual(self.task.get("result"), -1)
        post_execute.disconnect(handler)

    def test_post_execute_in_worker_signal(self):
        broker = self.broker
        broker.list_key = "post_execute_in_worker_test:q"
        broker.delete_queue()
        self.signal_was_called: bool = False
        self.task: Optional[dict] = None
        self.func = None

        def handler(sender, task, **kwargs):
            self.signal_was_called = True
            self.task = task

        post_execute_in_worker.connect(handler)
        task_id = async_task("math.copysign", 1, -1, broker=broker)
        task_queue = Queue()
        result_queue = Queue()
        event = Event()
        event.set()
        pusher(task_queue, event, broker=broker)
        task_queue.put("STOP")
        worker(task_queue, result_queue, Value("f", -1))
        result_queue.put("STOP")
        monitor(result_queue, broker)
        broker.delete_queue()
        self.assertTrue(self.signal_was_called)
        self.assertEqual(self.task.get("id"), task_id)
        self.assertEqual(self.task.get("result"), -1)
        post_execute_in_worker.disconnect(handler)

    def test_post_execute_in_worker_exc_info_is_none_on_success(self):
        broker = self.broker
        broker.list_key = "post_execute_in_worker_exc_info_success:q"
        broker.delete_queue()
        captured = {}

        def handler(sender, task, exc_info=None, **kwargs):
            captured["exc_info"] = exc_info
            captured["success"] = task.get("success")

        post_execute_in_worker.connect(handler)
        try:
            async_task("math.copysign", 1, -1, broker=broker)
            task_queue = Queue()
            result_queue = Queue()
            event = Event()
            event.set()
            pusher(task_queue, event, broker=broker)
            task_queue.put("STOP")
            worker(task_queue, result_queue, Value("f", -1))
            result_queue.put("STOP")
            monitor(result_queue, broker)
            self.assertTrue(captured["success"])
            self.assertIsNone(captured["exc_info"])
        finally:
            post_execute_in_worker.disconnect(handler)
            broker.delete_queue()

    def test_post_execute_in_worker_exc_info_carries_live_exception(self):
        broker = self.broker
        broker.list_key = "post_execute_in_worker_exc_info_failure:q"
        broker.delete_queue()
        captured = {}

        def handler(sender, task, exc_info=None, **kwargs):
            captured["exc_info"] = exc_info
            captured["success"] = task.get("success")

        post_execute_in_worker.connect(handler)
        try:
            async_task("tests.tasks.raise_exception", broker=broker)
            task_queue = Queue()
            result_queue = Queue()
            event = Event()
            event.set()
            pusher(task_queue, event, broker=broker)
            task_queue.put("STOP")
            worker(task_queue, result_queue, Value("f", -1))
            result_queue.put("STOP")
            monitor(result_queue, broker)
            self.assertFalse(captured["success"])
            exc_info = captured["exc_info"]
            self.assertIsNotNone(exc_info)
            exc_type, exc_value, exc_tb = exc_info
            self.assertIs(exc_type, TaskError)
            self.assertIsInstance(exc_value, TaskError)
            self.assertEqual(str(exc_value), "this is an exception!")
            self.assertIsNotNone(exc_tb)
        finally:
            post_execute_in_worker.disconnect(handler)
            broker.delete_queue()

    def test_pre_post_chain_progress_signals_fire_around_async_chain(self):
        broker = self.broker
        broker.list_key = "chain_progress_test:q"
        broker.delete_queue()
        events = []

        def pre_handler(sender, task, **kwargs):
            events.append(("pre", task.get("id")))

        def post_handler(sender, task, **kwargs):
            events.append(("post", task.get("id")))

        pre_chain_progress.connect(pre_handler)
        post_chain_progress.connect(post_handler)
        try:
            tag = uuid()
            task = {
                "id": tag[1],
                "name": tag[0],
                "func": "math.copysign",
                "args": (1, -1),
                "kwargs": {},
                "started": timezone.now(),
                "stopped": timezone.now(),
                "success": True,
                "result": -1.0,
                "chain": [("math.copysign", (1, -1))],
                "group": "chain-progress-group",
                "cached": False,
                "sync": False,
            }
            save_task(task, broker)
            # Order matters: pre fires before the inner async_chain runs, post
            # fires after the synchronous async_chain call returns.
            self.assertEqual(events, [("pre", task["id"]), ("post", task["id"])])
        finally:
            pre_chain_progress.disconnect(pre_handler)
            post_chain_progress.disconnect(post_handler)
            broker.delete_queue()

    def test_chain_progress_signals_do_not_fire_without_chain(self):
        broker = self.broker
        broker.list_key = "chain_progress_skip_test:q"
        broker.delete_queue()
        fired = []

        def handler(sender, task, **kwargs):
            fired.append(task.get("id"))

        pre_chain_progress.connect(handler)
        post_chain_progress.connect(handler)
        try:
            tag = uuid()
            task = {
                "id": tag[1],
                "name": tag[0],
                "func": "math.copysign",
                "args": (1, -1),
                "kwargs": {},
                "started": timezone.now(),
                "stopped": timezone.now(),
                "success": True,
                "result": -1.0,
                # no "chain" key
            }
            save_task(task, broker)
            self.assertEqual(fired, [])
        finally:
            pre_chain_progress.disconnect(handler)
            post_chain_progress.disconnect(handler)
            broker.delete_queue()

    def test_post_chain_progress_fires_even_if_async_chain_raises(self):
        broker = self.broker
        broker.list_key = "chain_progress_raise_test:q"
        broker.delete_queue()
        events = []

        def pre_handler(sender, task, **kwargs):
            events.append("pre")

        def post_handler(sender, task, **kwargs):
            events.append("post")

        pre_chain_progress.connect(pre_handler)
        post_chain_progress.connect(post_handler)

        def boom_async_chain(*args, **kwargs):
            raise RuntimeError("simulated async_chain failure")

        with patch("django_q.monitor.async_chain", side_effect=boom_async_chain):
            try:
                tag = uuid()
                task = {
                    "id": tag[1],
                    "name": tag[0],
                    "func": "math.copysign",
                    "args": (1, -1),
                    "kwargs": {},
                    "started": timezone.now(),
                    "stopped": timezone.now(),
                    "success": True,
                    "result": -1.0,
                    "chain": [("math.copysign", (1, -1))],
                    "group": "chain-progress-raise",
                    "cached": False,
                    "sync": False,
                }
                # The chain block in save_task is outside its inner try/except,
                # so the simulated async_chain failure propagates. The
                # try/finally we added must still let post_chain_progress fire
                # before the exception escapes.
                with self.assertRaises(RuntimeError):
                    save_task(task, broker)
                self.assertEqual(events, ["pre", "post"])
            finally:
                pre_chain_progress.disconnect(pre_handler)
                post_chain_progress.disconnect(post_handler)
                broker.delete_queue()


class DateUtilsTests(unittest.TestCase):
    def test_add_months(self):
        # add some months
        initial_date = datetime(2020, 2, 2)
        new_date = add_months(initial_date, 3)
        self.assertEqual(new_date.year, 2020)
        self.assertEqual(new_date.month, 5)
        self.assertEqual(new_date.day, 2)

        # push to next year
        initial_date = datetime(2020, 11, 2)
        new_date = add_months(initial_date, 3)
        self.assertEqual(new_date.year, 2021)
        self.assertEqual(new_date.month, 2)
        self.assertEqual(new_date.day, 2)

        # last day of the month
        initial_date = datetime(2020, 1, 31)
        new_date = add_months(initial_date, 1)
        self.assertEqual(new_date.year, 2020)
        self.assertEqual(new_date.month, 2)
        self.assertEqual(new_date.day, 29)

    def test_add_years(self):
        initial_date = datetime(2020, 2, 2)
        new_date = add_years(initial_date, 1)
        self.assertEqual(new_date.year, 2021)
        self.assertEqual(new_date.month, 2)
        self.assertEqual(new_date.day, 2)

        # test leap year
        initial_date = datetime(2020, 2, 29)
        new_date = add_years(initial_date, 1)
        self.assertEqual(new_date.year, 2021)
        self.assertEqual(new_date.month, 2)
        self.assertEqual(new_date.day, 28)
