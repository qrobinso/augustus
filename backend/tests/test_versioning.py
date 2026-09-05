"""Exercise version automation with real commits in isolated repositories."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


def git(repo, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=check
    )


@pytest.fixture
def repo(tmp_path):
    for name in ("frontend/package.json", "frontend/package-lock.json", "backend/app/__init__.py"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith("__init__.py"):
            target.write_text('__version__ = "0.1.0"\n')
        else:
            data = {"name": "test", "version": "0.1.0"}
            if "lock" in name:
                data["packages"] = {"": {"version": "0.1.0"}, "node_modules/example": {"version": "9.8.7"}}
            target.write_text(json.dumps(data, indent=2) + "\n")
    for name in ("scripts/version.py", ".githooks/pre-commit"):
        if (ROOT / name).exists():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, tmp_path / name)
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Version Test")
    git(tmp_path, "config", "commit.gpgsign", "false")
    git(tmp_path, "config", "core.hooksPath", str(tmp_path / "disabled-hooks"))
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial")
    git(tmp_path, "config", "core.hooksPath", ".githooks")
    (tmp_path / "change.txt").write_text("feature\n")
    git(tmp_path, "add", "change.txt")
    return tmp_path


def assert_version(repo, expected):
    assert json.loads(git(repo, "show", "HEAD:frontend/package.json").stdout)["version"] == expected
    lock = json.loads(git(repo, "show", "HEAD:frontend/package-lock.json").stdout)
    assert lock["version"] == lock["packages"][""]["version"] == expected
    assert lock["packages"]["node_modules/example"]["version"] == "9.8.7"
    namespace = {}
    exec(git(repo, "show", "HEAD:backend/app/__init__.py").stdout, namespace)
    assert namespace["__version__"] == expected


def test_main_commit_bumps_and_stages_all_versions(repo):
    git(repo, "commit", "-m", "feat: example")
    assert_version(repo, "0.1.1")
    assert git(repo, "status", "--porcelain").stdout == ""


def test_feature_branch_does_not_bump(repo):
    git(repo, "switch", "-c", "feature/example")
    git(repo, "commit", "-m", "feat: example")
    assert_version(repo, "0.1.0")


def test_manual_minor_bump_is_not_incremented_again(repo):
    result = subprocess.run(
        [sys.executable, "scripts/version.py", "--bump", "minor"],
        cwd=repo, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    git(repo, "add", "frontend", "backend")
    git(repo, "commit", "-m", "feat: release")
    assert_version(repo, "0.2.0")


def test_unstaged_version_file_edits_are_preserved_and_commit_rejected(repo):
    path = repo / "frontend/package.json"
    content = path.read_text().replace('"name": "test"', '"name": "unfinished"')
    path.write_text(content)
    before = git(repo, "rev-parse", "HEAD").stdout
    result = git(repo, "commit", "-m", "feat: example", check=False)
    assert result.returncode != 0
    assert path.read_text() == content
    assert git(repo, "rev-parse", "HEAD").stdout == before


def test_empty_commit_attempt_does_not_change_versions(repo):
    git(repo, "reset", "HEAD", "change.txt")
    result = git(repo, "commit", "-m", "empty", check=False)
    assert result.returncode != 0
    assert_version(repo, "0.1.0")
    assert git(repo, "diff").stdout == ""


def test_out_of_sync_versions_fail_check(repo):
    (repo / "backend/app/__init__.py").write_text('__version__ = "0.0.1"\n')
    result = subprocess.run(
        [sys.executable, "scripts/version.py", "--check"],
        cwd=repo, text=True, capture_output=True,
    )
    assert result.returncode == 1
    assert "out of sync" in result.stderr
