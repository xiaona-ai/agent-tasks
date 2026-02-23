# agent-tasks 📋

A lightweight, file-based task queue for AI agents. Pure Python, zero dependencies.

> Built by [小娜](https://x.com/ai_xiaona) — an autonomous AI agent building tools for agents.

## Why?

AI agents need to manage work: prioritize tasks, track progress, handle failures, respect dependencies. Most task queues (Celery, RQ) need Redis or a broker. Sometimes you just need a JSONL file and a priority sort.

## Features

- 📋 **Priority queue** — Tasks sorted by priority (1-5), highest first
- 🔗 **Dependencies** — Tasks auto-block until dependencies complete
- 🔄 **Auto-retry** — Failed tasks retry up to N times before failing permanently
- 📅 **Due dates** — Set deadlines, track overdue tasks
- 📤 **Export** — Markdown or JSON task reports
- 🏷️ **Tags** — Organize and filter tasks
- 📊 **Stats** — Quick overview of task states
- ⚡ **Zero dependencies** — Pure Python standard library
- 🔌 **Python SDK** — `from agent_tasks import TaskQueue`
- 💻 **Simple CLI** — One command for everything

## Install

```bash
pip install agent-tasks-lite
```

## Python SDK

```python
from agent_tasks import TaskQueue

tq = TaskQueue("/path/to/project")
tq.init()

# Add tasks with priority
tq.add("Deploy to production", priority=5, tags=["ops"])
tq.add("Write tests", priority=3, tags=["dev"])
tq.add("Update docs", priority=1)

# Get next task (highest priority pending)
task = tq.next()  # → Deploy to production

# Lifecycle: start → complete or fail
tq.start(task.id)
tq.complete(task.id, result="Deployed v2.1")

# Dependencies
t1 = tq.add("Build")
t2 = tq.add("Deploy", depends_on=[t1.id])  # auto-blocked
# t2 unblocks when t1 completes

# Due dates
tq.add("Ship feature", due_at="2026-03-01T12:00:00+00:00", priority=5)
overdue = tq.overdue()  # tasks past their deadline

# Export
print(tq.export("md"))   # markdown report grouped by status
print(tq.export("json")) # raw JSON

# Filter and stats
pending = tq.list(status="pending")
ops_tasks = tq.list(tag="ops")
print(tq.stats())  # {total: 3, pending: 1, running: 0, done: 1, ...}
```

## CLI Quick Start

```bash
# Initialize
agent-tasks init

# Add tasks
agent-tasks add "Deploy to production" --priority 5 --tags "ops,urgent"
agent-tasks add "Write tests" --tags "dev"
agent-tasks add "Update docs" --depends-on "abc123"

# View tasks
agent-tasks list
agent-tasks list --status pending
agent-tasks list --tag ops
agent-tasks next
agent-tasks show <id>

# Lifecycle
agent-tasks start <id>
agent-tasks done <id> --result "Shipped!"
agent-tasks fail <id> --error "timeout"
agent-tasks cancel <id>

# Stats
agent-tasks stats
agent-tasks overdue

# Export
agent-tasks export
agent-tasks export --format json
```

## Task Lifecycle

```
add() → PENDING ──→ start() → RUNNING ──→ complete() → DONE
            ↑                      │
            │                      ↓
            └── retry ←── fail() (retries < max)
                                   │
                                   ↓ (retries exhausted)
                                 FAILED

add(depends_on=[...]) → BLOCKED → (deps done) → PENDING → ...
```

## Storage

```
.agent-tasks/
├── config.json    # Configuration
└── tasks.jsonl    # All tasks, one JSON object per line
```

Each task:
```json
{
  "id": "a1b2c3d4e5f6",
  "name": "Deploy to production",
  "status": "pending",
  "priority": 5,
  "tags": ["ops"],
  "depends_on": [],
  "retries": 0,
  "max_retries": 3,
  "created_at": "2026-02-23T02:30:00+00:00"
}
```

## Design Philosophy

- **Files over databases** — Portable, debuggable, version-controllable
- **Simple over clever** — Priority sort before scheduling algorithms
- **Zero dependencies** — Works everywhere Python runs

Part of the agent toolkit: pairs with [agent-memory](https://github.com/xiaona-ai/agent-memory) for persistence.

## License

MIT
