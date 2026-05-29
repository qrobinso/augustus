# Contributing to Augustus

Thank you for your interest in contributing to Augustus! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/qrobinso/augustus.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test your changes
6. Commit: `git commit -m 'Add some feature'`
7. Push: `git push origin feature/your-feature-name`
8. Open a Pull Request

## Development Setup

See the [README.md](README.md) for development setup instructions.

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## Code Style

Linting and formatting are enforced by tooling. Install the dev tools once:

```bash
# Backend (from backend/)
pip install -r requirements-dev.txt

# Frontend (from frontend/)
npm install
```

Then run the checks before opening a PR:

```bash
# Backend — lint and format with ruff
cd backend
ruff check .          # lint
ruff check . --fix    # auto-fix lint issues
ruff format .         # format

# Frontend — eslint + prettier
cd frontend
npm run lint          # lint
npm run lint:fix      # auto-fix lint issues
npm run format        # format with prettier
```

- **Python**: ruff enforces PEP 8 plus import sorting and modern-syntax rules (config in `backend/pyproject.toml`).
  - Use type hints where appropriate
  - Follow async/await patterns for database operations

- **TypeScript/React**:
  - ESLint flat config + Prettier (config in `frontend/eslint.config.js` and `frontend/.prettierrc.json`)
  - Use functional components with hooks
  - Prefer TypeScript types over `any`

## Branch & Scope Conventions

- **Branch names** are prefixed by type: `feature/<name>`, `fix/<name>`, `chore/<name>`, `docs/<name>`.
- **One feature per branch.** Keep each branch focused on a single concern. If you start
  building something unrelated (e.g. a new subsystem) while on a feature branch, cut a new
  branch for it rather than letting two features tangle together — untangling them later is
  error-prone and bloats the diff.
- **Branch off `master`** unless you are intentionally stacking on in-progress work.
- **Commit messages** follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`. Use the imperative mood
  ("add feature", not "added feature") and reference issues when applicable (`fix #123: ...`).
- **Keep generated files out of feature diffs** where possible — regenerate lock files in
  their own commit so they don't obscure the real changes under review.

## Pull Request Process

1. Update documentation if needed
2. Ensure all tests pass (if applicable)
3. Update the README.md if you're adding new features
4. Ensure your code follows the project's style guidelines
5. Request review from maintainers

## Areas for Contribution

- Bug fixes
- New features
- Documentation improvements
- Performance optimizations
- Test coverage
- UI/UX improvements
- Additional TTS or LLM provider integrations

## Questions?

Open an issue for any questions or concerns. We're happy to help!

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming and inclusive community.

