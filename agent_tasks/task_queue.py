"""Core task queue implementation — file-based, zero dependencies."""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

STORE_DIR = ".agent-tasks"
TASKS_FILE = "tasks.jsonl"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "store_path": STORE_DIR,
    "max_retries": 3,
    "default_priority": 3,
    "default_timeout": 300,  # seconds
}

# Task statuses
PENDING = "pending"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
BLOCKED = "blocked"  # waiting on dependencies


class Task:
    """Represents a single task."""

    __slots__ = (
        "id", "name", "description", "status", "priority",
        "created_at", "started_at", "completed_at", "due_at",
        "tags", "metadata", "depends_on", "subtasks",
        "retries", "max_retries", "timeout",
        "result", "error",
    )

    def __init__(self, data: dict):
        self.id: str = data.get("id", uuid.uuid4().hex[:12])
        self.name: str = data.get("name", "")
        self.description: str = data.get("description", "")
        self.status: str = data.get("status", PENDING)
        self.priority: int = data.get("priority", 3)
        self.created_at: str = data.get("created_at", datetime.now(timezone.utc).isoformat())
        self.started_at: Optional[str] = data.get("started_at")
        self.completed_at: Optional[str] = data.get("completed_at")
        self.due_at: Optional[str] = data.get("due_at")
        self.tags: List[str] = data.get("tags", [])
        self.metadata: Dict[str, Any] = data.get("metadata", {})
        self.depends_on: List[str] = data.get("depends_on", [])
        self.subtasks: List[str] = data.get("subtasks", [])
        self.retries: int = data.get("retries", 0)
        self.max_retries: int = data.get("max_retries", 3)
        self.timeout: int = data.get("timeout", 300)
        self.result: Optional[str] = data.get("result")
        self.error: Optional[str] = data.get("error")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "due_at": self.due_at,
            "tags": self.tags,
            "metadata": self.metadata,
            "depends_on": self.depends_on,
            "subtasks": self.subtasks,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "result": self.result,
            "error": self.error,
        }

    def __repr__(self) -> str:
        return f"Task(id={self.id!r}, name={self.name!r}, status={self.status!r})"


