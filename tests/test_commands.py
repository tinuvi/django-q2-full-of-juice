from django.core.management import call_command
from django.test import TestCase


class CommandsTests(TestCase):
    def test_qcluster(self):
        call_command("qcluster", run_once=True)

    def test_qmonitor(self):
        call_command("qmonitor", run_once=True)

    def test_qinfo(self):
        call_command("qinfo")
        call_command("qinfo", config=True)
        call_command("qinfo", ids=True)

    def test_qmemory(self):
        call_command("qmemory", run_once=True)
        call_command("qmemory", workers=True, run_once=True)
