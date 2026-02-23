"""Tests for v0.2.0 features: due dates, overdue, export."""
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from agent_tasks import TaskQueue
from agent_tasks.task_queue import PENDING, RUNNING, DONE, FAILED


class TestDueDates(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.tq = TaskQueue(self.d)
        self.tq.init()

    def test_add_with_due(self):
        due = "2026-03-01T12:00:00+00:00"
        task = self.tq.add("Deadline task", due_at=due)
        self.assertEqual(task.due_at, due)
        fetched = self.tq.get(task.id)
        self.assertEqual(fetched.due_at, due)

    def test_add_without_due(self):
        task = self.tq.add("No deadline")
        self.assertIsNone(task.due_at)

    def test_overdue_returns_past_due(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self.tq.add("Overdue", due_at=past)
        self.tq.add("Not yet", due_at=future)
        self.tq.add("No due")
        overdue = self.tq.overdue()
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0].name, "Overdue")

    def test_overdue_excludes_done(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        t = self.tq.add("Done task", due_at=past)
        self.tq.start(t.id)
        self.tq.complete(t.id)
        self.assertEqual(len(self.tq.overdue()), 0)


class TestExport(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.tq = TaskQueue(self.d)
        self.tq.init()

    def test_export_md(self):
        self.tq.add("Task A", tags=["dev"])
        t = self.tq.add("Task B", priority=5)
        self.tq.start(t.id)
        self.tq.complete(t.id, result="Done!")
        md = self.tq.export("md")
        self.assertIn("# Task Report", md)
        self.assertIn("Task A", md)
        self.assertIn("Task B", md)
        self.assertIn("Done!", md)
        self.assertIn("Pending", md)

    def test_export_json(self):
        self.tq.add("JSON task")
        out = self.tq.export("json")
        import json
        data = json.loads(out)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "JSON task")

    def test_export_empty(self):
        md = self.tq.export("md")
        self.assertIn("Total: 0", md)

    def test_export_with_due(self):
        self.tq.add("Due task", due_at="2026-03-01T12:00:00+00:00")
        md = self.tq.export("md")
        self.assertIn("📅 2026-03-01", md)


if __name__ == "__main__":
    unittest.main()