class TaskQueue:
    """File-based task queue for AI agents.

    Usage:
        from agent_tasks import TaskQueue

        tq = TaskQueue("/path/to/project")
        tq.init()

        task = tq.add("Deploy to production", priority=5, tags=["ops"])
        tq.start(task.id)
        tq.complete(task.id, result="Deployed v2.1")

        next_task = tq.next()  # highest priority pending task
    """

    def __init__(self, path: Optional[str] = None, config: Optional[dict] = None):
        self._root = Path(path or os.getcwd())
        self._config = {**DEFAULT_CONFIG, **(config or {})}

    @property
    def store(self) -> Path:
        sp = self._config.get("store_path", STORE_DIR)
        p = Path(sp)
        if p.is_absolute():
            return p
        return self._root / sp

    @property
    def _tasks_path(self) -> Path:
        return self.store / TASKS_FILE

    def init(self) -> Path:
        """Initialize the task store."""
        self.store.mkdir(parents=True, exist_ok=True)
        cfg_path = self.store / CONFIG_FILE
        if not cfg_path.exists():
            cfg_path.write_text(json.dumps(self._config, indent=2))
        if not self._tasks_path.exists():
            self._tasks_path.touch()
        return self.store

    def _ensure_store(self):
        if not self.store.is_dir():
            raise FileNotFoundError(
                f"Task store not found at {self.store}. Call .init() first."
            )

    def _load_all(self) -> List[Task]:
        self._ensure_store()
        p = self._tasks_path
        if not p.exists():
            return []
        tasks = []
        for line in p.read_text().splitlines():
            line = line.strip()
            if line:
                tasks.append(Task(json.loads(line)))
        return tasks

    def _save_all(self, tasks: List[Task]):
        with open(self._tasks_path, "w") as f:
            for t in tasks:
                f.write(json.dumps(t.to_dict(), ensure_ascii=False) + "\n")

    def _find(self, task_id: str, tasks: Optional[List[Task]] = None) -> Optional[Task]:
        for t in (tasks or self._load_all()):
            if t.id == task_id:
                return t
        return None

    def add(
        self,
        name: str,
        description: str = "",
        priority: Optional[int] = None,
        tags: Optional[List[str]] = None,
        depends_on: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
        timeout: Optional[int] = None,
        due_at: Optional[str] = None,
    ) -> Task:
        """Add a new task. Returns the created Task.

        Args:
            due_at: Optional ISO-8601 datetime string for the deadline.
        """
        self._ensure_store()
        if priority is None:
            priority = self._config.get("default_priority", 3)
        priority = max(1, min(5, int(priority)))
        if timeout is None:
            timeout = self._config.get("default_timeout", 300)

        task = Task({
            "name": name,
            "description": description,
            "priority": priority,
            "tags": tags or [],
            "depends_on": depends_on or [],
            "metadata": metadata or {},
            "timeout": timeout,
            "due_at": due_at,
            "max_retries": self._config.get("max_retries", 3),
        })

        # Check if blocked by dependencies
        if task.depends_on:
            all_tasks = self._load_all()
            unfinished = [
                d for d in task.depends_on
                if any(t.id == d and t.status != DONE for t in all_tasks)
                or not any(t.id == d for t in all_tasks)
            ]
            if unfinished:
                task.status = BLOCKED

        with open(self._tasks_path, "a") as f:
            f.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")
        return task

    def get(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self._find(task_id)

    def list(
        self,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 50,
    ) -> List[Task]:
        """List tasks with optional filters."""
        tasks = self._load_all()
        if status:
            tasks = [t for t in tasks if t.status == status]
        if tag:
            tasks = [t for t in tasks if tag in t.tags]
        return tasks[-limit:]

    def next(self) -> Optional[Task]:
        """Get the highest-priority pending task (unblocked)."""
        tasks = self._load_all()
        pending = [t for t in tasks if t.status == PENDING]
        if not pending:
            return None
        # Sort by priority desc, then by created_at asc
        pending.sort(key=lambda t: (-t.priority, t.created_at))
        return pending[0]

    def start(self, task_id: str) -> Optional[Task]:
        """Mark a task as running."""
        tasks = self._load_all()
        task = self._find(task_id, tasks)
        if not task or task.status not in (PENDING, BLOCKED):
            return None
        task.status = RUNNING
        task.started_at = datetime.now(timezone.utc).isoformat()
        self._save_all(tasks)
        return task

    def complete(self, task_id: str, result: Optional[str] = None) -> Optional[Task]:
        """Mark a task as done."""
        tasks = self._load_all()
        task = self._find(task_id, tasks)
        if not task or task.status != RUNNING:
            return None
        task.status = DONE
        task.completed_at = datetime.now(timezone.utc).isoformat()
        task.result = result
        # Unblock dependent tasks
        self._unblock_dependents(task_id, tasks)
        self._save_all(tasks)
        return task

    def fail(self, task_id: str, error: Optional[str] = None) -> Optional[Task]:
        """Mark a task as failed. Auto-retries if retries < max_retries."""
        tasks = self._load_all()
        task = self._find(task_id, tasks)
        if not task or task.status != RUNNING:
            return None
        task.retries += 1
        if task.retries < task.max_retries:
            task.status = PENDING
            task.error = error
        else:
            task.status = FAILED
            task.completed_at = datetime.now(timezone.utc).isoformat()
            task.error = error
        self._save_all(tasks)
        return task

    def cancel(self, task_id: str) -> Optional[Task]:
        """Cancel a pending/blocked task."""
        tasks = self._load_all()
        task = self._find(task_id, tasks)
        if not task or task.status not in (PENDING, BLOCKED):
            return None
        task.status = FAILED
        task.completed_at = datetime.now(timezone.utc).isoformat()
        task.error = "Cancelled"
        self._save_all(tasks)
        return task

    def delete(self, task_id: str) -> bool:
        """Permanently delete a task."""
        tasks = self._load_all()
        new = [t for t in tasks if t.id != task_id]
        if len(new) == len(tasks):
            return False
        self._save_all(new)
        return True

    def add_subtask(self, parent_id: str, name: str, **kwargs) -> Optional[Task]:
        """Add a subtask to an existing task."""
        tasks = self._load_all()
        parent = self._find(parent_id, tasks)
        if not parent:
            return None
        subtask = self.add(name, depends_on=[parent_id] if kwargs.get("depends_on_parent") else None, **kwargs)
        # Re-load to get the subtask appended
        tasks = self._load_all()
        parent = self._find(parent_id, tasks)
        parent.subtasks.append(subtask.id)
        self._save_all(tasks)
        return subtask

    def stats(self) -> dict:
        """Get task statistics."""
        tasks = self._load_all()
        counts = {PENDING: 0, RUNNING: 0, DONE: 0, FAILED: 0, BLOCKED: 0}
        for t in tasks:
            counts[t.status] = counts.get(t.status, 0) + 1
        return {
            "total": len(tasks),
            **counts,
        }

    def _unblock_dependents(self, completed_id: str, tasks: List[Task]):
        """Check blocked tasks and unblock if all deps are done."""
        done_ids = {t.id for t in tasks if t.status == DONE}
        done_ids.add(completed_id)
        for t in tasks:
            if t.status == BLOCKED and t.depends_on:
                if all(d in done_ids for d in t.depends_on):
                    t.status = PENDING

    def overdue(self) -> List[Task]:
        """Return tasks that are past their due date and not done/failed."""
        now = datetime.now(timezone.utc).isoformat()
        tasks = self._load_all()
        return [
            t for t in tasks
            if t.due_at and t.due_at < now and t.status not in (DONE, FAILED)
        ]

    def export(self, fmt: str = "md") -> str:
        """Export tasks as markdown or JSON."""
        tasks = self._load_all()
        if fmt == "json":
            return json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False)
        # Markdown
        lines = ["# Task Report", ""]
        by_status = {}
        for t in tasks:
            by_status.setdefault(t.status, []).append(t)
        status_order = [RUNNING, PENDING, BLOCKED, DONE, FAILED]
        icons = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌", "blocked": "🔒"}
        for s in status_order:
            group = by_status.get(s, [])
            if not group:
                continue
            lines.append(f"## {icons.get(s, '')} {s.capitalize()} ({len(group)})")
            lines.append("")
            for t in group:
                pri = f" P{t.priority}" if t.priority != 3 else ""
                tags = f" `{', '.join(t.tags)}`" if t.tags else ""
                due = f" 📅 {t.due_at[:10]}" if t.due_at else ""
                lines.append(f"- **{t.name}**{pri}{tags}{due} [{t.id}]")
                if t.description:
                    lines.append(f"  {t.description}")
                if t.result:
                    lines.append(f"  → {t.result}")
                if t.error:
                    lines.append(f"  ⚠️ {t.error}")
            lines.append("")
        # Stats
        s = self.stats()
        lines.append(f"---\n*Total: {s['total']} | Done: {s[DONE]} | Pending: {s[PENDING]} | Failed: {s[FAILED]}*")
        return "\n".join(lines)

    def count(self) -> int:
        return len(self._load_all())

    def clear(self) -> int:
        """Delete all tasks. Returns count deleted."""
        tasks = self._load_all()
        n = len(tasks)
        self._save_all([])
        return n

    def __len__(self) -> int:
        return self.count()

    def __repr__(self) -> str:
        return f"TaskQueue(path={self._root!r}, store={self.store!r})"
