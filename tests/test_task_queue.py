"""Tests for agent-tasks core functionality."""
import tempfile
import unittest

from agent_tasks import TaskQueue
from agent_tasks.task_queue import PENDING, RUNNING, DONE, FAILED, BLOCKED


class TestInit(unittest.TestCase):
    def test_init_creates_store(self):
        d = tempfile.mkdtemp()
        tq = TaskQueue(d)
        store = tq.init()
        self.assertTrue(store.is_dir())
        self.assertTrue((store / "tasks.jsonl").exists())
        self.assertTrue((store / "config.json").exists())


class TestAddAndGet(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.tq = TaskQueue(self.d)
        self.tq.init()

    def test_add_task(self):
        task = self.tq.add("Test task", description="Do something")
        self.assertEqual(task.name, "Test task")
        self.assertEqual(task.status, PENDING)
        self.assertEqual(task.priority, 3)

    def test_get_task(self):
        task = self.tq.add("Find me")
        found = self.tq.get(task.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Find me")

    def test_get_nonexistent(self):
        self.assertIsNone(self.tq.get("nope"))

    def test_add_with_priority(self):
        task = self.tq.add("Urgent", priority=5)
        self.assertEqual(task.priority, 5)

    def test_add_with_tags(self):
        task = self.tq.add("Tagged", tags=["ops", "deploy"])
        self.assertEqual(task.tags, ["ops", "deploy"])


class TestLifecycle(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.tq = TaskQueue(self.d)
        self.tq.init()

    def test_start_complete(self):
        task = self.tq.add("Work")
        self.tq.start(task.id)
        t = self.tq.get(task.id)
        self.assertEqual(t.status, RUNNING)
        self.assertIsNotNone(t.started_at)

        self.tq.complete(task.id, result="Done!")
        t = self.tq.get(task.id)
        self.assertEqual(t.status, DONE)
        self.assertEqual(t.result, "Done!")
        self.assertIsNotNone(t.completed_at)

    def test_fail_with_retry(self):
        task = self.tq.add("Flaky", priority=1)
        self.tq.start(task.id)
        t = self.tq.fail(task.id, error="timeout")
        self.assertEqual(t.status, PENDING)  # auto-retry
        self.assertEqual(t.retries, 1)

    def test_fail_permanently(self):
        tq = TaskQueue(self.d, config={"max_retries": 1})
        tq.init()
        task = tq.add("One shot")
        tq.start(task.id)
        t = tq.fail(task.id, error="boom")
        self.assertEqual(t.status, FAILED)

    def test_cancel(self):
        task = self.tq.add("Cancel me")
        t = self.tq.cancel(task.id)
        self.assertEqual(t.status, FAILED)
        self.assertEqual(t.error, "Cancelled")

    def test_delete(self):
        task = self.tq.add("Delete me")
        self.assertTrue(self.tq.delete(task.id))
        self.assertIsNone(self.tq.get(task.id))
        self.assertFalse(self.tq.delete("nope"))


class TestPriorityQueue(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.tq = TaskQueue(self.d)
        self.tq.init()

    def test_next_returns_highest_priority(self):
        self.tq.add("Low", priority=1)
        self.tq.add("High", priority=5)
        self.tq.add("Medium", priority=3)
        task = self.tq.next()
        self.assertEqual(task.name, "High")

    def test_next_empty(self):
        self.assertIsNone(self.tq.next())

    def test_next_skips_running(self):
        t1 = self.tq.add("First", priority=5)
        self.tq.add("Second", priority=4)
        self.tq.start(t1.id)
        task = self.tq.next()
        self.assertEqual(task.name, "Second")


class TestDependencies(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.tq = TaskQueue(self.d)
        self.tq.init()

    def test_blocked_by_dependency(self):
        t1 = self.tq.add("First")
        t2 = self.tq.add("Second", depends_on=[t1.id])
        self.assertEqual(t2.status, BLOCKED)

    def test_unblock_on_complete(self):
        t1 = self.tq.add("First")
        t2 = self.tq.add("Second", depends_on=[t1.id])
        self.assertEqual(t2.status, BLOCKED)

        self.tq.start(t1.id)
        self.tq.complete(t1.id)

        t2 = self.tq.get(t2.id)
        self.assertEqual(t2.status, PENDING)

    def test_next_skips_blocked(self):
        t1 = self.tq.add("First", priority=1)
        self.tq.add("Blocked", priority=5, depends_on=[t1.id])
        task = self.tq.next()
        self.assertEqual(task.name, "First")


class TestFiltering(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.tq = TaskQueue(self.d)
        self.tq.init()

    def test_list_by_status(self):
        self.tq.add("Pending")
        t = self.tq.add("Will run")
        self.tq.start(t.id)
        pending = self.tq.list(status=PENDING)
        self.assertEqual(len(pending), 1)
        running = self.tq.list(status=RUNNING)
        self.assertEqual(len(running), 1)

    def test_list_by_tag(self):
        self.tq.add("Ops task", tags=["ops"])
        self.tq.add("Dev task", tags=["dev"])
        ops = self.tq.list(tag="ops")
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].name, "Ops task")


class TestStats(unittest.TestCase):
    def test_stats(self):
        d = tempfile.mkdtemp()
        tq = TaskQueue(d)
        tq.init()
        tq.add("One")
        t = tq.add("Two")
        tq.start(t.id)
        s = tq.stats()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s[PENDING], 1)
        self.assertEqual(s[RUNNING], 1)


class TestClearAndCount(unittest.TestCase):
    def test_count_and_clear(self):
        d = tempfile.mkdtemp()
        tq = TaskQueue(d)
        tq.init()
        tq.add("A")
        tq.add("B")
        self.assertEqual(len(tq), 2)
        n = tq.clear()
        self.assertEqual(n, 2)
        self.assertEqual(len(tq), 0)


if __name__ == "__main__":
    unittest.main()
