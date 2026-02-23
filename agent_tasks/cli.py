"""CLI entry point for agent-tasks."""
import argparse
import json
import sys
from .task_queue import TaskQueue, PENDING, RUNNING, DONE, FAILED, BLOCKED


def main():
    parser = argparse.ArgumentParser(
        prog="agent-tasks",
        description="Lightweight task queue for AI agents",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialize .agent-tasks/ in current directory")

    p_add = sub.add_parser("add", help="Add a task")
    p_add.add_argument("name", help="Task name")
    p_add.add_argument("--desc", default="", help="Description")
    p_add.add_argument("--priority", type=int, default=None, choices=range(1, 6))
    p_add.add_argument("--tags", default="", help="Comma-separated tags")
    p_add.add_argument("--depends-on", default="", help="Comma-separated task IDs")

    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--status", choices=[PENDING, RUNNING, DONE, FAILED, BLOCKED])
    p_list.add_argument("--tag", help="Filter by tag")
    p_list.add_argument("-n", type=int, default=50, help="Max results")

    sub.add_parser("next", help="Show the highest-priority pending task")

    p_start = sub.add_parser("start", help="Start a task")
    p_start.add_argument("id", help="Task ID")

    p_done = sub.add_parser("done", help="Complete a task")
    p_done.add_argument("id", help="Task ID")
    p_done.add_argument("--result", default=None, help="Result message")

    p_fail = sub.add_parser("fail", help="Fail a task")
    p_fail.add_argument("id", help="Task ID")
    p_fail.add_argument("--error", default=None, help="Error message")

    p_cancel = sub.add_parser("cancel", help="Cancel a task")
    p_cancel.add_argument("id", help="Task ID")

    p_delete = sub.add_parser("delete", help="Delete a task")
    p_delete.add_argument("id", help="Task ID")
    p_delete.add_argument("--force", "-f", action="store_true")

    p_show = sub.add_parser("show", help="Show task details")
    p_show.add_argument("id", help="Task ID")

    sub.add_parser("stats", help="Show task statistics")

    args = parser.parse_args()
    tq = TaskQueue()

    if args.command == "init":
        d = tq.init()
        print(f"Initialized agent-tasks in {d}")

    elif args.command == "add":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        deps = [d.strip() for d in args.depends_on.split(",") if d.strip()] if args.depends_on else []
        task = tq.add(args.name, description=args.desc, priority=args.priority, tags=tags, depends_on=deps)
        print(f"Added task {task.id}: {task.name} [{task.status}]")

    elif args.command == "list":
        tasks = tq.list(status=args.status, tag=args.tag, limit=args.n)
        _print_tasks(tasks)

    elif args.command == "next":
        task = tq.next()
        if task:
            _print_task_detail(task)
        else:
            print("No pending tasks.")

    elif args.command == "start":
        task = tq.start(args.id)
        if task:
            print(f"Started task {task.id}: {task.name}")
        else:
            print(f"Cannot start task {args.id} (not found or not pending)")
            sys.exit(1)

    elif args.command == "done":
        task = tq.complete(args.id, result=args.result)
        if task:
            print(f"Completed task {task.id}: {task.name}")
        else:
            print(f"Cannot complete task {args.id} (not found or not running)")
            sys.exit(1)

    elif args.command == "fail":
        task = tq.fail(args.id, error=args.error)
        if task:
            if task.status == PENDING:
                print(f"Task {task.id} failed, retrying ({task.retries}/{task.max_retries})")
            else:
                print(f"Task {task.id} failed permanently: {task.error}")
        else:
            print(f"Cannot fail task {args.id}")
            sys.exit(1)

    elif args.command == "cancel":
        task = tq.cancel(args.id)
        if task:
            print(f"Cancelled task {task.id}")
        else:
            print(f"Cannot cancel task {args.id}")
            sys.exit(1)

    elif args.command == "delete":
        if not args.force:
            confirm = input(f"Delete task {args.id}? [y/N] ").strip().lower()
            if confirm != "y":
                print("Cancelled.")
                return
        if tq.delete(args.id):
            print(f"Deleted task {args.id}")
        else:
            print(f"Task {args.id} not found")
            sys.exit(1)

    elif args.command == "show":
        task = tq.get(args.id)
        if task:
            _print_task_detail(task)
        else:
            print(f"Task {args.id} not found")
            sys.exit(1)

    elif args.command == "stats":
        s = tq.stats()
        print(f"Total: {s['total']}")
        print(f"  Pending: {s[PENDING]}  Running: {s[RUNNING]}  "
              f"Done: {s[DONE]}  Failed: {s[FAILED]}  Blocked: {s[BLOCKED]}")

    else:
        parser.print_help()


STATUS_ICONS = {
    PENDING: "⏳",
    RUNNING: "🔄",
    DONE: "✅",
    FAILED: "❌",
    BLOCKED: "🔒",
}


def _print_tasks(tasks):
    if not tasks:
        print("No tasks found.")
        return
    for t in tasks:
        icon = STATUS_ICONS.get(t.status, "?")
        tags = f" [{', '.join(t.tags)}]" if t.tags else ""
        pri = f" P{t.priority}" if t.priority != 3 else ""
        print(f"{icon} [{t.id}]{pri}{tags} {t.name}")


def _print_task_detail(task):
    icon = STATUS_ICONS.get(task.status, "?")
    print(f"{icon} {task.name}")
    print(f"  ID: {task.id}")
    print(f"  Status: {task.status} | Priority: {task.priority}")
    if task.description:
        print(f"  Description: {task.description}")
    if task.tags:
        print(f"  Tags: {', '.join(task.tags)}")
    if task.depends_on:
        print(f"  Depends on: {', '.join(task.depends_on)}")
    if task.subtasks:
        print(f"  Subtasks: {', '.join(task.subtasks)}")
    print(f"  Created: {task.created_at[:19]}")
    if task.started_at:
        print(f"  Started: {task.started_at[:19]}")
    if task.completed_at:
        print(f"  Completed: {task.completed_at[:19]}")
    if task.result:
        print(f"  Result: {task.result}")
    if task.error:
        print(f"  Error: {task.error}")
    print(f"  Retries: {task.retries}/{task.max_retries}")


if __name__ == "__main__":
    main()
