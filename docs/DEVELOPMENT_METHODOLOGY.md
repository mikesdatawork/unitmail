# unitMail Development Methodology

## Document Information

**Version**: 1.0  
**Date**: 2026-01-11  
**Status**: Active  
**Applies To**: All unitMail development

## Purpose

This document defines how unitMail is developed. It covers processes, tools, standards, and workflows that all contributors must follow.

## Development Philosophy

**Core Principles**

1. **Simple over clever** - Code that's easy to understand beats code that's "elegant"
2. **Working over perfect** - Ship functional code, improve later
3. **Tested over untested** - If it's not tested, it's broken
4. **Documented over obvious** - Future you will thank present you
5. **Open over closed** - Default to transparency, share progress

**What We Avoid**

- Over-engineering solutions
- Premature optimization
- Feature creep
- Technical debt (we pay as we go)
- Vendor lock-in
- Proprietary dependencies

## Project Structure

### Repository Layout

```
unitmail/
├── docs/               # Documentation
│   ├── architecture/
│   ├── guides/
│   └── api/
├── src/                # Source code
│   ├── client/         # GTK application
│   ├── gateway/        # Gateway service
│   ├── common/         # Shared code
│   └── tests/          # Test suite
├── scripts/            # Build and utility scripts
├── configs/            # Configuration templates
├── migrations/         # Database migrations
├── packaging/          # Package build files
│   ├── deb/
│   ├── rpm/
│   └── appimage/
└── tools/              # Development tools
```

### Directory Rules

- No directory or file named 'claude'
- All scripts in `/scripts` directory
- All documentation in `/docs` directory
- Tests live next to code (test_*.py)
- Configs never contain secrets

## Development Environment

### Required Software

**Core Tools**
- Python 3.11 or later
- Git 2.35+
- Make (for build automation)
- PostgreSQL 3.35+

**Development Tools**
- pytest (testing)
- black (code formatting)
- flake8 (linting)
- mypy (type checking)
- pytest-cov (coverage)

**GTK Development**
- GTK 4.0+
- PyGObject
- Glade (UI design)

### Environment Setup

Developers set up their environment like this:

```bash
# Clone repository
git clone https://github.com/unitmail/unitmail.git
cd unitmail

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests to verify setup
pytest

# Start developing
```

No Docker required. No complex setup. Standard Python tools only.

## Version Control

### Git Workflow

**Branch Strategy**

```
main          - Production ready code
develop       - Integration branch
feature/*     - New features
bugfix/*      - Bug fixes
hotfix/*      - Urgent production fixes
release/*     - Release preparation
```

**Rules**

- Never commit directly to `main`
- All changes via pull request
- One feature per branch
- Delete branch after merge
- Keep commits atomic

**Commit Messages**

Format:
```
<type>: <short summary>

<optional detailed description>

<optional issue reference>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, no logic change)
- `refactor`: Code change that neither fixes bug nor adds feature
- `test`: Add or update tests
- `chore`: Maintenance tasks

Examples:
```
feat: add PGP encryption support

Implements automatic PGP encryption when recipient public key
is available. Falls back to plaintext if key not found.

Closes #123
```

```
fix: prevent duplicate message IDs

Message ID generation was not checking for collisions.
Added uniqueness check in database layer.

Fixes #456
```

### Pull Request Process

**Creating PR**

1. Branch from `develop`
2. Make changes
3. Write tests
4. Update documentation
5. Run full test suite
6. Create PR with description
7. Link related issues

**PR Template**

```markdown
## Description
Brief explanation of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How was this tested?

## Checklist
- [ ] Tests pass locally
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] No new warnings
```

**Review Requirements**

- At least one approval required
- All tests must pass
- No merge conflicts
- Documentation updated
- Code coverage maintained or improved

**Merging**

- Squash commits when merging features
- Preserve commits for releases
- Delete branch after merge
- Update changelog

## Coding Standards

### Python Style

**Follow PEP 8** with these specifics:

- Line length: 100 characters (not 79)
- Use f-strings for formatting
- Type hints on all public functions
- Docstrings on all modules, classes, functions

**Example**

```python
def send_email(
    to: str,
    subject: str,
    body: str,
    attachments: list[str] | None = None
) -> bool:
    """Send an email via SMTP gateway.
    
    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body (plain text)
        attachments: Optional list of file paths
        
    Returns:
        True if queued successfully, False otherwise
        
    Raises:
        ValueError: If email address is invalid
        SMTPError: If gateway connection fails
    """
    if not validate_email(to):
        raise ValueError(f"Invalid email address: {to}")
    
    # Implementation here
    return True
