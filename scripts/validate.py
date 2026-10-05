#!/usr/bin/env python3
"""Run repeatable release checks. No network, model calls or customer writes."""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/global-gtm-strategy-skill"


def check_structure():
    """Check this repository's minimal frontmatter and local Markdown links."""
    errors = []
    entry = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    parts = entry.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        errors.append("SKILL.md: missing YAML frontmatter")
    else:
        fields = dict(re.findall(r"^(name|description):\s*(.+)$", parts[1], re.M))
        if fields.get("name") != SKILL.name:
            errors.append("skill name does not match directory")
        if not 0 < len(fields.get("description", "")) <= 1024:
            errors.append("description must contain 1–1024 characters")
    links = 0
    # Historical outputs are retained, so broken archive links are also findings.
    for file in sorted(ROOT.rglob("*.md")):
        if any(part in {".git", ".validation-output", "growth-workspaces"} for part in file.parts):
            continue
        content = re.sub(r"```.*?```", "", file.read_text(encoding="utf-8"), flags=re.S)
        for target in re.findall(r"\[[^\]\n]+\]\(([^)]+)\)", content):
            target = target.split("#", 1)[0].strip("<>")
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            links += 1
            if not (file.parent / target).is_file() and not (file.parent / target).is_dir():
                errors.append(f"{file.relative_to(ROOT)}: broken link {target}")
    return dict(
        passed=not errors,
        local_links=links,
        errors=errors,
        limits="Repository checks, not a complete YAML/spec parser or semantic quality evaluation.",
    )


def execute(label, arguments, output):
    """Run a bounded child process and retain its exact stdout/stderr."""
    result = subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    (output / f"{label}.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        print(f"{label} failed:\n{result.stdout}{result.stderr}", file=sys.stderr)
    return dict(name=label, passed=result.returncode == 0, exit_code=result.returncode)


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    checks = [dict(name="structure", **check_structure())]
    commands = (
        ("unit", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_helpers.py"]),
        ("release", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_release.py"]),
        (
            "stress",
            [
                "tests/stress.py",
                str(SKILL / "scripts"),
                str(output / "stress.json"),
            ],
        ),
        (
            "expanded",
            [
                "tests/expanded.py",
                str(SKILL / "scripts"),
                str(output / "expanded.json"),
            ],
        ),
    )
    for label, arguments in commands:
        try:
            checks.append(execute(label, arguments, output))
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append(dict(name=label, passed=False, error=str(exc)))
    report = dict(
        passed=all(check["passed"] for check in checks),
        checks=checks,
        limits="Deterministic helper checks; model behavior and real market outcomes require separate review.",
    )
    (output / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="optional directory for verification logs")
    args = parser.parse_args()
    if args.output:
        report = run(args.output.absolute())
    else:
        with tempfile.TemporaryDirectory(prefix="gtm-validation-") as directory:
            report = run(Path(directory))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(not report["passed"])


if __name__ == "__main__":
    sys.exit(main())
