---
name: skill-eval
description: |
  Run the agentic evaluation repo for a target skill. Use when
  asked to execute repo-defined suites, collect evidence, write per-case
  results, and produce a short audit report for the target skill.
---

# Skill Eval

Use this skill only for the evaluator flow.

This skill does not define test truth.
The test repo defines the cases, assertions, and report contract.

This skill is a dynamic black-box evaluator.
Do not replace execution with a static read-through when a fresh-agent run is possible.

## Required Inputs

- optional path to the test repo
- `target_id`, or permission to use the repo default
- selected suite names, or permission to use the defaults
- path or revision of the target skill if the user provided one

If the user does not provide a test repo path, the evaluator must first look for a local
`agentic-evals` folder in the current workspace and clone the default repo only if that
folder is missing.

Default test repo:

- folder name: `agentic-evals`
- clone URL: `https://github.com/Jiayi-Ye02/agentic-evals.git`

## Non-Negotiables

- Before any test evaluation, check whether a local `agentic-evals` folder already exists.
- If the test repo folder does not exist, clone `https://github.com/Jiayi-Ye02/agentic-evals.git` before doing anything else.
- Read `agentic-evals/docs/test-protocol.md` before running any case.
- Resolve `target_id` before selecting cases. Use the user-provided `target_id` when available. Otherwise, use the repo default target, which is currently `voice-ai-integration`.
- Read `agentic-evals/targets/<target_id>/target.yaml` before selecting cases.
- Read the selected suite files before executing cases.
- Create one brand-new isolated workspace for every case attempt under a temp parent directory. Never execute a case in the user's main workspace.
- Execute each case by running a fresh Codex sub-agent on the case prompt with `spawn_agent` and `fork_context: false`.
- Do not use `codex exec`, terminal wrappers, or any other fallback executor for case execution.
- If `spawn_agent` is unavailable or agent creation fails, stop the evaluation immediately and report the failure reason instead of continuing.
- After each successful `spawn_agent`, immediately report the sub-agent nickname in the main thread so the user can find and open it in the Codex app. If no nickname is available, report the agent id.
- Send the case `input.user_prompt` to the fresh agent verbatim. Do not paraphrase the user request.
- Do not leak the case title, assertions, expected route, intended answer, or your prior judgment into the fresh-agent prompt.
- The fresh sub-agent is the execution subject, not the judge. Do not ask it to grade the case, interpret the assertions, or decide pass/fail.
- Do not invent pass or fail rules outside the repo.
- Do not mark `pass` from a generic self-report alone.
- Do not mark `pass` from a static source review alone when a fresh-agent run was available.
- Treat any attempt that reads or executes outside its case workspace as invalid evidence. Do not judge the case from that attempt.
- If a case cannot be judged reliably, mark it `blocked`.
- On clone failure, report the error and stop. Do not silently continue without the test repo.

## Workflow

### Step 1: Acquire the test repo

Resolve the test repo path in this order:

1. If the user provided a repo path, use it.
2. Otherwise, look for a local folder named `agentic-evals` in the current workspace.
3. If that folder does not exist, run:

```bash
git clone --depth 1 https://github.com/Jiayi-Ye02/agentic-evals.git
```

Do not continue until the repo is present locally or the clone has failed.

### Step 2: Load the repo contract

Read:

- `agentic-evals/docs/test-protocol.md`
- `agentic-evals/targets/<target_id>/target.yaml`
- each selected suite file
- each case file referenced by those suites

Do not start execution before the case set is known.

### Step 3: Create a run directory

Create:

```text
runs/<run_id>/
├── manifest.json
├── transcript.md
├── case-results/
└── report.md
```

`manifest.json` should include:

- `run_id`
- `target_id`
- `suite_ids`
- `target_skill_path`
- `started_at`
- `model` if available
- `workspace_mode` with value `isolated-per-case`
- `case_workspace_root` for the parent temp directory used for per-case workspaces
- `notes` when the environment diverges from case setup or trace collection has limits

