#!/usr/bin/env python3
"""Parse a GitHub HTTP URL that points to a target skill directory or SKILL.md."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse


SUPPORTED_HOSTS = {"github.com", "www.github.com"}
HEX_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


@dataclass
class ParsedSkillUrl:
    source_url: str
    repo_url: str
    org: str
    repo: str
    ref: str
    subdir: str
    normalized_url: str
    entry_type: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_url": self.source_url,
            "repo_url": self.repo_url,
            "org": self.org,
            "repo": self.repo,
            "ref": self.ref,
            "subdir": self.subdir,
            "normalized_url": self.normalized_url,
            "entry_type": self.entry_type,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse a GitHub URL into repo URL, ref, and skill subdir."
    )
    parser.add_argument("url", help="GitHub HTTP URL to a skill directory or SKILL.md")
    return parser.parse_args()


def list_remote_refs(repo_url: str) -> set[str]:
    proc = subprocess.run(
        ["git", "ls-remote", "--heads", "--tags", repo_url],
        check=True,
        capture_output=True,
        text=True,
    )
    refs: set[str] = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        ref = parts[1]
        if ref.startswith("refs/heads/"):
            refs.add(ref.removeprefix("refs/heads/"))
        elif ref.startswith("refs/tags/"):
            refs.add(ref.removeprefix("refs/tags/"))
    return refs


def split_ref_and_subdir(tail_parts: list[str], repo_url: str) -> tuple[str, list[str]]:
    if not tail_parts:
        raise ValueError("missing ref and skill path after /tree/ or /blob/")

    remote_refs = list_remote_refs(repo_url)
    for split in range(len(tail_parts), 0, -1):
        ref = "/".join(tail_parts[:split])
        if ref in remote_refs:
            subdir_parts = tail_parts[split:]
            if not subdir_parts:
                raise ValueError("URL must point to a skill directory or SKILL.md, not only a ref")
            return ref, subdir_parts

    first = tail_parts[0]
    if HEX_RE.match(first):
        subdir_parts = tail_parts[1:]
        if not subdir_parts:
            raise ValueError("commit URL must include a skill directory or SKILL.md path")
        return first, subdir_parts

    raise ValueError(
        "unable to resolve ref from GitHub URL; prefer a /tree/<ref>/<skill-path> or /blob/<ref>/<skill-path>/SKILL.md URL"
    )


def parse_github_skill_url(url: str) -> ParsedSkillUrl:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("skill URL must use http or https")
    if parsed.netloc not in SUPPORTED_HOSTS:
        raise ValueError("only github.com HTTP URLs are supported")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 4:
        raise ValueError("GitHub URL is too short to identify a repository and skill path")

    org, repo, entry_type = parts[0], parts[1], parts[2]
    if entry_type not in {"tree", "blob"}:
        raise ValueError("GitHub URL must use /tree/ or /blob/")

    repo_url = f"https://github.com/{org}/{repo}.git"
    ref, subdir_parts = split_ref_and_subdir(parts[3:], repo_url)

    if entry_type == "blob":
        if not subdir_parts or subdir_parts[-1] != "SKILL.md":
            raise ValueError("blob URLs must point to SKILL.md")
        subdir_parts = subdir_parts[:-1]

    subdir = str(PurePosixPath(*subdir_parts))
    if not subdir or subdir == ".":
        raise ValueError("URL must resolve to a skill directory")

    normalized_url = f"https://github.com/{org}/{repo}/{entry_type}/{ref}/{subdir}"
    if entry_type == "blob":
        normalized_url = f"{normalized_url}/SKILL.md"

    return ParsedSkillUrl(
        source_url=url,
        repo_url=repo_url,
        org=org,
        repo=repo,
        ref=ref,
        subdir=subdir,
        normalized_url=normalized_url,
        entry_type=entry_type,
    )


def main() -> int:
    args = parse_args()
    parsed = parse_github_skill_url(args.url)
    print(json.dumps(parsed.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
