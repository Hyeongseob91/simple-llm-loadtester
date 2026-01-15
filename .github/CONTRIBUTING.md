# Contributing to Simple LLM Loadtester

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

### 1. Fork the Repository

```bash
# Fork via GitHub UI, then clone your fork
git clone https://github.com/YOUR_USERNAME/simple-llm-loadtester.git
cd simple-llm-loadtester
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## Development Guidelines

### Code Style

- **Python**: Follow PEP 8 guidelines
- **Type hints**: Required for all functions
- **Linter**: We use `ruff` for linting

```bash
# Run linter
ruff check shared/ services/

# Auto-fix issues
ruff check --fix shared/ services/
```

### Testing

All contributions must include tests and pass existing tests.

```bash
# Run all tests
pytest tests/unit tests/integration -v

# Run with coverage
pytest tests/unit tests/integration --cov=shared/core --cov-report=term-missing

# Minimum coverage: 35%
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding tests
- `refactor`: Code refactoring
- `chore`: Maintenance tasks

**Examples:**
```
feat(api): Add benchmark comparison endpoint
fix(metrics): Correct percentile calculation
docs: Update installation guide
test(recommend): Add edge case tests
```

## Pull Request Process

### 1. Before Submitting

- [ ] All tests pass locally
- [ ] Code follows project style guidelines
- [ ] New code has appropriate tests
- [ ] Documentation updated if needed

### 2. PR Title

Use the same format as commit messages:
```
feat(core): Add support for streaming responses
```

### 3. PR Description Template

```markdown
## Summary
Brief description of changes

## Changes
- Change 1
- Change 2

## Testing
How was this tested?

## Related Issues
Fixes #123
```

### 4. Review Process

1. CI must pass (tests, linting)
2. At least 1 maintainer approval required
3. All review comments addressed
4. Branch up to date with main

## Project Structure

```
simple-llm-loadtester/
├── services/           # Microservices
│   ├── cli/           # CLI application
│   ├── api/           # FastAPI backend
│   └── web/           # Next.js frontend
├── shared/            # Shared libraries
│   ├── core/          # Core logic (metrics, load generator)
│   ├── adapters/      # Server adapters (vLLM, OpenAI, etc.)
│   └── database/      # Database layer
└── tests/             # Test suites
    ├── unit/
    ├── integration/
    └── api/
```

## Need Help?

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Use discussions for questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
