# Current Status

`skill-eval` has been migrated at the contract level to OpenClaw-native terminology and evidence flow.

## What is ready

- repo contract updated to use OpenClaw session history as the evidence source
- artifact names normalized to `accepted-session.json`
- OpenClaw runner design documented
- helper scaffold script added for deterministic run-directory initialization

## What still depends on runtime support

A fully automated dynamic evaluation still requires a live runtime where:

- `sessions_spawn` can create fresh subagents successfully
- `sessions_history` returns enough detail to judge reads, commands, ordering, and final answers
- long-running child execution can be awaited cleanly with `sessions_yield`

## Practical meaning

The repo and skill are now aligned with OpenClaw semantics.
The remaining work is mostly runtime execution reliability, not repo-contract mismatch.
