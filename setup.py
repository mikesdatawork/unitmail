#!/usr/bin/env python3
"""
Setup script for UnitMail.

This is a shim that reads configuration from pyproject.toml.
For most use cases, you should use `pip install .` or `pip install -e .`
which will use pyproject.toml directly via PEP 517/518.

This file exists for backward compatibility with tools that don't
support pyproject.toml yet.
"""

import sys

if sys.version_info < (3, 11):
    sys.exit("Error: UnitMail requires Python 3.11 or higher.")

try:
    from setuptools import setup
except ImportError:
    sys.exit("Error: setuptools is required. Install it with: pip install setuptools")

# Try to read version from __version__.py for consistency
try:
    import re
    from pathlib import Path

    version_file = Path(__file__).parent / "src" / "unitmail" / "__version__.py"
    version_content = version_file.read_text(encoding="utf-8")
    version_match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', version_content, re.M)
    version = version_match.group(1) if version_match else "0.1.0"
except Exception:
    version = "0.1.0"

# Read long description from README if available
try:
    from pathlib import Path

    readme_path = Path(__file__).parent / "README.md"
    if readme_path.exists():
        long_description = readme_path.read_text(encoding="utf-8")
        long_description_content_type = "text/markdown"
    else:
        long_description = "A modern email client with encryption support"
        long_description_content_type = "text/plain"
except Exception:
    long_description = "A modern email client with encryption support"
    long_description_content_type = "text/plain"

# Core dependencies (keep in sync with pyproject.toml)
install_requires = [
    "Flask>=3.0.0",
    "supabase>=2.0.0",
    "PyGObject>=3.46.0",
    "python-gnupg>=0.5.2",
    "PyJWT>=2.8.0",
    "cryptography>=41.0.0",
    "aiosmtpd>=1.4.4",
    "requests>=2.31.0",
]

# Development dependencies
extras_require = {
    "dev": [
        "pytest>=7.4.0",
        "playwright>=1.40.0",
        "pytest-playwright>=0.4.0",
        "black>=23.0.0",
        "flake8>=6.1.0",
        "mypy>=1.7.0",
        "pytest-cov>=4.1.0",
        "pytest-asyncio>=0.21.0",
    ],
}

setup(
    name="unitmail",
    version=version,
    description="A modern email client with encryption support",
    long_description=long_description,
    long_description_content_type=long_description_content_type,
    author="UnitMail Team",
    license="MIT",
    python_requires=">=3.11",
    packages=["unitmail"],
    package_dir={"": "src"},
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "unitmail=unitmail.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Email",
    ],
    keywords=["email", "encryption", "gpg", "smtp", "client"],
)
