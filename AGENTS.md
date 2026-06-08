# Agent Notes

This repo is maintained through small, numbered release-readiness tasks.

## Start Here

At the start of a continuation session, read:

- `CLAUDE.md`
- `AGENTS.md`
- `memory.md`
- `docs/tasks/backlog.md`
- `git status --short --branch`
- `git log --oneline --decorate -12`

If one of those files is missing, note it in `memory.md` and treat restoring the
handoff trail as valid release-readiness cleanup.

## Task Flow

- Continue from the highest `TASK-###` in `docs/tasks/backlog.md`; if a handoff
  prompt supplies a newer completed task number than the checkout has, use that
  prompt as the numbering source and make the next task one higher.
- Before substantial edits, add a WIP entry to `memory.md` with the task id,
  goal, starting point, planned changes, and pending verification.
- Keep changes narrowly scoped and release-oriented unless the user asks for a
  feature.
- Update `docs/tasks/backlog.md` and `memory.md` before committing.
- Commit coherent passing work with `[TASK-###]` in the subject.

## Local Checks

Use Python 3.12. The project pins runtime metadata to `>=3.12,<3.13` because the
current IRC dependency stack is not Python 3.13 compatible.

Preferred checks:

```powershell
.\.venv\Scripts\python -m pytest -q -o cache_dir=.tmp\pytest-cache --basetemp=.tmp\pytest-basetemp
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mlb_irc_bot --dry-run
```

For IRC-visible output or live alert changes, prefer real `#mlbtest` verification
after local checks and before deployment claims.
