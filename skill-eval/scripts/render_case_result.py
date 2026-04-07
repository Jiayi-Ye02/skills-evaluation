#!/usr/bin/env python3
"""Deterministic helper for writing one case-result JSON file.

This script does not judge the case. It only normalizes output structure so the agent can
pass already-judged data in a stable shape.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit('usage: render_case_result.py <output-path> <input-json-path>')

out_path = Path(sys.argv[1]).resolve()
in_path = Path(sys.argv[2]).resolve()
payload = json.loads(in_path.read_text(encoding='utf-8'))

required = [
    'case_id',
    'workspace_root',
    'session_path',
    'status',
    'blocked_reason',
    'assertions',
    'notes',
    'suggested_fix_files',
]
for key in required:
    if key not in payload:
        raise SystemExit(f'missing required key: {key}')

normalized = {
    'case_id': payload['case_id'],
    'workspace_root': payload['workspace_root'],
    'thread_id': payload.get('thread_id'),
    'session_path': payload['session_path'],
    'status': payload['status'],
    'blocked_reason': payload['blocked_reason'],
    'assertions': payload['assertions'],
    'notes': payload['notes'],
    'suggested_fix_files': payload['suggested_fix_files'],
}

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(str(out_path))
