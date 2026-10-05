#!/usr/bin/env python3
"""Flag potential private data without printing matched values. Read-only Git scan."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "credential": re.compile(
        rb"(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|"
        rb"sk-(?:proj-)?[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16}|"
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    ),
    "personal_path": re.compile(rb"/(?:Users|home)/[A-Za-z0-9._-]+"),
    "email": re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def findings(data):
    result = []
    for rule, pattern in PATTERNS.items():
        matches = pattern.findall(data)
        if rule == "email":
            matches = [
                value
                for value in matches
                if not value.endswith(b"@users.noreply.github.com")
                and value not in {b"git@github.com", b"noreply@github.com"}
                and not value.endswith(
                    (b"@example.com", b"@example.org", b"@example.net", b"@example.invalid")
                )
            ]
        if matches:
            result.append({"rule": rule, "matches": len(matches)})
    return result


def scan(history=False):
    current = []
    paths = git("ls-files", "-z").decode().split("\0")
    for name in filter(None, paths):
        path = ROOT / name
        if path.is_file():
            hits = findings(path.read_bytes())
            if hits:
                current.append({"file": name, "findings": hits})
    archived = []
    objects = 0
    metadata = []
    if history:
        for line in git("rev-list", "--objects", "--all").splitlines():
            oid = line.split(b" ", 1)[0].decode()
            if git("cat-file", "-t", oid).strip() != b"blob":
                continue
            objects += 1
            hits = findings(git("cat-file", "blob", oid))
            if hits:
                archived.append({"object": oid, "findings": hits})
        for line in git("log", "--all", "--format=%H%x09%an <%ae> %cn <%ce>%n%B%x00").split(b"\0"):
            hits = findings(line)
            if hits:
                metadata.append({"findings": hits})
    return {
        "passed": not (current or archived or metadata),
        "tracked_files": len(list(filter(None, paths))),
        "current": current,
        "history_scanned": history,
        "historical_blobs": objects,
        "historical_findings": archived,
        "commit_metadata_findings": metadata,
        "limits": "Pattern-based triage, not a privacy guarantee. Public third-party contacts may be false positives. Untracked files, remote-only refs, GitHub artifacts and arbitrary token formats require separate review. Matched values are never printed.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history", action="store_true", help="scan all locally reachable Git history"
    )
    parser.add_argument("--output", type=Path, help="save a redacted findings report")
    args = parser.parse_args()
    report = scan(args.history)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return int(not report["passed"])


if __name__ == "__main__":
    sys.exit(main())
