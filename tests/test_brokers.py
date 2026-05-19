import os
import unittest
from time import sleep
from unittest.mock import patch

from django.test import TransactionTestCase

from django_q.brokers import Broker, get_broker
from django_q.conf import Conf
from django_q.humanhash import uuid
from tests.settings import MONGO_HOST, REDIS_HOST


class BrokerBaseTests(unittest.TestCase):
    def test_broker(self):
        broker = Broker()
        broker.enqueue("test")
        broker.dequeue()
        broker.queue_size()
        broker.lock_size()
        broker.purge_queue()
        broker.delete("id")
        broker.delete_queue()
        broker.acknowledge("test")
        broker.ping()
        broker.info()
        # stats
        self.assertIsNone(broker.get_stat("test_1"))
        broker.set_stat("test_1", "test", 3)
        self.assertEqual(broker.get_stat("test_1"), "test")
        self.assertEqual(broker.get_stats("test:*")[0], "test")
        # stats with no cache
        with patch.object(Conf, "CACHE", "not_configured"):
            broker.cache = broker.get_cache()
            self.assertIsNone(broker.get_stat("test_1"))
            broker.set_stat("test_1", "test", 3)
            self.assertIsNone(broker.get_stat("test_1"))
            self.assertIsNone(broker.get_stats("test:*"))

    def test_broker_set_stat_prunes_stale_master_list(self):
        # regression: set_stat should prune stale master-list entries on register
        broker = Broker()
        a_key = f"{Conf.Q_STAT}:A"
        b_key = f"{Conf.Q_STAT}:B"
        broker.cache.delete(Conf.Q_STAT)

        broker.set_stat(a_key, "state_a", 3)
        self.assertIn(a_key, broker.cache.get(Conf.Q_STAT))

        # Drop A's per-stat value to simulate a dead cluster whose TTL expired,
        # leaving the master-list entry as a stale reference.
        broker.cache.delete(a_key)
        self.assertIsNone(broker.get_stat(a_key))
        self.assertIn(a_key, broker.cache.get(Conf.Q_STAT))

        # Registering B should prune stale A from the master list.
        broker.set_stat(b_key, "state_b", 3)
        key_list = broker.cache.get(Conf.Q_STAT)
        self.assertNotIn(a_key, key_list)
        self.assertIn(b_key, key_list)
        self.assertEqual(broker.get_stat(b_key), "state_b")

    def test_broker_set_stat_skips_master_list_write_on_repeat(self):
        # set_stat should only write the master list when membership changes
        broker = Broker()
        a_key = f"{Conf.Q_STAT}:A"
        broker.cache.delete(Conf.Q_STAT)

        writes = []
        orig_set = broker.cache.set

        def counting_set(key, value, timeout=None, **kw):
            if key == Conf.Q_STAT:
                writes.append(key)
            return orig_set(key, value, timeout, **kw)

        with patch.object(broker.cache, "set", counting_set):
            # First call adds a new entry, one master-list write expected
            broker.set_stat(a_key, "state_a", 3)
            self.assertEqual(len(writes), 1)

            # Subsequent calls for the same key must not rewrite the master list
            broker.set_stat(a_key, "state_a", 3)
            broker.set_stat(a_key, "state_a", 3)
            broker.set_stat(a_key, "state_a", 3)
            self.assertEqual(len(writes), 1)

    def test_redis(self):
        with patch.object(Conf, "DJANGO_REDIS", None):
            broker = get_broker()
            self.assertTrue(broker.ping())
            self.assertIsNotNone(broker.info())
            with patch.object(Conf, "REDIS", {"host": REDIS_HOST, "port": 7799}):
                broker = get_broker()
                with self.assertRaises(Exception):
                    broker.ping()
            with patch.object(Conf, "REDIS", f"redis://{REDIS_HOST}:7799"):
                broker = get_broker()
                with self.assertRaises(Exception):
                    broker.ping()

    def test_custom(self):
        with patch.object(Conf, "BROKER_CLASS", "django_q.brokers.redis_broker.Redis"):
            broker = get_broker()
            self.assertTrue(broker.ping())
            self.assertIsNotNone(broker.info())
            self.assertEqual(broker.__class__.__name__, "Redis")

    @unittest.skipUnless(
        os.getenv("IRON_MQ_TOKEN"), reason="requires IronMQ credentials"
    )
    def test_ironmq(self):
        iron_mq = {
            "token": os.getenv("IRON_MQ_TOKEN"),
            "project_id": os.getenv("IRON_MQ_PROJECT_ID"),
        }
        with patch.object(Conf, "IRON_MQ", iron_mq):
            # check broker
            broker = get_broker(list_key=uuid()[0])
            self.assertTrue(broker.ping())
            self.assertIsNotNone(broker.info())
            # initialize the queue
            broker.enqueue("test")
            # clear before we start
            broker.purge_queue()
            self.assertEqual(broker.queue_size(), 0)
            # async_task
            broker.enqueue("test")
            # dequeue
            task = broker.dequeue()[0]
            self.assertEqual(task[1], "test")
            broker.acknowledge(task[0])
            self.assertIsNone(broker.dequeue())
            # delete job
            task_id = broker.enqueue("test")
            broker.delete(task_id)
            self.assertIsNone(broker.dequeue())
            # fail
            task_id = broker.enqueue("test")
            broker.fail(task_id)
            # bulk test
            for _ in range(5):
                broker.enqueue("test")
            with patch.object(Conf, "BULK", 5):
                tasks = broker.dequeue()
                for task in tasks:
                    self.assertIsNotNone(task)
                    broker.acknowledge(task[0])
                # duplicate acknowledge
                broker.acknowledge(task[0])
            # delete queue
            broker.enqueue("test")
            broker.enqueue("test")
            broker.purge_queue()
            self.assertIsNone(broker.dequeue())
            broker.delete_queue()

    @unittest.skipUnless(
        os.getenv("AWS_ACCESS_KEY_ID"), reason="requires AWS credentials"
    )
    def test_sqs(self):
        sqs = {
            "aws_region": os.getenv("AWS_REGION"),
            "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
            "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
            "receive_message_wait_time_seconds": 5,
        }
        with patch.object(Conf, "SQS", sqs):
            # check broker
            broker = get_broker(list_key="testing")
            self.assertIn("receive_message_wait_time_seconds", Conf.SQS)
            self.assertIn("aws_region", Conf.SQS)
            self.assertTrue(broker.ping())
            self.assertIsNotNone(broker.info())
            self.assertEqual(broker.queue_size(), 0)
            # async_task
            broker.enqueue("test")
            # dequeue
            task = broker.dequeue()[0]
            self.assertEqual(task[1], "test")
            broker.acknowledge(task[0])
            self.assertIsNone(broker.dequeue())
            # Retry test
            with patch.object(Conf, "RETRY", 1):
                broker.enqueue("test")
                sleep(2)
                # Sometimes SQS is not linear
                task = broker.dequeue()
                if not task:
                    self.skipTest("SQS being weird")
                task = task[0]
                self.assertGreater(len(task), 0)
                broker.acknowledge(task[0])
                sleep(2)
            # delete job
            with patch.object(Conf, "RETRY", 60):
                broker.enqueue("test")
                sleep(1)
                task = broker.dequeue()
                if not task:
                    self.skipTest("SQS being weird")
                task_id = task[0][0]
                broker.delete(task_id)
                self.assertIsNone(broker.dequeue())
                # fail
                broker.enqueue("test")
                while task is None:
                    task = broker.dequeue()[0]
                broker.fail(task[0][0])
            # bulk test
            for _ in range(10):
                broker.enqueue("test")
            with patch.object(Conf, "BULK", 12):
                tasks = broker.dequeue()
                for task in tasks:
                    self.assertIsNotNone(task)
                    broker.acknowledge(task[0])
                # duplicate acknowledge
                broker.acknowledge(task[0])
                self.assertEqual(broker.lock_size(), 0)
            # delete queue
            broker.enqueue("test")
            broker.purge_queue()
            broker.delete_queue()


