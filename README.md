# skills-evaluation

Open Agent Skills repository for the `skill-eval` skill.

## Install

List available skills:

```bash
npx skills add Jiayi-Ye02/skills-evaluation --list
```

Install `skill-eval` globally:

```bash
npx skills add Jiayi-Ye02/skills-evaluation --skill skill-eval -g -y
```

After installing, restart Codex to pick up the new skill.

## Included skill

- `skill-eval`: Runs the `agentic-evals` evaluation repo against a target skill, collects case results, and writes a short report.

## Requirements

- Codex with `spawn_agent` available
- `git`
- `bash`
- Network access if `agentic-evals` needs to be cloned

## Repo layout

```text
skill-eval/
  SKILL.md
  scripts/
```
