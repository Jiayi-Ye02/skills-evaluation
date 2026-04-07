#!/usr/bin/env python3
"""Prepare an isolated source workspace for one target-skill variant URL."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from parse_github_skill_url import HEX_RE, parse_github_skill_url  # noqa: E402


COPY_IGNORE = shutil.ignore_patterns(".git", "runs", "__pycache__", "*.pyc", ".DS_Store")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a variant source workspace from a GitHub skill URL."
    )
    parser.add_argument("source_workspace", help="Local workspace that contains agentic-evals/")
    parser.add_argument("target_id", help="Target skill id under evaluation")
    parser.add_argument(
        "variant_url", help="GitHub HTTP URL to the target skill directory or SKILL.md"
    )
    parser.add_argument(
        "output_root", help="Output directory for checkout and prepared source workspace"
    )
    parser.add_argument("--label", default="variant", help="Human-readable variant label")
    return parser.parse_args()


def run(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=str(cwd) if cwd else None, check=True)


def copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        raise SystemExit(f"destination already exists: {dest}")
    shutil.copytree(src, dest, ignore=COPY_IGNORE)


def checkout_repo(repo_url: str, ref: str, checkout_dir: Path) -> None:
    if HEX_RE.match(ref):
        run(["git", "clone", "--depth", "1", repo_url, str(checkout_dir)])
        run(["git", "checkout", ref], cwd=checkout_dir)
        return
    run(["git", "clone", "--depth", "1", "--branch", ref, repo_url, str(checkout_dir)])


def main() -> int:
    args = parse_args()
    source_workspace = Path(args.source_workspace).resolve()
    local_eval_repo = source_workspace / "agentic-evals"
    if not local_eval_repo.is_dir():
        raise SystemExit(f"missing local eval repo: {local_eval_repo}")

    parsed = parse_github_skill_url(args.variant_url)
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    safe_label = "".join(ch.lower() if ch.isalnum() else "-" for ch in args.label).strip("-")
    safe_label = safe_label or "variant"
    checkout_dir = output_root / f"{safe_label}-checkout"
    prepared_source = output_root / f"{safe_label}-source"
    if checkout_dir.exists() or prepared_source.exists():
        raise SystemExit(
            f"output paths already exist under {output_root}; choose a fresh output root"
        )

    checkout_repo(parsed.repo_url, parsed.ref, checkout_dir)
    resolved_skill_dir = checkout_dir / parsed.subdir
    if not resolved_skill_dir.is_dir():
        raise SystemExit(f"skill directory does not exist after checkout: {resolved_skill_dir}")
    if not (resolved_skill_dir / "SKILL.md").is_file():
        raise SystemExit(f"skill directory is missing SKILL.md: {resolved_skill_dir}")

    prepared_source.mkdir(parents=True, exist_ok=False)
    copy_tree(local_eval_repo, prepared_source / "agentic-evals")

    target_dest = prepared_source / ".agents" / "skills" / args.target_id
    target_dest.parent.mkdir(parents=True, exist_ok=True)
    copy_tree(resolved_skill_dir, target_dest)

    manifest = {
        "label": args.label,
        "target_id": args.target_id,
        "source_url": args.variant_url,
        "normalized": parsed.to_dict(),
        "checkout_dir": str(checkout_dir),
        "resolved_skill_dir": str(resolved_skill_dir),
        "prepared_source_workspace": str(prepared_source),
    }
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