### Step 3A: Create a fresh case workspace for every attempt

Before executing a case, create a temp parent directory and then create a brand-new
workspace for that case attempt.

Use the helper script:

```bash
bash skill-eval/scripts/create_case_workspace.sh "<source_workspace>" "<case_workspace_root>" "<case_id>" --target "<target_id>"
```

The script returns the absolute path to the new attempt workspace.
`<source_workspace>` must be the shared workspace root that contains sibling
`agentic-evals/` and `.agents/` directories.
By default it should copy only the target skill materials needed for execution:

- the target `entry_skill`
- the target `roots`
- any explicit extra relative paths passed as additional arguments when a case needs local fixtures

The case workspace must not include repo evaluation materials such as `targets/`, `docs/`, `runs/`, or the evaluator skill itself unless a case explicitly requires them.

Rules:

- Run this once before the first attempt of every case.
- Run it again before every retry of the same case. Retries must not reuse the prior attempt workspace.
- Apply case `setup` only inside the returned workspace.
- Treat the returned workspace as a minimal target-skill sandbox, not a full clone of the eval repo.
- Resolve repo-defined files from `<source_workspace>/agentic-evals/` and target skill files from `<source_workspace>/.agents/`.
- Record the parent temp directory as `case_workspace_root` in `manifest.json`.
- Record the exact attempt workspace used for judgment as `workspace_root` in `case-results/<case_id>.json`.

### Step 4: Execute each case dynamically

For every case:

1. Create a fresh isolated workspace for that case attempt under `case_workspace_root`.
2. Apply the case setup as far as the environment allows, but only inside that attempt workspace.
3. Start a fresh sub-agent with `spawn_agent` and `fork_context: false`.
   - Do not substitute `codex exec` or any other fresh-session mechanism.
   - If `spawn_agent` fails, stop the run immediately and record the failure reason.
   - After the spawn succeeds, immediately tell the user the sub-agent nickname in the main thread so they can click `Open` in the Codex app.
4. Give the fresh agent only the task-local context it needs:
   - workspace root
   - the case `input.user_prompt`
   - a requirement to answer naturally as if serving the user
   - a requirement to return a compact execution trace and final answer only
5. Tell the fresh agent to return its final message using exactly this shape:

```text
TRACE_FILES_READ:
- one absolute path per line for each file actually read; if none, write "- none"
TRACE_COMMANDS_EXECUTED:
- one shell command per line for each command actually executed, including failed commands; if none, write "- none"
FINAL_ANSWER:
- then the exact user-facing answer
```

6. Do not tell the fresh agent which files it is expected to read.
7. Do not tell the fresh agent what the correct answer should be.
8. Validate the returned trace before judging:
   - every file under `TRACE_FILES_READ` must be inside the attempt workspace
   - every command under `TRACE_COMMANDS_EXECUTED` must operate inside the attempt workspace
   - if the trace touches the user's main workspace or any other path outside the attempt workspace, invalidate that attempt, append the mismatch to `transcript.md`, create a brand-new attempt workspace, and rerun the case once
   - if you still cannot prove isolation after the retry, mark the case `blocked` with `blocked_reason: "environment"`
9. Append the accepted fresh-agent trace and final answer to `transcript.md`.
10. Judge each assertion in the main evaluator from the accepted trace and answer.
11. Write `case-results/<case_id>.json`.

Each case result must include:

- `case_id`
- `workspace_root`
- `status`
- `blocked_reason`
- `assertions`
- `notes`
- `suggested_fix_files`

### Step 4A: Fresh-agent prompt template

Use a prompt equivalent to this shape:

