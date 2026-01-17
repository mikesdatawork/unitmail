# Contributing to unitMail

Thank you for your interest in contributing to unitMail! This document provides guidelines for contributing to the project, including development setup, code standards, testing requirements, and the pull request process.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Style Guide](#code-style-guide)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [Community Guidelines](#community-guidelines)

---

## Development Setup

### Prerequisites

Ensure you have the following installed:

- **Python 3.11+**: Primary development language
- **Git**: Version control
- **Docker** (optional): For running services locally
- **Node.js 18+** (optional): For frontend tooling

### Getting Started

#### 1. Fork and Clone

```bash
# Fork the repository on GitHub first, then:
git clone https://github.com/YOUR_USERNAME/unitmail.git
cd unitmail

# Add upstream remote
git remote add upstream https://github.com/unitmail/unitmail.git
```

#### 2. Create Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate
```

#### 3. Install Dependencies

```bash
# Install package in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
python -c "import unitmail; print(unitmail.__version__)"
```

#### 4. Set Up Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run on all files (optional)
pre-commit run --all-files
```

#### 5. Configure Environment

```bash
# Copy example configuration
cp config/settings.example.toml config/settings.toml

# Create .env file for secrets (optional)
cat << 'EOF' > .env
API_JWT_SECRET=dev-secret-change-in-production
EOF
```

#### 6. Set Up Database

unitMail uses SQLite which requires no separate database server. The database is automatically created on first run.

```bash
# The database will be created at ~/.unitmail/data/unitmail.db
# Run migrations if upgrading from a previous version:
python scripts/migrate.py up
```

The SQLite database is a single file that can be easily backed up by copying.

#### 7. Verify Setup

```bash
# Run tests
pytest

# Run linters
black --check src tests
flake8 src tests
mypy src

# Start development server
python -m unitmail
```

### IDE Setup

#### VS Code

Recommended extensions:
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Black Formatter (ms-python.black-formatter)

`.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.formatting.provider": "none",
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true
    },
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true
}
```

#### PyCharm

1. Set Python interpreter to `.venv/bin/python`
2. Enable Black formatter in Settings > Tools > Black
3. Enable Flake8 in Settings > Editor > Inspections

---

## Code Style Guide

### Python Style

We follow [PEP 8](https://pep8.org/) with some additions, enforced by Black and Flake8.

#### Formatting with Black

```bash
# Format all code
black src tests

# Check without modifying
black --check src tests
```

Black configuration (`pyproject.toml`):

```toml
[tool.black]
line-length = 88
target-version = ['py311', 'py312']
```

#### Linting with Flake8

```bash
flake8 src tests
```

#### Type Hints

All code must have type hints. We use MyPy for static type checking.

```python
# Good
def send_message(
    to: list[str],
    subject: str,
    body: str,
    encrypt: bool = False
) -> MessageResult:
    ...

# Bad
def send_message(to, subject, body, encrypt=False):
    ...
```

Run MyPy:

```bash
mypy src
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Modules | snake_case | `message_handler.py` |
| Classes | PascalCase | `MessageHandler` |
| Functions | snake_case | `send_message()` |
| Variables | snake_case | `message_count` |
| Constants | UPPER_SNAKE_CASE | `MAX_MESSAGE_SIZE` |
| Private | Leading underscore | `_internal_method()` |

### Import Order

Use isort for consistent imports:

```python
# Standard library
import os
from datetime import datetime
from typing import Optional

# Third-party
import flask
from pydantic import BaseModel

# Local
from unitmail.common import config
from unitmail.common.models import Message
```

### Docstrings

Use Google-style docstrings:

```python
def send_message(
    to: list[str],
    subject: str,
    body: str,
    encrypt: bool = False
) -> MessageResult:
    """Send an email message.

    Queues a message for delivery through the gateway.
    Supports optional PGP encryption if recipient keys
    are available.

    Args:
        to: List of recipient email addresses.
        subject: Email subject line.
        body: Plain text message body.
        encrypt: Whether to encrypt the message.

    Returns:
        MessageResult containing queue ID and status.

    Raises:
        ValidationError: If recipient addresses are invalid.
        QuotaExceededError: If daily quota is exceeded.

    Example:
        >>> result = send_message(
        ...     to=["user@example.com"],
        ...     subject="Hello",
        ...     body="Message content"
        ... )
        >>> print(result.queue_id)
        'q_abc123'
    """
```

### Error Handling

Use custom exceptions from `src/common/exceptions.py`:

```python
from unitmail.common.exceptions import (
    ValidationError,
    QuotaExceededError,
    MessageNotFoundError,
)

def get_message(message_id: str) -> Message:
    message = db.query(Message).filter_by(id=message_id).first()
    if message is None:
        raise MessageNotFoundError(f"Message not found: {message_id}")
    return message
```

### Logging

Use the standard logging module:

```python
import logging

logger = logging.getLogger(__name__)

def process_message(message_id: str) -> None:
    logger.info("Processing message", extra={"message_id": message_id})
    try:
        # ... process
        logger.debug("Message processed successfully")
    except Exception as e:
        logger.error("Failed to process message", exc_info=True)
        raise
```

---

## Testing Requirements

### Test Structure

```
tests/
├── unit/              # Unit tests
│   ├── test_models.py
│   ├── test_services.py
│   └── test_api.py
├── e2e/               # End-to-end tests
│   ├── test_send_receive.py
│   └── test_user_flows.py
├── fixtures/          # Test fixtures
│   ├── messages.py
│   └── users.py
└── conftest.py        # Pytest configuration
```

### Writing Tests

#### Unit Tests

```python
import pytest
from unitmail.common.models import Message

class TestMessage:
    """Tests for the Message model."""

    def test_create_message(self):
        """Test creating a new message."""
        message = Message(
            from_addr="sender@example.com",
            to_addr=["recipient@example.com"],
            subject="Test",
            body="Content"
        )
        assert message.from_addr == "sender@example.com"
        assert message.subject == "Test"

    def test_invalid_email_raises_error(self):
        """Test that invalid email raises ValidationError."""
        with pytest.raises(ValidationError):
            Message(
                from_addr="invalid-email",
                to_addr=["recipient@example.com"],
                subject="Test",
                body="Content"
            )

    @pytest.mark.parametrize("subject,expected", [
        ("Test", "Test"),
        ("", "(No Subject)"),
        (None, "(No Subject)"),
    ])
    def test_subject_normalization(self, subject, expected):
        """Test subject line normalization."""
        message = Message(
            from_addr="sender@example.com",
            to_addr=["recipient@example.com"],
            subject=subject,
            body="Content"
        )
        assert message.display_subject == expected
```

#### Using Fixtures

```python
# conftest.py
import pytest
from unitmail.common.storage import EmailStorage

@pytest.fixture
def db():
    """Create a test database."""
    storage = EmailStorage(":memory:")
    yield storage
    storage.close()

@pytest.fixture
def sample_message():
    """Create a sample message for testing."""
    return Message(
        from_addr="sender@example.com",
        to_addr=["recipient@example.com"],
        subject="Test Message",
        body="This is a test message."
    )

# test_services.py
def test_save_message(db, sample_message):
    """Test saving a message to the database."""
    db.save(sample_message)
    retrieved = db.get(Message, sample_message.id)
    assert retrieved.subject == "Test Message"
```

#### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_send():
    """Test async message sending."""
    result = await async_send_message(
        to=["user@example.com"],
        subject="Async Test",
        body="Content"
    )
    assert result.status == "queued"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/unitmail --cov-report=html

# Run specific test file
pytest tests/unit/test_models.py

# Run tests matching pattern
pytest -k "test_send"

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x
```

### Coverage Requirements

- **Minimum coverage**: 80%
- **Critical paths**: 95%+ (authentication, message handling, encryption)

```bash
# Generate coverage report
pytest --cov=src/unitmail --cov-report=term-missing

# Open HTML report
open htmlcov/index.html
```

---

## Pull Request Process

### Before You Start

1. **Check existing issues**: Look for related issues or PRs
2. **Open an issue first**: For new features or significant changes
3. **Sync with upstream**: Ensure your fork is up to date

```bash
git fetch upstream
git checkout main
git merge upstream/main
```

### Creating a Branch

Use descriptive branch names:

```bash
# Feature
git checkout -b feature/add-encryption-option

# Bug fix
git checkout -b fix/message-encoding-error

# Documentation
git checkout -b docs/update-api-reference
```

### Making Changes

1. Make focused, atomic commits
2. Write clear commit messages
3. Keep PRs small and reviewable

#### Commit Message Format

```
type(scope): Short description

Longer description if needed. Explain what and why,
not how (the code shows how).

Fixes #123
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:

```
feat(api): Add message encryption endpoint

Add POST /api/v1/messages/encrypt endpoint that allows
encrypting message content with recipient's PGP key.

Closes #456
```

```
fix(smtp): Handle non-ASCII characters in subject

Messages with non-ASCII subject lines were being rejected.
Now properly encode using RFC 2047 format.

Fixes #789
```

### Pre-Submit Checklist

Before submitting your PR:

```bash
# Format code
black src tests

# Run linters
flake8 src tests
mypy src

# Run tests
pytest

# Check coverage
pytest --cov=src/unitmail

# Update documentation if needed
```

### Submitting the PR

1. Push your branch:

```bash
git push origin feature/your-feature
```

2. Open PR on GitHub with:
   - Clear title describing the change
   - Description explaining what/why
   - Reference to related issues
   - Screenshots for UI changes

#### PR Template

```markdown
## Description

Brief description of the changes.

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update

## How Has This Been Tested?

Describe the tests you ran to verify your changes.

## Checklist

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code where needed
- [ ] I have updated the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing tests pass locally
- [ ] Any dependent changes have been merged

## Related Issues

Fixes #(issue number)
```

### Code Review

- Address all reviewer feedback
- Push additional commits to address feedback
- Avoid force-pushing once review has started
- Be patient and respectful

### After Merge

- Delete your feature branch
- Update your local main branch

```bash
git checkout main
git pull upstream main
git branch -d feature/your-feature
```

---

## Issue Reporting

### Bug Reports

Use the bug report template:

```markdown
## Bug Description

Clear description of the bug.

## Steps to Reproduce

1. Go to '...'
2. Click on '...'
3. See error

## Expected Behavior

What you expected to happen.

## Actual Behavior

What actually happened.

## Environment

- OS: Ubuntu 22.04
- unitMail version: 0.1.0
- Python version: 3.11.7

## Logs/Screenshots

```
Paste relevant logs here
```

## Additional Context

Any other relevant information.
```

### Feature Requests

Use the feature request template:

```markdown
## Feature Description

Clear description of the feature.

## Problem/Motivation

Why is this feature needed?

## Proposed Solution

How should it work?

## Alternatives Considered

What alternatives did you consider?

## Additional Context

Any other relevant information.
```

### Security Issues

**Do not open public issues for security vulnerabilities.**

Instead:
1. Email security@unitmail.org
2. Include detailed description
3. Wait for response before disclosure

---

## Community Guidelines

### Code of Conduct

We are committed to providing a welcoming and inclusive environment.

**Be respectful**: Treat everyone with respect. Disagreements are fine; personal attacks are not.

**Be constructive**: Provide helpful feedback. Explain why, not just what.

**Be patient**: Not everyone has the same experience level. Help others learn.

**Be inclusive**: Welcome newcomers. Avoid jargon when possible.

### Getting Help

- **GitHub Discussions**: For questions and ideas
- **Discord/Matrix**: For real-time chat (link in README)
- **Stack Overflow**: Tag questions with `unitmail`

### Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project website

Thank you for contributing to unitMail!

---

## Quick Reference

### Common Commands

```bash
# Install dev environment
pip install -e ".[dev]"

# Format code
black src tests

# Run linters
flake8 src tests && mypy src

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/unitmail --cov-report=html

# Build package
python -m build

# Start development server
python -m unitmail
```

### Useful Links

- [GitHub Repository](https://github.com/unitmail/unitmail)
- [Issue Tracker](https://github.com/unitmail/unitmail/issues)
- [Project Documentation](https://docs.unitmail.org)
- [API Reference](/docs/API_REFERENCE.md)
