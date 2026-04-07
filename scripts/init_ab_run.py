#!/usr/bin/env python3
"""Initialize an A/B evaluation run driven by two GitHub skill URLs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize an ab-urls evaluation run.")
    parser.add_argument("root", nargs="?", default=".", help="Workspace root that contains agentic-evals/")
    parser.add_argument("target_id", help="Target skill id under evaluation")
    parser.add_argument("variant_a_url", help="GitHub HTTP URL for variant A")
    parser.add_argument("variant_b_url", help="GitHub HTTP URL for variant B")
    parser.add_argument("--label-a", default="A")
    parser.add_argument("--label-b", default="B")
    parser.add_argument("--suite-id", dest="suite_ids", action="append", default=[])
    parser.add_argument("--case-id", dest="case_ids", action="append", default=[])
    parser.add_argument("--skip-prepare-variants", action="store_true")
    return parser.parse_args()


def run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def ensure_single_run_dirs(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "case-artifacts").mkdir(exist_ok=True)
    (run_dir / "case-results").mkdir(exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init_variant_run_manifest(
    target_id: str,
    case_root: Path,
    suite_ids: list[str],
    case_ids: list[str],
    label: str,
    source_url: str,
) -> dict:
    return {
        "run_mode": "single-run",
        "target_id": target_id,
        "suite_ids": suite_ids,
        "selected_case_ids": case_ids,
        "target_skill_path": f".agents/skills/{target_id}/SKILL.md",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "workspace_mode": "isolated-per-case",
        "case_workspace_root": str(case_root),
        "evidence_mode": "codex-local-session-store",
        "variant_label": label,
        "variant_source_url": source_url,
        "notes": [
            "This variant run is part of an ab-urls parent run.",
            "Use the normal per-case spawn_agent flow inside this run directory.",
        ],
    }


def prepare_variant(root: Path, target_id: str, url: str, temp_root: Path, label: str) -> dict:
    prepare_script = SCRIPT_DIR / "prepare_variant_source_workspace.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(prepare_script),
            str(root),
            target_id,
            url,
            str(temp_root),
            "--label",
            label,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    target_yaml = root / "agentic-evals" / "targets" / args.target_id / "target.yaml"
    if not target_yaml.exists():
        raise SystemExit(f"missing target config: {target_yaml}")

    current_run_id = run_id()
    ab_run_dir = root / "agentic-evals" / "runs" / current_run_id
    variant_source_root = Path(tempfile.mkdtemp(prefix=f"openclaw-skill-eval-{args.target_id}-ab-"))

    case_root_a = variant_source_root / "case-workspaces" / args.label_a
    case_root_b = variant_source_root / "case-workspaces" / args.label_b
    case_root_a.mkdir(parents=True, exist_ok=True)
    case_root_b.mkdir(parents=True, exist_ok=True)

    run_dir_a = ab_run_dir / "variants" / args.label_a / "run"
    run_dir_b = ab_run_dir / "variants" / args.label_b / "run"
    ensure_single_run_dirs(run_dir_a)
    ensure_single_run_dirs(run_dir_b)

    manifest_a = init_variant_run_manifest(
        args.target_id,
        case_root_a,
        args.suite_ids,
        args.case_ids,
        args.label_a,
        args.variant_a_url,
    )
    manifest_b = init_variant_run_manifest(
        args.target_id,
        case_root_b,
        args.suite_ids,
        args.case_ids,
        args.label_b,
        args.variant_b_url,
    )
    write_json(run_dir_a / "manifest.json", manifest_a)
    write_json(run_dir_b / "manifest.json", manifest_b)

    top_manifest = {
        "run_mode": "ab-urls",
        "run_id": current_run_id,
        "target_id": args.target_id,
        "suite_ids": args.suite_ids,
        "selected_case_ids": args.case_ids,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "variant_source_root": str(variant_source_root),
        "variants": {
            args.label_a: {
                "label": args.label_a,
                "source_url": args.variant_a_url,
                "variant_run_dir": str(run_dir_a),
            },
            args.label_b: {
                "label": args.label_b,
                "source_url": args.variant_b_url,
                "variant_run_dir": str(run_dir_b),
            },
        },
        "notes": [
            "Each variant must be prepared into its own source workspace before creating per-case workspaces.",
            "Each variant run under variants/<label>/run must satisfy the single-run artifact contract.",
        ],
    }

    if not args.skip_prepare_variants:
        variant_root = variant_source_root / "variants"
        variant_root.mkdir(parents=True, exist_ok=True)
        top_manifest["variants"][args.label_a]["source_manifest"] = prepare_variant(
            root, args.target_id, args.variant_a_url, variant_root, args.label_a
        )
        top_manifest["variants"][args.label_b]["source_manifest"] = prepare_variant(
            root, args.target_id, args.variant_b_url, variant_root, args.label_b
        )
        write_json(
            ab_run_dir / "variants" / args.label_a / "source-manifest.json",
            top_manifest["variants"][args.label_a]["source_manifest"],
        )
        write_json(
            ab_run_dir / "variants" / args.label_b / "source-manifest.json",
            top_manifest["variants"][args.label_b]["source_manifest"],
        )

    write_json(ab_run_dir / "manifest.json", top_manifest)
    (ab_run_dir / "report.md").write_text(
        "# Comparison Summary\n\n"
        "## Variant Table\n\n"
        "## Case Matrix\n\n"
        "## Regressions\n\n"
        "## Improvements\n\n"
        "## Suggested Next Fixes\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "run_mode": "ab-urls",
                "run_id": current_run_id,
                "run_dir": str(ab_run_dir),
                "variant_source_root": str(variant_source_root),
                "variant_a_run_dir": str(run_dir_a),
                "variant_b_run_dir": str(run_dir_b),
                "next_step": "Run the normal per-case evaluator flow in each variant run, then call render_ab_report.py on the parent run directory.",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