```

**Formatting**

Run before committing:
```bash
black src/
flake8 src/
mypy src/
```

All of these must pass with zero errors.

### File Naming

**Python Files**
- Modules: `lowercase_with_underscores.py`
- Classes: Match class name but lowercase
- Tests: `test_<module_name>.py`

**Scripts**
- Format: `s###_descriptive_name.sh`
- Examples: `s001_install_deps.sh`, `s002_build_package.sh`
- Sequence numbers for ordering
- Version suffixes: `s001_script_a.sh`, `s001_script_b.sh`

**Documentation**
- Markdown only: `*.md`
- UPPERCASE for main docs: `README.md`, `ARCHITECTURE.md`
- lowercase for guides: `installation.md`, `contributing.md`

### Code Organization

**Imports**

Order:
1. Standard library
2. Third-party packages
3. Local modules

Separated by blank line.

```python
import os
import sys
from pathlib import Path

import click
from flask import Flask

from unitmail.common import config
from unitmail.gateway import smtp
```

**Function Length**

- Keep functions under 50 lines
- If longer, break into smaller functions
- One function = one responsibility

**Class Design**

- Prefer composition over inheritance
- Keep classes focused
- Avoid god objects
- Use dataclasses for simple data containers

## Testing

### Test Requirements

**Coverage Target**: 80% minimum

**What Must Be Tested**
- All public APIs
- All business logic
- All error conditions
- All data transformations
- Integration points

**What Can Skip Tests**
- Simple getters/setters
- UI event handlers (test manually)
- Configuration files
- Migration scripts (tested manually)

### Test Organization

```
src/
├── client/
│   ├── composer.py
│   └── test_composer.py
├── gateway/
│   ├── smtp.py
│   └── test_smtp.py
```

Tests live next to code. No separate test directory.

### Writing Tests

**Structure**: Arrange, Act, Assert

```python
def test_send_email_validates_address():
    # Arrange
    gateway = Gateway(config)
    invalid_email = "not-an-email"
    
    # Act & Assert
    with pytest.raises(ValueError, match="Invalid email"):
        gateway.send(invalid_email, "subject", "body")
```

**Naming**
- Test functions: `test_<what>_<condition>`
- Be specific: `test_send_email_rejects_invalid_recipient`
- Not vague: `test_send_email_error`

**Fixtures**

Use pytest fixtures for setup:

```python
@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    db = create_test_database()
    yield db
    db.cleanup()

def test_message_storage(temp_db):
    message = Message(...)
    temp_db.save(message)
    assert temp_db.get(message.id) == message
```

### Running Tests

**Locally**
```bash
# All tests
pytest

# Specific file
pytest src/gateway/test_smtp.py

# Specific test
pytest src/gateway/test_smtp.py::test_send_email_validates_address

# With coverage
pytest --cov=src --cov-report=html
```

**CI/CD** (GitHub Actions)

Tests run automatically on:
- Every push
- Every pull request
- Daily at 2am UTC

If tests fail, PR cannot merge.

### Integration Testing

**Manual Test Scenarios**

Before release, manually test:

1. Install on fresh Ubuntu 22.04
2. Run first-time setup wizard
3. Send email to Gmail account
4. Receive email from Outlook
5. Compose with attachment (5MB file)
6. Search for old message
7. Backup and restore
8. Update to new version

Document results in release checklist.

## Documentation

### What Gets Documented

**Code Level**
- All public functions (docstrings)
- All classes (docstrings)
- All modules (top-level docstring)
- Complex algorithms (inline comments)

**Project Level**
- Architecture decisions
- API reference
- User guides
- Installation instructions
- Troubleshooting
- Changelog

### Documentation Standards

**Docstrings**: Google style

```python
def calculate_spam_score(message: Message) -> float:
    """Calculate spam probability for a message.
    
    Uses Bayesian classification based on message content,
    sender reputation, and header analysis.
    
    Args:
        message: The email message to analyze
        
    Returns:
        Spam score between 0.0 (ham) and 1.0 (spam)
        
    Example:
        >>> msg = Message(subject="Get rich quick!")
        >>> calculate_spam_score(msg)
        0.95
    """
```

**Markdown Files**: Clear structure

- One H1 per document
- Use tables for comparisons
- Code blocks with language specified
- Links to related documents
- Update date at top

### Keeping Docs Updated

**When Code Changes**
- Update docstrings immediately
- Update API docs if public interface changes
- Update guides if user workflow changes
- Update changelog

**Review Process**
- Docs reviewed in PR same as code
- Outdated docs = failed review
- No PR merge without doc updates

## Build Process

### Building Locally

**Development Build**
```bash
# Install in development mode
pip install -e .

# Run from source
python -m unitmail.client
```

**Package Build**
```bash
# Build all packages
make build

# Or specific package
make build-deb
make build-rpm
make build-appimage
```

### Build Scripts

All build scripts in `/scripts`:

