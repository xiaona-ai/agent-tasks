# agent-tasks Roadmap

## ✅ v0.1.0 — Core Task Queue (2026-02-23)
- [x] TaskQueue class: add/start/complete/fail/cancel/delete/next/list/stats
- [x] Priority queue (1-5)
- [x] Dependency tracking (blocked → pending on completion)
- [x] Auto-retry on failure
- [x] JSONL file storage, zero dependencies
- [x] CLI with full lifecycle
- [x] 21 tests passing
- [x] GitHub repo + README

## ✅ v0.2.0 — Due Dates & Export (2026-02-23)
- [x] Due dates (due_at parameter + overdue tracking)
- [x] Export (markdown report grouped by status + JSON)
- [x] CLI: --due, export, overdue commands
- [x] GitHub Actions CI (Python 3.8/3.10/3.12)
- [x] 29 tests passing (+8 new)
- [x] Dev.to article

## 🔜 Next
- [ ] Subtask management (parent-child relationships)
- [ ] Recurring tasks (repeat patterns)
- [ ] Integration with agent-memory