class BrokerDBTests(TransactionTestCase):
    def test_orm(self):
        with patch.object(Conf, "ORM", "default"):
            # check broker
            broker = get_broker(list_key="orm_test")
            self.assertTrue(broker.ping())
            self.assertIsNotNone(broker.info())
            # clear before we start
            broker.delete_queue()
            # async_task
            broker.enqueue("test")
            self.assertEqual(broker.queue_size(), 1)
            # dequeue
            task = broker.dequeue()[0]
            self.assertEqual(task[1], "test")
            broker.acknowledge(task[0])
            self.assertEqual(broker.queue_size(), 0)
            # Retry test
            with patch.object(Conf, "RETRY", 1):
                broker.enqueue("test")
                self.assertEqual(broker.queue_size(), 1)
                broker.dequeue()
                self.assertEqual(broker.queue_size(), 0)
                sleep(1.5)
                self.assertEqual(broker.queue_size(), 1)
                task = broker.dequeue()[0]
                self.assertEqual(broker.queue_size(), 0)
                broker.acknowledge(task[0])
                sleep(1.5)
                self.assertEqual(broker.queue_size(), 0)
            # delete job
            task_id = broker.enqueue("test")
            broker.delete(task_id)
            self.assertIsNone(broker.dequeue())
            # fail
            task_id = broker.enqueue("test")
            broker.fail(task_id)
            # bulk test
            for _ in range(5):
                broker.enqueue("test")
            with patch.object(Conf, "BULK", 5):
                tasks = broker.dequeue()
                self.assertEqual(broker.lock_size(), Conf.BULK)
                for task in tasks:
                    self.assertIsNotNone(task)
                    broker.acknowledge(task[0])
                # test lock size
                self.assertEqual(broker.lock_size(), 0)
                # test duplicate acknowledge
                broker.acknowledge(task[0])
            # delete queue
            broker.enqueue("test")
            broker.enqueue("test")
            broker.delete_queue()
            self.assertEqual(broker.queue_size(), 0)

    def test_mongo(self):
        with patch.object(Conf, "MONGO", {"host": MONGO_HOST, "port": 27017}):
            # check broker
            broker = get_broker(list_key="mongo_test")
            self.assertTrue(broker.ping())
            self.assertIsNotNone(broker.info())
            # clear before we start
            broker.delete_queue()
            # async_task
            broker.enqueue("test")
            self.assertEqual(broker.queue_size(), 1)
            # dequeue
            task = broker.dequeue()[0]
            self.assertEqual(task[1], "test")
            broker.acknowledge(task[0])
            self.assertEqual(broker.queue_size(), 0)
            # Retry test
            with patch.object(Conf, "RETRY", 1):
                broker.enqueue("test")
                self.assertEqual(broker.queue_size(), 1)
                broker.dequeue()
                self.assertEqual(broker.queue_size(), 0)
                sleep(1.5)
                self.assertEqual(broker.queue_size(), 1)
                task = broker.dequeue()[0]
                self.assertEqual(broker.queue_size(), 0)
                broker.acknowledge(task[0])
                sleep(1.5)
                self.assertEqual(broker.queue_size(), 0)
            # delete job
            task_id = broker.enqueue("test")
            broker.delete(task_id)
            self.assertIsNone(broker.dequeue())
            # fail
            task_id = broker.enqueue("test")
            broker.fail(task_id)
            # bulk test
            for _ in range(5):
                broker.enqueue("test")
            tasks = [broker.dequeue()[0] for _ in range(5)]
            self.assertEqual(broker.lock_size(), 5)
            for task in tasks:
                self.assertIsNotNone(task)
                broker.acknowledge(task[0])
            # test lock size
            self.assertEqual(broker.lock_size(), 0)
            # test duplicate acknowledge
            broker.acknowledge(task[0])
            # delete queue
            broker.enqueue("test")
            broker.enqueue("test")
            broker.purge_queue()
            broker.delete_queue()
            self.assertEqual(broker.queue_size(), 0)
