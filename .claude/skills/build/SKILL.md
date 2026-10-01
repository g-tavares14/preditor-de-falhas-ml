---
name: build
description: Lifecycle shortcut for the implementation lifecycle. Use only when the user explicitly invokes /build.
disable-model-invocation: true
---

# Build

Treat `/build` as an explicit request to implement the next pending task in `tasks/todo.md`, or the task the user names. If the user supplies `auto` or `all`, require an approved specification and plan and a clean baseline, then run the remaining tasks in dependency order. Stop on ambiguity, failed verification, or an irreversible action that lacks authorization.

## Orchestrated mode (default when the agents exist)

When the `implementer` and `reviewer` agents are available (a project set up by `setup-project` has them in `.claude/agents/`), this session is the orchestrator: it delegates, relays, and decides what goes back to the user. It does not write the task's code itself. For each task, one at a time:

1. **Implement.** Call the `implementer` with the task (e.g. "implement T2") plus any context the user added. Give it one task per call, even in `auto`, so each task is reviewed before the next starts.
2. **Stopped?** If the implementer returns `stopped` (a question, a dependency to add, a failed verification, a migration to approve), stop the loop and bring it to the user. The implementer cannot commit, change dependencies, or apply migrations (a plugin hook blocks it); when the user authorizes one of those, run it in this session, then resume the task with the implementer.
3. **Review.** Call the `reviewer` with the task and its diff (`git diff` plus new files, or the file list from the implementer's report).
4. **Fix.** If the review has `blocking` or `important` findings, send them to the implementer; prefer continuing the same implementer (SendMessage) so it keeps the task's context. Review the new diff again. After two fix rounds with findings still open, stop and give the user both reports. Findings the implementer disagrees with, and `suggestion`-only findings, go to the user and do not start another round.
5. **Close.** When the review is `approved` or `approved with suggestions`, mark the task ✅ in `tasks/todo.md`. Commit only if the user asked for it. Never mark a checkpoint: checkpoints belong to the user. In `auto`, stop at every checkpoint unless the request says to go through it.

Report to the user once per stop, not after every call: the task(s) done, the verification evidence, the implementer's review questions, the reviewer's suggestions and decisions for the owner, and anything noted as out of scope. Do not repeat the full agent reports when a summary is enough, and do not claim a check passed unless an agent ran it.

## In-session mode (fallback)

If the agents are not available, implement in this session: read and follow both `../incremental-implementation/SKILL.md` and `../test-driven-development/SKILL.md` in full, with the same stop rules. Tell the user once that the agent-skills plugin's `setup-project` skill installs the agents that add the review loop.
