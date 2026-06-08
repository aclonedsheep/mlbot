# Claude Handoff

Follow the shared repo workflow in `AGENTS.md`.

Release-readiness continuations should:

- Read `memory.md`, `docs/tasks/backlog.md`, and recent git history first.
- Record WIP in `memory.md` before substantial edits.
- Keep task numbers monotonic with `[TASK-###]` commit subjects.
- Run the relevant Python 3.12 checks before committing.
- Finish by updating `memory.md` with the commit hash and a concise resume prompt
  for the next session.
