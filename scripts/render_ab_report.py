#!/usr/bin/env python3
"""Render A/B comparison artifacts from two variant run directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an A/B evaluation comparison report.")
    parser.add_argument("ab_run_dir", help="Top-level A/B run directory")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--variant-a-run-dir", default=None)
    parser.add_argument("--variant-b-run-dir", default=None)
    parser.add_argument("--label-a", default="A")
    parser.add_argument("--label-b", default="B")
    parser.add_argument("--variant-a-url", default="")
    parser.add_argument("--variant-b-url", default="")
    return parser.parse_args()


def load_case_results(run_dir: Path) -> dict[str, dict]:
    case_dir = run_dir / "case-results"
    if not case_dir.is_dir():
        return {}
    results = {}
    for path in sorted(case_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        results[payload["case_id"]] = payload
    return results


def summarize_statuses(results: dict[str, dict]) -> dict[str, int]:
    summary = {"pass": 0, "fail": 0, "blocked": 0}
    for payload in results.values():
        summary[payload["status"]] = summary.get(payload["status"], 0) + 1
    return summary


def assertion_fingerprint(payload: dict | None) -> list[tuple[str, str]]:
    if not payload:
        return []
    pairs = []
    for item in payload.get("assertions", []):
        pairs.append((item.get("summary", ""), item.get("status", "unknown")))
    return sorted(pairs)


def classify_case(case_a: dict | None, case_b: dict | None) -> str:
    if case_a is None or case_b is None:
        return "environment-divergence"

    status_a = case_a["status"]
    status_b = case_b["status"]
    if status_a == "pass" and status_b in {"fail", "blocked"}:
        return "regression"
    if status_a in {"fail", "blocked"} and status_b == "pass":
        return "improvement"
    if status_a == status_b:
        if assertion_fingerprint(case_a) != assertion_fingerprint(case_b):
            return "behavior-change"
        return f"same-{status_a}"
    if "blocked" in {status_a, status_b}:
        return "environment-divergence"
    return "behavior-change"


def first_note(payload: dict | None) -> str:
    if not payload:
        return "Variant did not produce a case result."
    notes = payload.get("notes", [])
    return notes[0] if notes else ""


def collect_case_matrix(results_a: dict[str, dict], results_b: dict[str, dict]) -> list[dict]:
    rows = []
    for case_id in sorted(set(results_a) | set(results_b)):
        case_a = results_a.get(case_id)
        case_b = results_b.get(case_id)
        rows.append(
            {
                "case_id": case_id,
                "status_a": case_a["status"] if case_a else "not-run",
                "status_b": case_b["status"] if case_b else "not-run",
                "comparison": classify_case(case_a, case_b),
                "notes": [first_note(case_a), first_note(case_b)],
            }
        )
    return rows


def build_summary(rows: list[dict]) -> dict[str, int]:
    summary = {
        "cases_total": len(rows),
        "same_pass": 0,
        "same_fail": 0,
        "same_blocked": 0,
        "regressions": 0,
        "improvements": 0,
        "behavior_changes": 0,
        "environment_divergence": 0,
    }
    for row in rows:
        key = row["comparison"]
        if key == "same-pass":
            summary["same_pass"] += 1
        elif key == "same-fail":
            summary["same_fail"] += 1
        elif key == "same-blocked":
            summary["same_blocked"] += 1
        elif key == "regression":
            summary["regressions"] += 1
        elif key == "improvement":
            summary["improvements"] += 1
        elif key == "behavior-change":
            summary["behavior_changes"] += 1
        elif key == "environment-divergence":
            summary["environment_divergence"] += 1
    return summary


def collect_suggested_fix_files(
    rows: list[dict], results_a: dict[str, dict], results_b: dict[str, dict]
) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row["comparison"] not in {"regression", "behavior-change"}:
            continue
        for payload in (results_a.get(row["case_id"]), results_b.get(row["case_id"])):
            if not payload:
                continue
            for path in payload.get("suggested_fix_files", []):
                if path not in seen:
                    seen.add(path)
                    paths.append(path)
                if len(paths) == 3:
                    return paths
    return paths


def write_markdown(
    ab_run_dir: Path,
    rows: list[dict],
    summary: dict[str, int],
    counts_a: dict[str, int],
    counts_b: dict[str, int],
    label_a: str,
    label_b: str,
    url_a: str,
    url_b: str,
    suggested_fix_files: list[str],
) -> None:
    report_path = ab_run_dir / "report.md"
    regressions = [row for row in rows if row["comparison"] == "regression"]
    improvements = [row for row in rows if row["comparison"] == "improvement"]
    lines = [
        "# Comparison Summary",
        "",
        f"- Target comparison: `{label_a}` vs `{label_b}`",
        f"- Cases compared: `{summary['cases_total']}`",
        f"- Regressions: `{summary['regressions']}`",
        f"- Improvements: `{summary['improvements']}`",
        f"- Behavior changes: `{summary['behavior_changes']}`",
        f"- Environment divergence: `{summary['environment_divergence']}`",
        "",
        "## Variant Table",
        "",
        "| Variant | URL | pass | fail | blocked |",
        "| --- | --- | --- | --- | --- |",
        f"| `{label_a}` | `{url_a}` | `{counts_a.get('pass', 0)}` | `{counts_a.get('fail', 0)}` | `{counts_a.get('blocked', 0)}` |",
        f"| `{label_b}` | `{url_b}` | `{counts_b.get('pass', 0)}` | `{counts_b.get('fail', 0)}` | `{counts_b.get('blocked', 0)}` |",
        "",
        "## Case Matrix",
        "",
        "| Case ID | A | B | Comparison |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['case_id']}` | `{row['status_a']}` | `{row['status_b']}` | `{row['comparison']}` |"
        )

    lines.extend(["", "## Regressions", ""])
    if regressions:
        for row in regressions:
            lines.append(
                f"- `{row['case_id']}` regressed from `{row['status_a']}` to `{row['status_b']}`. {row['notes'][0]} {row['notes'][1]}"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "## Improvements", ""])
    if improvements:
        for row in improvements:
            lines.append(
                f"- `{row['case_id']}` improved from `{row['status_a']}` to `{row['status_b']}`. {row['notes'][0]} {row['notes'][1]}"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "## Suggested Next Fixes", ""])
    if suggested_fix_files:
        for path in suggested_fix_files:
            lines.append(f"- `{path}`")
    else:
        lines.append("- No variant-specific fix files were suggested.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    ab_run_dir = Path(args.ab_run_dir).resolve()
    variant_a_run_dir = (
        Path(args.variant_a_run_dir).resolve()
        if args.variant_a_run_dir
        else ab_run_dir / "variants" / args.label_a / "run"
    )
    variant_b_run_dir = (
        Path(args.variant_b_run_dir).resolve()
        if args.variant_b_run_dir
        else ab_run_dir / "variants" / args.label_b / "run"
    )

    results_a = load_case_results(variant_a_run_dir)
    results_b = load_case_results(variant_b_run_dir)
    rows = collect_case_matrix(results_a, results_b)
    summary = build_summary(rows)
    counts_a = summarize_statuses(results_a)
    counts_b = summarize_statuses(results_b)
    suggested_fix_files = collect_suggested_fix_files(rows, results_a, results_b)

    payload = {
        "run_mode": "ab-urls",
        "target_id": args.target_id,
        "variant_a": {
            "label": args.label_a,
            "source_url": args.variant_a_url,
            "run_dir": str(variant_a_run_dir),
        },
        "variant_b": {
            "label": args.label_b,
            "source_url": args.variant_b_url,
            "run_dir": str(variant_b_run_dir),
        },
        "summary": summary,
        "cases": rows,
    }
    comparison_path = ab_run_dir / "comparison.json"
    comparison_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(
        ab_run_dir,
        rows,
        summary,
        counts_a,
        counts_b,
        args.label_a,
        args.label_b,
        args.variant_a_url,
        args.variant_b_url,
        suggested_fix_files,
    )
    print(
        json.dumps(
            {
                "comparison_json": str(comparison_path),
                "report_md": str(ab_run_dir / "report.md"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
