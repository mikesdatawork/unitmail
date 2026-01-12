# Skill: Packaging and Documentation

## What This Skill Does
Creates distribution packages and comprehensive documentation for deployment.

## Packaging

### DEB (Debian/Ubuntu)
```
packaging/deb/
├── debian/
│   ├── control      # Package metadata
│   ├── rules        # Build instructions
│   ├── changelog    # Version history
│   └── copyright    # License
└── build.sh         # Build script
```

### RPM (Fedora/RHEL)
```
packaging/rpm/
├── unitmail.spec    # RPM spec file
└── build.sh         # Build script
```

### AppImage (Portable)
```
packaging/appimage/
├── AppRun           # Entry point
├── unitmail.desktop # Desktop entry
└── build.sh         # Build script
```

### Build All
```bash
./scripts/build-packages.sh all
./scripts/build-packages.sh deb rpm
./scripts/build-packages.sh -v 1.0.0 appimage
```

## Documentation

| File | Purpose |
|------|---------|
| INSTALLATION.md | Setup guide |
| USER_GUIDE.md | User manual |
| ADMIN_GUIDE.md | Server admin |
| API_REFERENCE.md | REST API docs |
| CONTRIBUTING.md | Dev guide |
| CHANGELOG.md | Version history |

## CI/CD Workflows

### ci.yml
- Lint, test, security scan
- Python 3.11/3.12 matrix
- Playwright E2E tests

### release.yml
- Build all packages
- Create GitHub release
- Publish to PyPI

Note: Workflows require `workflow` token scope to push.