- `s001_install_deps.sh` - Install build dependencies
- `s002_build_deb.sh` - Build Debian package
- `s003_build_rpm.sh` - Build RPM package
- `s004_build_appimage.sh` - Build AppImage
- `s005_run_tests.sh` - Run full test suite
- `s006_check_style.sh` - Run linters

Scripts are numbered for execution order.

### Versioning

**Format**: MAJOR.MINOR.PATCH

**When to Bump**
- MAJOR: Breaking changes (API incompatible)
- MINOR: New features (backward compatible)
- PATCH: Bug fixes only

**Version Files**
- `src/unitmail/__version__.py` - Single source of truth
- `setup.py` - Reads from __version__.py
- `debian/changelog` - Updated on release
- `CHANGELOG.md` - Human-readable changes

### Release Process

**Steps**

1. Update version in `__version__.py`
2. Update `CHANGELOG.md`
3. Create release branch: `release/v1.2.3`
4. Run full test suite
5. Build all packages
6. Test packages on clean systems
7. Merge to main
8. Tag release: `v1.2.3`
9. Build final packages
10. Create GitHub release
11. Upload packages
12. Announce release

**Release Checklist**

```markdown
- [ ] Version bumped
- [ ] Changelog updated
- [ ] All tests pass
- [ ] Packages build successfully
- [ ] Manual testing completed
- [ ] Documentation reviewed
- [ ] Security scan clean
- [ ] Release notes written
- [ ] Tagged in git
- [ ] Packages uploaded
- [ ] Announcement sent
```

## Dependency Management

### Adding Dependencies

**Before Adding**

Ask:
1. Is this really needed?
2. Is it actively maintained?
3. What's the license?
4. How many dependencies does it have?
5. Is there a lighter alternative?

**Approval Required**

Dependencies need approval before adding. Create issue with:
- Why it's needed
- Alternatives considered
- License compatibility
- Maintenance status
- Size impact

**No Approval Needed**

Standard tools:
- pytest, black, flake8, mypy
- Standard library only
- GTK/PyGObject (project requirement)

### Security

**Dependency Scanning**

Run weekly:
```bash
pip-audit
safety check
```

**Updating**

- Review updates monthly
- Test before updating
- Update one at a time
- Document breaking changes

**Pinning**

`requirements.txt`:
```
# Exact versions for reproducibility
flask==2.3.0
sqlalchemy==2.0.0
cryptography==40.0.0
```

`requirements-dev.txt`:
```
# Can use ranges for dev tools
pytest>=7.0.0,<8.0.0
black>=23.0.0
```

## Code Review

### Review Checklist

**Functionality**
- [ ] Does it work?
- [ ] Does it solve the problem?
- [ ] Are edge cases handled?
- [ ] Is error handling present?

**Code Quality**
- [ ] Is it readable?
- [ ] Is it maintainable?
- [ ] Are names clear?
- [ ] Is it properly structured?

**Testing**
- [ ] Are there tests?
- [ ] Do tests cover edge cases?
- [ ] Do all tests pass?
- [ ] Is coverage maintained?

**Documentation**
- [ ] Are docstrings present?
- [ ] Is documentation updated?
- [ ] Are complex parts explained?

**Security**
- [ ] No secrets in code?
- [ ] Input validation present?
- [ ] SQL injection prevented?
- [ ] XSS prevented?

### Providing Feedback

**Good Feedback**
```
The error handling here could be more specific. Instead of catching 
all exceptions, catch SMTPException and let others propagate.

Suggested change:
try:
    smtp.send(message)
except SMTPException as e:
    logger.error(f"SMTP failed: {e}")
    raise
```

**Bad Feedback**
```
This is wrong.
```

**Guidelines**
- Be specific
- Suggest solutions
- Ask questions if unclear
- Focus on code, not person
- Assume good intent

### Responding to Feedback

**If You Agree**
- Make the change
- Reply "Fixed in latest commit"

**If You Disagree**
- Explain your reasoning
- Provide alternative
- Be open to discussion
- Defer to maintainer if deadlock

## Issue Tracking

### Issue Labels

**Type**
- `bug` - Something broken
- `feature` - New functionality
- `enhancement` - Improve existing
- `docs` - Documentation only
- `question` - Need clarification

**Priority**
- `critical` - Blocks users, fix immediately
- `high` - Important, fix soon
- `medium` - Normal priority
- `low` - Nice to have

**Status**
- `needs-triage` - New, not reviewed
- `accepted` - Will be worked on
- `in-progress` - Someone is working on it
- `blocked` - Can't proceed yet

### Issue Templates

**Bug Report**
```markdown
## Description
Brief description of bug

## Steps to Reproduce
1. Step one
2. Step two
3. See error

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: Ubuntu 22.04
- Version: 1.0.0
- Install method: AppImage
```

