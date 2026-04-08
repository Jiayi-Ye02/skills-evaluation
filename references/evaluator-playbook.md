# Evaluator Playbook

This playbook is the concrete OpenClaw-native execution procedure for running `skill-eval`.

Use it together with:

- `skill-eval/SKILL.md`
- `skill-eval/references/openclaw-runner-design.md`
- `agentic-evals/AGENT.md`

## End-to-End Flow

### 1. Resolve scope

- Determine repo path
- Resolve `target_id`
- Resolve selected suites or cases
- Read the target, suites, and cases before execution

### 2. Initialize run

- Create `runs/<run_id>/`
- Write `manifest.json`
- Create empty:
  - `case-artifacts/`
  - `case-results/`
  - `transcript.md`

Recommended `manifest.json` extra fields:

- `selected_case_ids`
- `runtime_notes`
- `tool_limits`

### 3. For each case

#### 3A. Create attempt workspace

Run:

```bash
bash skills/skill-eval/scripts/create_case_workspace.sh "<source_workspace>" "<case_workspace_root>" "<case_id>" --target "<target_id>"
```

Save the returned path as the attempt `workspace_root`.

#### 3B. Apply setup

- Reproduce case setup only inside `workspace_root`
- If the setup cannot be applied faithfully, record the mismatch immediately
- Do not pull missing fixtures from outside the allowed workspace snapshot

#### 3C. Spawn execution subject

Call `sessions_spawn` with roughly:

- `runtime: "subagent"`
- `mode: "run"`
- `cwd: workspace_root`
- `agentId: "main"` unless a different subagent id is explicitly required
- `task: <spawned-subagent prompt>`
- `timeoutSeconds`: set per suite size

The spawned-subagent prompt should require consultation of the local target skill materials, not merely allow it. When the target skill instructions and relevant local reference docs exist inside the case workspace, require the child to consult them before answering.

Record:

- `childSessionKey`
- any returned label
- spawn time

#### 3D. Wait

If completion is not immediate:

- use `sessions_yield` to end the current turn and wait for the completion push
- on the resumed turn, continue with `sessions_history`

Avoid polling `sessions_list` in a loop.

#### 3E. Retrieve evidence

Fetch child history:

- `sessions_history(sessionKey=<childSessionKey>, includeTools=true)`

Write the raw result to:

- `case-artifacts/<case_id>/accepted-session.json`

Extract the final assistant answer and write:

- `case-artifacts/<case_id>/final-answer.txt`

#### 3F. Validate isolation

From session history, inspect:

- file reads
- file writes
- shell commands
- observed cwd values

If reliable evidence shows access outside `workspace_root`:

- append a note to `transcript.md`
- create a brand-new attempt workspace
- rerun the case once

If isolation is still not reliable after retry:

- mark the case `blocked`

#### 3G. Judge assertions

For each required assertion:

- mark `pass` only when the accepted evidence clearly supports it
- mark `fail` when the accepted evidence clearly violates it
- mark `blocked` when evidence is too weak to decide

For forbidden assertions:

- mark `fail` when a forbidden signal is present
- otherwise leave them satisfied implicitly or document them in notes if useful

Evidence references should prefer:

- `accepted-session.json#msg-<n>`
- `final-answer.txt#L<line>`

#### 3H. Write case result

Write `case-results/<case_id>.json` with:

- `case_id`
- `workspace_root`
- `thread_id` or `null`
- `session_path` as `openclaw-session://<childSessionKey>`
- `status`
- `blocked_reason`
- `assertions`
- `notes`
- `suggested_fix_files`

#### 3I. Append transcript

Append a human-readable section to `transcript.md` including:

- case id
- workspace root
- session key
- summarized evidence timeline
- final answer excerpt

### 4. Write report

`report.md` must contain exactly:

1. `Run Summary`
2. `Case Table`
3. `Failures`
4. `Suggested Next Fixes`

Keep the fixes short and point to real files.

## Assertion Mapping Tips

### Consultation assertions

Look for:

- `read`
- `exec` outputs containing file contents
- any tool result that clearly names the consulted file

### Ordering assertions

Compare message order within `accepted-session.json`.
If the history shape does not preserve enough ordering detail, mark the assertion `blocked`.

### Final-answer assertions

Judge from `final-answer.txt` first.
Use session history only to clarify ambiguity.

## Runtime Failure Policy

### `sessions_spawn` failure

Stop immediately and report the failure reason.
This is an evaluator-environment failure, not a skill failure.

### `sessions_history` missing or coarse

Mark affected cases `blocked`.
Do not invent evidence.

### Pairing / gateway issues

Write explicit environment notes in `manifest.json` and `report.md`.
If no dynamic cases can be executed, stop and report the environment blocker.

## Minimal Operator Checklist

Before running a target:

- repo present
- target/suites/cases read
- case workspace helper works
- `sessions_spawn` available
- `sessions_history` available

If any of these are false, fix the environment before trusting the evaluation.
