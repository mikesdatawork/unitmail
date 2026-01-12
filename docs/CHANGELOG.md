# Changelog

All notable changes to unitMail will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Version Format

Each release section includes the following categories:

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Features that will be removed in future versions
- **Removed**: Features removed in this version
- **Fixed**: Bug fixes
- **Security**: Security-related changes and vulnerability fixes

---

## [Unreleased]

### Added
- Placeholder for upcoming features

### Changed
- Placeholder for upcoming changes

### Fixed
- Placeholder for upcoming fixes

---

## [0.1.0] - 2026-01-11

### Added

#### Core Infrastructure
- Initial project structure with Python 3.11+ support
- Supabase integration for cloud database functionality
- Configuration management with TOML file support and environment variables
- Pydantic-based settings validation with type safety
- Database migration system with version tracking
- Custom exception hierarchy for error handling

#### Database Schema
- Users table with email validation and secure password hashing
- Messages table with full email metadata storage
- Folders table with hierarchical structure support
- Contacts table with optional PGP key storage
- Queue table for outbound email management
- Config table for user-specific settings
- Mesh peers table for WireGuard network configuration

#### Configuration
- Example configuration file (`settings.example.toml`)
- Support for SMTP, API, DNS, mesh, and crypto settings
- Logging configuration with JSON output option
- Environment-based configuration overrides

#### Documentation
- Project overview and philosophy
- System architecture documentation
- Technical specifications
- Requirements document with MoSCoW prioritization
- Development methodology guidelines
- Cost control matrix

#### Development
- pytest-based test infrastructure
- Black code formatting configuration
- Flake8 linting rules
- MyPy static type checking
- Coverage reporting setup
- Playwright integration for E2E testing

### Changed
- N/A (initial release)

### Deprecated
- N/A (initial release)

### Removed
- N/A (initial release)

### Fixed
- N/A (initial release)

### Security
- Bcrypt/Argon2 password hashing implementation
- JWT token-based authentication design
- Row-level security policies for database tables
- TLS 1.2+ requirement for all connections
- DKIM, SPF, and DMARC support planned

---

## Release Notes Template

For future releases, use this template:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- Feature 1 description
- Feature 2 description

### Changed
- Change 1 description
- Change 2 description

### Deprecated
- Deprecation 1 description

### Removed
- Removal 1 description

### Fixed
- Fix 1 description ([#issue-number](link))
- Fix 2 description ([#issue-number](link))

### Security
- Security fix 1 description ([CVE-XXXX-XXXXX](link))
```

---

## Upcoming Releases

### [0.2.0] - Planned Q1 2026

**Focus**: GTK Client MVP

- GTK 4 desktop application
- Basic compose and read functionality
- Folder management UI
- Settings panel
- Gateway connectivity

### [0.3.0] - Planned Q2 2026

**Focus**: Gateway Service

- SMTP server implementation
- Email queue processing
- DKIM signing
- API endpoints for client communication
- WebSocket real-time updates

### [0.4.0] - Planned Q2 2026

**Focus**: Search and Encryption

- Full-text search implementation
- PGP key management
- Message encryption/decryption
- Contact PGP key import

### [0.5.0] - Planned Q3 2026

**Focus**: Mesh Networking

- WireGuard integration
- Peer discovery
- Direct mesh routing
- Offline capability

### [1.0.0] - Planned Q3 2026

**Focus**: Production Ready

- Complete feature set
- Performance optimization
- Security audit completed
- Documentation finalized
- Multi-distribution packages

---

## Migration Guides

### Migrating from 0.1.x to 0.2.x

*This section will be updated when 0.2.0 is released.*

```bash
# Backup your data before upgrading
unitmail-backup --output ~/unitmail-backup-$(date +%Y%m%d).tar.gz

# Update the package
pip install --upgrade unitmail

# Run database migrations
python scripts/migrate.py up
```

---

## Links

- [GitHub Releases](https://github.com/unitmail/unitmail/releases)
- [Documentation](https://docs.unitmail.org)
- [Issue Tracker](https://github.com/unitmail/unitmail/issues)
- [Contributing Guide](/docs/CONTRIBUTING.md)

[Unreleased]: https://github.com/unitmail/unitmail/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/unitmail/unitmail/releases/tag/v0.1.0
