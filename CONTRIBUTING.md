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

- **Python**: Follow PEP 8 style guidelines
  - Use type hints where appropriate
  - Follow async/await patterns for database operations
  - Use descriptive variable and function names

- **TypeScript/React**: 
  - Use ESLint configuration provided
  - Follow React best practices
  - Use functional components with hooks
  - Prefer TypeScript types over `any`

- **Commits**: Write clear, descriptive commit messages
  - Use present tense ("Add feature" not "Added feature")
  - Reference issues when applicable: "Fix #123: ..."

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

