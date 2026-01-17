# Skill: Python Project Initialization

## What This Skill Does
Initializes a complete Python 3.11+ project with modern packaging standards, dependency management, and Git version control.

## Files Created

### pyproject.toml
Modern Python project configuration with:
- Build system (setuptools)
- Project metadata
- Dependencies and optional dev dependencies
- Tool configurations (black, mypy, pytest, coverage)

### requirements.txt
Pinned production dependencies for reproducible builds:
- Flask 3.0.0 - Web framework for API
- PyGObject 3.46.0 - GTK bindings
- python-gnupg 0.5.2 - PGP encryption
- PyJWT 2.8.0 - JWT tokens
- cryptography 41.0.7 - TLS/encryption
- aiosmtpd 1.4.4 - Async SMTP server
- SQLite (built into Python) - Local database with FTS5

### requirements-dev.txt
Development and testing tools:
- pytest ecosystem (pytest, pytest-cov, pytest-asyncio)
- Playwright for E2E testing
- Code quality (black, flake8, mypy, isort)

### __version__.py
Single source of truth for version info.

## Usage
```bash
# Development install
pip install -e ".[dev]"

# Production install
pip install .

# Run tests
pytest

# Format code
black src/
```

## Git Integration
Repository initialized with initial commit containing all project files.