```text
You are a fresh Codex agent running in the workspace <workspace>.

Task: answer this user request naturally, using the local workspace as needed:
"<case input.user_prompt>"

Requirements:
- Work as a normal Codex agent would for a real user request.
- Use the target skill docs if relevant.
- Treat `<workspace>` as your only workspace for this task.
- Start from `<workspace>` and keep all file reads, writes, and shell commands inside it.
- If something you need is missing inside `<workspace>`, say so from that workspace instead of reaching outside it.
- Do not mention that you are being evaluated.
- Before your final answer, include a compact machine-readable trace section with exactly these headings:
TRACE_FILES_READ:
- one absolute path per line for each file you actually read; if none, write - none
TRACE_COMMANDS_EXECUTED:
- one shell command per line for each command you actually executed, including failed commands; if none, write - none
FINAL_ANSWER:
- then give the exact answer you would send to the user

Be accurate: list only files you actually read and commands you actually executed.
```

Keep the prompt minimal.
Do not include the case assertions in the fresh-agent prompt.

### Step 4AA: Required executor

The evaluator must start fresh sub-agents directly with `spawn_agent`.

Why:

- it creates a genuinely fresh agent context
- it makes the agent visible in the Codex app as a background agent the user can open
- it keeps the trace inside the current evaluation thread
- it is easier to capture the returned trace and final answer deterministically

Do not treat `codex exec` as a fallback executor.
If `spawn_agent` fails or the environment does not allow it, stop the evaluation immediately and report the failure reason. Do not continue the case with any substitute executor.

### Step 4B: Environment mismatch handling

Case `setup` is part of the contract.
Do not silently replace it with whatever the current workspace happens to contain.

If the environment does not match the case setup:

- Record the mismatch in `manifest.json` and `transcript.md`
- Judge only the assertions that remain reliable
- Mark an assertion `blocked` when the mismatch prevents reliable judgment
- Propagate the case to `blocked` unless a required assertion already failed independently
- Do not repair the mismatch by reading from the user's main workspace or any path outside the case workspace

Examples:

- case says `docs_index_present: true`, but the real workspace is missing `references/docs.txt`
- case expects restricted networking behavior, but the current runtime cannot simulate that condition
- case setup would require mutating protected files that the evaluator cannot safely write

### Step 5: Write the report

`report.md` must contain exactly:

1. `Run Summary`
2. `Case Table`
3. `Failures`
4. `Suggested Next Fixes`

Keep `Suggested Next Fixes` to at most 3 items and point to real files.

## Evidence Rules

Prefer:

- fresh-agent file reads
- fresh-agent commands executed
- ordering between reads and commands
- specific fresh-agent final outputs
- trace paths that stay entirely inside the accepted `workspace_root`

Use natural-language assertion entries for every case requirement.

Cases may include:

- optional `assert.summary`
- optional per-assertion `description`
- assertion entries with `pass_criteria`, optional `fail_signals`, and optional `evidence_scope`

Treat those human-readable fields as part of the repo-defined contract. Use them to guide the evaluator's judgment, but do not pass them to the fresh execution sub-agent.

If the trace does not support a reliable judgment, mark that assertion `blocked` and propagate the case to `blocked` unless a required assertion already failed.

For each assertion:

- judge from the accepted trace and final answer. Pass only when the pass criteria are satisfied and no fail signal is present. If the evidence is mixed or insufficient, mark it `blocked` unless the failure is independently clear from the transcript.
- when `evidence_scope` points to `trace`, prefer concrete trace evidence such as file reads, command attempts, or ordering
- when `evidence_scope` points to `final_answer`, prefer explicit answer content and route commitment
- when `evidence_scope` includes both, reconcile the trace and final answer together instead of treating one in isolation

Isolation validation is mandatory:

- An attempt is invalid if any traced file path is outside the accepted `workspace_root`.
- An attempt is invalid if any traced command clearly targets the user's source workspace or another path outside `workspace_root`.
- Invalid attempts can explain `notes`, but they cannot satisfy assertions or justify a `pass`.
- If all attempts for a case are invalid, mark the case `blocked`.

Static reads by the evaluator are allowed for:

- loading the repo contract
- understanding the case
- understanding the target skill after the fresh-agent run
- mapping failures to likely fix files

Static reads by the evaluator are not enough on their own to mark a dynamic case `pass` when a fresh-agent run was available.
