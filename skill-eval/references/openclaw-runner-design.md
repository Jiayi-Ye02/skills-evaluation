# OpenClaw Runner Design for `skill-eval`

This file defines the intended evaluator execution pattern after the repo contract was migrated from Codex-local evidence to OpenClaw-native orchestration.

## Goals

- Run each case in a fresh isolated workspace
- Execute the case with an OpenClaw spawned subagent
- Capture authoritative evidence from `sessions_history`
- Write repo-defined artifacts under `agentic-evals/runs/<run_id>/`
- Keep the evaluator as the judge and the spawned subagent as the execution subject

## Tooling Model

The evaluator should use these OpenClaw tools directly:

- `sessions_spawn` — create a one-shot spawned subagent for each case
- `sessions_history` — fetch accepted session evidence for that child session
- `sessions_yield` — wait for completion when the orchestration spans multiple turns
- `read` / `write` / `edit` — create artifacts and update the run directory
- `exec` — run helper shell scripts such as `create_case_workspace.sh`

Avoid relying on:

- `~/.codex/sessions/`
- `state_5.sqlite`
- Codex-only executor assumptions

## Recommended Per-Case Flow

1. Create attempt workspace
   - Run `bash skills/skill-eval/scripts/create_case_workspace.sh <source_workspace> <case_workspace_root> <case_id> --target <target_id>`
   - Capture the returned absolute attempt workspace path

2. Apply case setup
   - Mutate only files inside the attempt workspace
   - If setup cannot be applied faithfully, record the mismatch in `manifest.json` and `transcript.md`

3. Spawn execution subject
   - Call `sessions_spawn` with:
     - `runtime: "subagent"`
     - `mode: "run"`
     - `cwd: <attempt workspace>`
     - `task: <minimal spawned-subagent prompt>`
   - Capture `childSessionKey`

4. Wait for completion
   - If the spawned session is long-running, call `sessions_yield` and continue on the pushed completion turn
   - Otherwise fetch its history after completion

5. Fetch evidence
   - Call `sessions_history` with `sessionKey: <childSessionKey>`
   - Prefer `includeTools: true`
   - Save the raw history as `case-artifacts/<case_id>/accepted-session.json`

6. Extract accepted final answer
   - Identify the final assistant reply from the child history
   - Save it as `case-artifacts/<case_id>/final-answer.txt`

7. Judge assertions
   - Evaluate required and forbidden checks from the child history and final answer
   - Record evidence as `accepted-session.json#msg-<n>` whenever possible

8. Validate isolation
   - Observed cwd, read paths, write paths, and commands should remain under the attempt workspace
   - If reliable evidence shows outside access, invalidate the attempt and rerun once in a new workspace
   - If reliable isolation still cannot be established, mark the case `blocked`

9. Write outputs
   - `case-results/<case_id>.json`
   - append to `transcript.md`
   - update `report.md`

## Suggested Manifest Notes

When the runtime has important constraints, write them explicitly. Examples:

- `sessions_history available but tool-call granularity limited`
- `pairing required prevented spawned execution`
- `used current-session continuation with sessions_yield for completion wait`

## Prompt Shape

Use a minimal execution prompt like:

```text
You are a fresh OpenClaw sub-agent running in the workspace <workspace>.

Task: answer this user request naturally, using the local workspace as needed:
"<case input.user_prompt>"

Requirements:
- Work as a normal OpenClaw sub-agent would for a real user request.
- Use the target skill docs if relevant.
- Treat <workspace> as your only workspace for this task.
- Start from <workspace> and keep all file reads, writes, and shell commands inside it.
- If something you need is missing inside <workspace>, say so from that workspace instead of reaching outside it.
- Do not mention that you are being evaluated.
- Give the exact answer you would send to the user.
```

## Failure Handling

- If `sessions_spawn` fails: stop the evaluation and report the reason
- If `sessions_history` cannot retrieve the child session: mark the case `blocked` with `blocked_reason: "environment"` or `"insufficient-evidence"` as appropriate
- Do not substitute evaluator guesses for missing dynamic evidence
