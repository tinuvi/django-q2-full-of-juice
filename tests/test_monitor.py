import uuid
from unittest.mock import patch

from django.test import TransactionTestCase

from django_q.brokers import get_broker
from django_q.cluster import Cluster
from django_q.conf import Conf
from django_q.monitor_terminal import get_ids, info, monitor
from django_q.status import Stat
from django_q.tasks import async_task


def do_sync():
    async_task("tests.tasks.countdown", 1, sync=True, save=True)


class MonitorTests(TransactionTestCase):
    def test_monitor(self):
        cluster_id = uuid.uuid4()
        self.assertEqual(Stat.get(pid=0, cluster_id=cluster_id).sentinel, 0)
        c = Cluster()
        c.start()
        try:
            stats = monitor(run_once=True)
            self.assertTrue(get_ids())
        finally:
            c.stop()
        self.assertGreater(len(stats), 0)
        found_c = False
        for stat in stats:
            if stat.cluster_id == c.cluster_id:
                found_c = True
                self.assertGreater(stat.uptime(), 0)
                self.assertTrue(stat.empty_queues())
                break
        self.assertTrue(found_c)
        # test lock size
        with patch.object(Conf, "ORM", "default"):
            b = get_broker("monitor_test")
            b.enqueue("test")
            b.dequeue()
            self.assertEqual(b.lock_size(), 1)
            monitor(run_once=True, broker=b)
            b.delete_queue()

    def test_info(self):
        info()
        do_sync()
        info()
        for _ in range(24):
            do_sync()
        info()
