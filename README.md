# skills-evaluation

`skill-eval` skill is the runner for the `agentic-evals` protocol.
It does not define what is correct to test. The `agentic-evals` repo defines targets,
suites, cases, assertions, and output format.

If you only remember one thing, remember this:

`agentic-evals` defines what to test, `skill-eval` runs the test, and a fresh Codex
sub-agent is the thing being judged.

## Skill Repo Layout

```text
README.md
agentic-evals/
├── AGENT.md
├── docs/
└── targets/
skill-eval/
├── SKILL.md
└── scripts/
```

## Install

Install `skill-eval` with:

```bash
npx skills add Jiayi-Ye02/skills-evaluation --skill skill-eval
```

- `skill-eval`: runs the `agentic-evals` evaluation repo against a target skill,
  collects per-case results, and writes a short report

It now supports:

- `single-run`: one target skill version
- `ab-urls`: two target skill versions supplied as GitHub HTTP URLs

## Framework Structure

In a normal run there are 4 separate roles:

1. `agentic-evals/`
   The test repo and source of truth for targets, suites, cases, assertions, and report contract.
2. `skill-eval`
   The evaluator skill that executes the repo-defined protocol.
3. target skill
   The skill under test, for example `.agents/skills/<target-skill>/`.
4. fresh Codex sub-agent
   The execution subject that receives the case prompt and produces the trace and answer to judge.

That separation matters:

- the test repo decides pass/fail rules
- the evaluator runs the process
- the fresh sub-agent is what actually gets tested

### Expected Workspace Layout

Your workspace will normally look like this:

```text
<workspace>/
├── .agents/
│   └── skills/
│       └── <target-skill>/
├── agentic-evals/
└── skill-eval/
```

## Requirements

- Codex with `spawn_agent` available
- `git`
- `bash`
- local target skill files
- local `agentic-evals` repo, or network access so it can be cloned if missing

## Quickstart

Once you have workspace prepared, ask Codex in plain language to use `skill-eval`. For example::

Single case:

```text
Use skill-eval to test target_id=voice-ai-integration, case_id=convoai-phase1-only-before-gates.
```

Single suite:

```text
Use skill-eval to test target_id=voice-ai-integration, suite=source-order.
```

Default target with default suites:

```text
Use skill-eval to run the default target with its default suites.
```

Chinese example:

```text
用 skill-eval 去测试 target_id=voice-ai-integration，测试范围 case_id=convoai-phase1-only-before-gates
```

A/B URL mode:

```text
Use skill-eval in ab-urls mode for target_id=voice-ai-integration.
variant_a_url=https://github.com/org/repo/tree/main/.agents/skills/voice-ai-integration
variant_b_url=https://github.com/org/repo/tree/rewrite/.agents/skills/voice-ai-integration
case_id=auth-prefers-rtc-token
```

Chinese A/B example:

```text
用 skill-eval 以 ab-urls 模式测试 target_id=voice-ai-integration。
variant_a_url=https://github.com/org/repo/tree/main/.agents/skills/voice-ai-integration
variant_b_url=https://github.com/org/repo/tree/rewrite/.agents/skills/voice-ai-integration
suite_id=convoai-api
```

## 5-Minute Mental Model

When you ask Codex to run an eval, the expected flow is:

1. Codex uses `skill-eval`.
2. `skill-eval` reads `agentic-evals/AGENT.md` and `agentic-evals/docs/session-evidence.md`.
3. It resolves the target from `agentic-evals/targets/<target_id>/target.yaml`.
4. It reads the selected suite and case files from `agentic-evals/targets/<target_id>/`.
5. It creates a new run directory under `agentic-evals/runs/<run_id>/`.
6. For each case, it creates a brand-new isolated temp workspace.
7. It spawns a fresh sub-agent for that case.
8. The evaluator copies the accepted child session and extracts the final user-facing answer.
9. The evaluator validates isolation and judges the assertions from the accepted child session evidence.
10. The evaluator writes final artifacts under `agentic-evals/runs/<run_id>/`.

In `ab-urls` mode, steps 6-10 happen twice, once for A and once for B, and then the evaluator writes a parent comparison report.

## What To Expect During A Run

During execution, the evaluator should:

- report which target, suite, or case it is using
- create a fresh case workspace under a temp directory
- spawn a fresh sub-agent for the case
- tell you the sub-agent nickname or id so you can open it in the Codex app
- write artifacts under `agentic-evals/runs/<run_id>/`

The evaluator should not:

- run the case directly in your main workspace
- silently replace the fresh sub-agent with a fallback executor
- mark `pass` from a vague self-report alone

## Run Artifacts

Every run should create:

```text
agentic-evals/runs/<run_id>/
├── manifest.json
├── case-artifacts/
├── transcript.md
├── case-results/
└── report.md
```

- `report.md`: short summary and next actions
- `case-results/<case_id>.json`: official status for one case
- `transcript.md`: readable transcript rendered from accepted child session evidence
- `manifest.json`: run metadata, workspace mode, and environment mismatch notes

In `ab-urls` mode the parent run additionally contains:

```text
agentic-evals/runs/<ab_run_id>/
├── manifest.json
├── variants/
│   ├── A/
│   │   ├── source-manifest.json
│   │   └── run/
│   └── B/
│       ├── source-manifest.json
│       └── run/
├── comparison.json
└── report.md
```

Helper scripts for this mode:

- `skill-eval/scripts/parse_github_skill_url.py`
- `skill-eval/scripts/prepare_variant_source_workspace.py`
- `skill-eval/scripts/init_ab_run.py`
- `skill-eval/scripts/render_ab_report.py`
