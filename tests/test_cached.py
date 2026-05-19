import time
from copy import deepcopy
from multiprocessing import Event, Value
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings

from django_q.brokers import get_broker
from django_q.conf import Conf
from django_q.monitor import monitor
from django_q.pusher import pusher
from django_q.queues import Queue
from django_q.tasks import (
    AsyncTask,
    Chain,
    Iter,
    async_chain,
    async_iter,
    async_task,
    count_group,
    delete_cached,
    delete_group,
    fetch,
    fetch_group,
    result,
    result_group,
)
from django_q.worker import worker


def _sleeping_func(_):
    time.sleep(1)


class CachedTests(TransactionTestCase):
    def setUp(self):
        self.django_redis_patch = patch.object(Conf, "DJANGO_REDIS", "default")
        self.django_redis_patch.start()
        self.addCleanup(self.django_redis_patch.stop)
        self.broker = get_broker()

    def test_cached(self):
        broker = self.broker
        broker.purge_queue()
        broker.cache.clear()
        group = "cache_test"
        # queue the tests
        task_id = async_task("math.copysign", 1, -1, cached=True, broker=broker)
        async_task("math.copysign", 1, -1, cached=True, broker=broker, group=group)
        async_task("math.copysign", 1, -1, cached=True, broker=broker, group=group)
        async_task("math.copysign", 1, -1, cached=True, broker=broker, group=group)
        async_task("math.copysign", 1, -1, cached=True, broker=broker, group=group)
        async_task("math.copysign", 1, -1, cached=True, broker=broker, group=group)
        async_task("math.popysign", 1, -1, cached=True, broker=broker, group=group)
        iter_id = async_iter("math.floor", [i for i in range(10)], cached=True)
        # test wait on cache
        # test wait timeout
        self.assertIsNone(result(task_id, wait=10, cached=True))
        self.assertIsNone(fetch(task_id, wait=10, cached=True))
        self.assertIsNone(result_group(group, wait=10, cached=True))
        self.assertIsNone(result_group(group, count=2, wait=10, cached=True))
        self.assertIsNone(fetch_group(group, wait=10, cached=True))
        self.assertIsNone(fetch_group(group, count=2, wait=10, cached=True))
        # run a single inline cluster
        task_count = 17
        self.assertEqual(broker.queue_size(), task_count)
        task_queue = Queue()
        stop_event = Event()
        stop_event.set()
        for _ in range(task_count):
            pusher(task_queue, stop_event, broker=broker)
        self.assertEqual(broker.queue_size(), 0)
        self.assertEqual(task_queue.qsize(), task_count)
        task_queue.put("STOP")
        result_queue = Queue()
        worker(task_queue, result_queue, Value("f", -1))
        self.assertEqual(result_queue.qsize(), task_count)
        result_queue.put("STOP")
        monitor(result_queue)
        self.assertEqual(result_queue.qsize(), 0)
        # assert results
        self.assertEqual(result(task_id, wait=500, cached=True), -1)
        self.assertEqual(fetch(task_id, wait=500, cached=True).result, -1)
        # make sure it's not in the db backend
        self.assertIsNone(fetch(task_id))
        # assert group
        self.assertEqual(count_group(group, cached=True), 6)
        self.assertEqual(count_group(group, cached=True, failures=True), 1)
        self.assertEqual(result_group(group, cached=True), [-1, -1, -1, -1, -1])
        self.assertEqual(len(result_group(group, cached=True, failures=True)), 6)
        self.assertEqual(len(fetch_group(group, cached=True)), 6)
        self.assertEqual(len(fetch_group(group, cached=True, failures=False)), 5)
        delete_group(group, cached=True)
        self.assertIsNone(count_group(group, cached=True))
        delete_cached(task_id)
        self.assertIsNone(result(task_id, cached=True))
        self.assertIsNone(fetch(task_id, cached=True))
        # iter cached
        self.assertIsNone(result(iter_id))
        self.assertIsNotNone(result(iter_id, cached=True))
        broker.cache.clear()

    def test_iter(self):
        broker = self.broker
        broker.purge_queue()
        broker.cache.clear()
        it = [i for i in range(10)]
        it2 = [(1, -1), (2, -1), (3, -4), (5, 6)]
        it3 = (1, 2, 3, 4, 5)
        t = async_iter("math.floor", it, sync=True)
        t2 = async_iter("math.copysign", it2, sync=True)
        t3 = async_iter("math.floor", it3, sync=True)
        t4 = async_iter("math.floor", (1,), sync=True)
        result_t = result(t)
        self.assertIsNotNone(result_t)
        task_t = fetch(t)
        self.assertEqual(task_t.result, result_t)
        self.assertIsNotNone(result(t2))
        self.assertIsNotNone(result(t3))
        self.assertEqual(result(t4)[0], 1)
        # test iter class
        i = Iter("math.copysign", sync=True, cached=True)
        i.append(1, -1)
        i.append(2, -1)
        i.append(3, -4)
        i.append(5, 6)
        self.assertFalse(i.started)
        self.assertEqual(i.length(), 4)
        self.assertIsNotNone(i.run())
        self.assertEqual(len(i.result()), 4)
        self.assertEqual(len(i.fetch().result), 4)
        i.append(1, -7)
        self.assertIsNone(i.result())
        i.run()
        self.assertEqual(len(i.result()), 5)

    def test_iter_default_cache_timeout(self):
        """async_iter when it completes after the default Django cache timeout expires."""
        broker = self.broker
        cache_settings = deepcopy(self._cache_settings())
        cache_settings["default"]["TIMEOUT"] = 1
        with override_settings(CACHES=cache_settings):
            broker.purge_queue()
            broker.cache.clear()
            it = [i for i in range(2)]
            t = async_iter(_sleeping_func, it, sync=True)
            result_t = result(t)
            self.assertIsNotNone(result_t)

    @staticmethod
    def _cache_settings():
        from django.conf import settings

        return settings.CACHES

    def test_chain(self):
        broker = self.broker
        broker.purge_queue()
        broker.cache.clear()
        task_chain = Chain(sync=True)
        task_chain.append("math.floor", 1)
        task_chain.append("math.copysign", 1, -1)
        task_chain.append("math.floor", 2)
        self.assertEqual(task_chain.length(), 3)
        self.assertIsNone(task_chain.current())
        task_chain.run()
        r = task_chain.result(wait=1000)
        self.assertEqual(task_chain.current(), task_chain.length())
        self.assertEqual(len(r), task_chain.length())
        t = task_chain.fetch()
        self.assertEqual(len(t), task_chain.length())
        task_chain.cached = True
        task_chain.append("math.floor", 3)
        self.assertEqual(task_chain.length(), 4)
        task_chain.run()
        r = task_chain.result(wait=1000)
        self.assertEqual(task_chain.current(), task_chain.length())
        self.assertEqual(len(r), task_chain.length())
        t = task_chain.fetch()
        self.assertEqual(len(t), task_chain.length())
        # test single
        rid = async_chain(
            ["tests.tasks.hello", "tests.tasks.hello"],
            sync=True,
            cached=True,
        )
        self.assertEqual(result_group(rid, cached=True), ["hello", "hello"])

    def test_asynctask_class(self):
        broker = self.broker
        broker.purge_queue()
        broker.cache.clear()
        a = AsyncTask("math.copysign")
        self.assertEqual(a.func, "math.copysign")
        a.args = (1, -1)
        self.assertFalse(a.started)
        a.cached = True
        self.assertTrue(a.cached)
        a.sync = True
        self.assertTrue(a.sync)
        a.broker = broker
        self.assertEqual(a.broker, broker)
        a.run()
        self.assertEqual(a.result(), -1)
        self.assertEqual(a.fetch().result, -1)
        # again with kwargs
        a = AsyncTask("math.copysign", 1, -1, cached=True, sync=True, broker=broker)
        a.run()
        self.assertEqual(a.result(), -1)
        # with q_options
        a = AsyncTask(
            "math.copysign",
            1,
            -1,
            q_options={"cached": True, "sync": False, "broker": broker},
        )
        self.assertFalse(a.sync)
        a.sync = True
        self.assertTrue(a.kwargs["q_options"]["sync"])
        a.run()
        self.assertEqual(a.result(), -1)
        a.group = "async_class_test"
        self.assertEqual(a.group, "async_class_test")
        a.save = False
        self.assertFalse(a.save)
        a.hook = "djq.tests.tasks.hello"
        self.assertEqual(a.hook, "djq.tests.tasks.hello")
        self.assertFalse(a.started)
        a.run()
        self.assertEqual(a.result_group(), [-1])
        self.assertEqual(a.fetch_group(), [a.fetch()])
        # global overrides
        with patch.object(Conf, "SYNC", True), patch.object(Conf, "CACHED", True):
            a = AsyncTask("math.floor", 1.5)
            a.run()
            self.assertEqual(a.result(), 1)
