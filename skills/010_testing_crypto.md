# Skill: Testing and Cryptography

## What This Skill Does
Sets up Playwright E2E testing and cryptographic modules for email security.

## E2E Testing

### Structure
```
tests/e2e/
├── conftest.py          # Pytest fixtures
├── playwright.config.py # Browser configuration
├── pages/               # Page Object Model
│   ├── login_page.py
│   ├── inbox_page.py
│   ├── compose_page.py
│   └── contacts_page.py
├── test_auth.py
├── test_compose.py
├── test_inbox.py
└── test_contacts.py
```

### Usage
```bash
pytest tests/e2e/
pytest tests/e2e/ --browser firefox
pytest tests/e2e/ --headed  # Visible browser
```

## Cryptography Modules

### dkim.py
- `DKIMSigner` - Sign outgoing email
- `DKIMVerifier` - Verify incoming signatures
- DNS record generation

### tls.py
- `TLSConfig` - TLS 1.2+ settings
- `CertificateManager` - Cert loading/validation
- `LetsEncryptHelper` - Automated certs

### pgp.py
- `PGPManager` - Full GPG integration
- Key generation, encrypt/decrypt, sign/verify
- Keyserver operations

### dns/checker.py
- `DNSChecker` - Verify DNS configuration
- SPF, DKIM, DMARC, MX, PTR checks
- Recommendation generation
