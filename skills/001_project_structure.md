# Skill: Project Structure Setup

## What This Skill Does
Creates the complete folder structure for the unitMail project following the modular architecture defined in the documentation.

## Structure Created
```
/unitmail
  /docs           - Project documentation
  /skills         - Skill documentation (this folder)
  /.agents        - Agent configurations
  /src
    /client       - GTK 4 desktop client
      /ui         - UI components (windows, dialogs)
      /models     - Data models (Message, Contact, etc.)
      /services   - Business logic services
    /gateway      - Gateway microservice
      /smtp       - SMTP send/receive handling
      /api        - REST API endpoints
      /dns        - DNS management utilities
      /crypto     - Encryption (DKIM, TLS, PGP)
    /common       - Shared utilities and config
  /tests
    /e2e          - Playwright end-to-end tests
    /unit         - pytest unit tests
  /config         - Configuration templates

## Files Created
- 14 `__init__.py` files for Python package structure
- `.gitignore` with Python and Playwright patterns

## Usage
This structure supports:
- Separation of client and gateway concerns
- Modular testing (unit + E2E)
- SQLite database with FTS5 search
- Clean deployment packaging
