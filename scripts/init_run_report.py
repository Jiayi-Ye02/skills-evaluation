#!/usr/bin/env python3
"""Initialize a report.md file with the exact required section headings."""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: init_run_report.py <report-path>')

p = Path(sys.argv[1]).resolve()
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(
    '# Run Summary\n\n'
    '## Case Table\n\n'
    '## Failures\n\n'
    '## Suggested Next Fixes\n',
    encoding='utf-8'
)
print(str(p))