**Feature Request**
```markdown
## Problem
What problem does this solve?

## Proposed Solution
How should it work?

## Alternatives Considered
What other approaches could work?

## Additional Context
Any other relevant information
```

## Security

### Security Practices

**During Development**
- Never commit secrets
- Use environment variables for config
- Validate all user input
- Parameterize SQL queries
- Use prepared statements
- Sanitize output

**Code Review**
- Check for SQL injection
- Check for XSS
- Check for path traversal
- Check for command injection
- Verify authentication
- Verify authorization

### Handling Security Issues

**If You Find One**
1. Do NOT create public issue
2. Email security@unitmail.com
3. Include details
4. Wait for response

**If Reported to You**
1. Acknowledge within 24 hours
2. Assess severity
3. Develop fix
4. Test thoroughly
5. Release patch
6. Notify reporters
7. Publish advisory

**Disclosure Timeline**
- Day 0: Reported
- Day 1: Acknowledged
- Day 7: Fix developed
- Day 14: Patch released
- Day 30: Public disclosure

## Development Workflow

### Daily Workflow

**Starting Work**
```bash
# Update local repository
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/add-pgp-support

# Install latest dependencies
pip install -r requirements.txt

# Run tests to verify clean state
pytest
```

**During Work**
```bash
# Make changes
vim src/crypto/pgp.py

# Run relevant tests
pytest src/crypto/test_pgp.py

# Run style checks
black src/crypto/pgp.py
flake8 src/crypto/pgp.py

# Commit atomic changes
git add src/crypto/pgp.py
git commit -m "feat: add PGP key generation"
```

**Finishing Work**
```bash
# Run full test suite
pytest

# Push branch
git push origin feature/add-pgp-support

# Create pull request on GitHub
# Wait for review
```

### Sprint Planning

**Two Week Sprints**

**Week 1 Monday**: Sprint planning
- Review backlog
- Select issues for sprint
- Estimate effort
- Assign work

**Daily**: Stand-up (async in chat)
- What did you do yesterday?
- What will you do today?
- Any blockers?

**Week 2 Friday**: Sprint review
- Demo completed work
- Review what shipped
- What didn't get done?
- Update backlog

**Week 2 Friday**: Retrospective
- What went well?
- What could improve?
- Action items for next sprint

### Estimation

**T-Shirt Sizing**

- **XS**: 1-2 hours
- **S**: Half day
- **M**: 1-2 days
- **L**: 3-5 days
- **XL**: 1-2 weeks

If estimate is XL, break it down into smaller tasks.

### Communication

**Channels**

- GitHub Issues: Feature discussion
- Pull Requests: Code review
- Discussions: General questions
- Email: Security issues only
- IRC/Matrix: Real-time chat (optional)

**Response Times**

- Security issues: 24 hours
- Bug reports: 48 hours
- Feature requests: 1 week
- Pull requests: 3 days
- General questions: Best effort

## Continuous Integration

### GitHub Actions Workflows

**On Push/PR**
```yaml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run tests
        run: pytest --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

**On Tag (Release)**
```yaml
name: Release
on:
  push:
    tags:
      - 'v*'
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build packages
        run: make build
      - name: Create release
        uses: actions/create-release@v1
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref }}
```

**Daily Security Scan**
```yaml
name: Security
on:
  schedule:
    - cron: '0 2 * * *'
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run pip-audit
        run: pip-audit
```

### Quality Gates

**PR Cannot Merge If**
- Tests fail
- Coverage drops below 80%
- Linting errors present
- Security vulnerabilities found
- No approval from reviewer

## Troubleshooting Development Issues

### Common Problems

**Tests Fail Locally**
```bash
# Clean environment
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Clear pytest cache
rm -rf .pytest_cache
rm -rf __pycache__

# Run again
pytest
```

**Import Errors**
```bash
# Install package in development mode
pip install -e .

# Verify installation
python -c "import unitmail; print(unitmail.__version__)"
```

**Black/Flake8 Conflicts**
```bash
# Black is authoritative for formatting
black src/

# Then check flake8
flake8 src/
```

**Merge Conflicts**
```bash
# Update your branch
git checkout feature/my-feature
git fetch origin
git rebase origin/develop

# Resolve conflicts
# ... fix conflicts in files ...

git add <resolved-files>
git rebase --continue
```

### Getting Help

**Before Asking**
1. Search existing issues
2. Check documentation
3. Read error message carefully
4. Try on clean environment

**When Asking**
- Provide full error message
- Include environment details
- Show what you tried
- Include minimal reproduction

## Conclusion

This methodology focuses on:
- Simple, clear processes
- Quality over speed
- Testing everything
- Documenting thoroughly
- Reviewing carefully

Follow these guidelines and unitMail will be maintainable, reliable, and easy to contribute to.

Questions or suggestions? Open an issue.
