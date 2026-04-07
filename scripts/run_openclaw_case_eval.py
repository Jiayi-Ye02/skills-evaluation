#!/usr/bin/env python3
"""Minimal OpenClaw-native runner scaffold for skill-eval.

This script is intentionally conservative:
- creates per-case isolated workspaces via create_case_workspace.sh
- writes a manifest skeleton and per-case placeholders
- prepares prompts meant for sessions_spawn + sessions_history orchestration

It does NOT call OpenClaw tools directly because tool calls belong in the agent runtime,
not inside a detached local script. The evaluator agent should use this file as a helper
for deterministic filesystem setup and artifact shaping, then perform the actual spawned
execution with OpenClaw tools.
"""

from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
TARGET_ID = sys.argv[2] if len(sys.argv) > 2 else 'voice-ai-integration'
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
RUN_DIR = ROOT / 'agentic-evals' / 'runs' / RUN_ID
CASE_ROOT = Path(tempfile.mkdtemp(prefix=f'openclaw-skill-eval-{TARGET_ID}-'))


def sh(args):
    p = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f'command failed: {args}\nstdout={p.stdout}\nstderr={p.stderr}')
    return p.stdout.strip()


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> int:
    target_yaml = ROOT / 'agentic-evals' / 'targets' / TARGET_ID / 'target.yaml'
    if not target_yaml.exists():
        raise SystemExit(f'missing target config: {target_yaml}')

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / 'case-artifacts').mkdir(exist_ok=True)
    (RUN_DIR / 'case-results').mkdir(exist_ok=True)

    manifest = {
        'run_id': RUN_ID,
        'target_id': TARGET_ID,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'workspace_mode': 'isolated-per-case',
        'case_workspace_root': str(CASE_ROOT),
        'evidence_mode': 'openclaw-session-history',
        'notes': [
            'Use this scaffold with OpenClaw tool orchestration: sessions_spawn, sessions_history, sessions_yield.'
        ],
    }
    (RUN_DIR / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps({
        'run_id': RUN_ID,
        'run_dir': str(RUN_DIR),
        'case_workspace_root': str(CASE_ROOT),
        'next_step': 'For each selected case, call create_case_workspace.sh then execute via sessions_spawn and inspect via sessions_history.'
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
