#!/usr/bin/env python3
"""Synchronize app versions and bump main commits without extra dependencies."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FILES = ("frontend/package.json", "frontend/package-lock.json", "backend/app/__init__.py")
VERSION_LINE = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def parse_version(value):
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value):
        raise ValueError(f"Expected major.minor.patch version, got {value!r}")
    return tuple(map(int, value.split(".")))


def load_versions():
    package = json.loads((ROOT / FILES[0]).read_text())
    lock = json.loads((ROOT / FILES[1]).read_text())
    backend = (ROOT / FILES[2]).read_text()
    match = VERSION_LINE.search(backend)
    if not match:
        raise ValueError("Backend __version__ is missing")
    version = package["version"]
    parse_version(version)
    if any(value != version for value in (lock["version"], lock["packages"][""]["version"], match[1])):
        raise ValueError("App versions are out of sync; restore matching versions before bumping")
    return version, package, lock, backend


def bump(part):
    version, package, lock, backend = load_versions()
    numbers = list(parse_version(version))
    index = ("major", "minor", "patch").index(part)
    numbers[index] += 1
    numbers[index + 1:] = [0] * (2 - index)
    new_version = ".".join(map(str, numbers))
    package["version"] = lock["version"] = lock["packages"][""]["version"] = new_version
    updates = (
        json.dumps(package, indent=2) + "\n",
        json.dumps(lock, indent=2) + "\n",
        VERSION_LINE.sub(f'__version__ = "{new_version}"', backend),
    )
    for name, content in zip(FILES, updates):
        (ROOT / name).write_text(content)
    print(f"Augustus {version} → {new_version}")


def pre_commit():
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        return
    if not git("diff", "--cached", "--name-only"):
        return
    # Never absorb unrelated, unstaged package or backend edits into a commit.
    if git("diff", "--name-only", "--", *FILES):
        raise ValueError("Stage or stash edits to the version files before committing on main")
    version, _, _, _ = load_versions()
    previous = json.loads(git("show", f"HEAD:{FILES[0]}"))["version"]
    if parse_version(version) < parse_version(previous):
        raise ValueError("App version cannot decrease on main")
    if version == previous:
        bump("patch")
        git("add", "--", *FILES)
    else:
        print(f"Augustus {version} (explicit version bump)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--bump", choices=("patch", "minor", "major"))
    action.add_argument("--check", action="store_true")
    action.add_argument("--pre-commit", action="store_true")
    args = parser.parse_args()
    try:
        if args.bump:
            bump(args.bump)
        elif args.check:
            print(f"Augustus {load_versions()[0]}: versions synchronized")
        else:
            pre_commit()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"Version update failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
