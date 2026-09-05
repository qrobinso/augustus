# Repository workflow

Make changes directly on `main` unless the user requests a different branch.

Keep automatic version updates enabled: `git config core.hooksPath .githooks`.
The pre-commit hook bumps the patch version for each nonempty commit on `main`
and stages the synchronized frontend, lockfile, and backend versions. It requires
Python 3 and refuses to absorb unstaged edits to those files.

For a feature release, run `python3 scripts/version.py --bump minor` before final
verification and stage all three version files; use `--bump major` for a breaking
release. The hook preserves an already staged version increase. Run
`python3 scripts/version.py --check` before publishing. Do not hard-code the
version in the UI or API: use package metadata or `app.__version__`.
