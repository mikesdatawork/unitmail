#!/bin/bash
#
# Build script for UnitMail RPM package
# Usage: ./build.sh [version]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/packaging/build/rpm"

# Extract version from source if not provided
if [ -z "$1" ]; then
    VERSION=$(grep -oP '__version__\s*=\s*"\K[^"]+' "$PROJECT_ROOT/src/unitmail/__version__.py" 2>/dev/null || echo "0.1.0")
else
    VERSION="$1"
fi

echo "=========================================="
echo "Building UnitMail RPM package"
echo "Version: $VERSION"
echo "=========================================="

# Check for required tools
if ! command -v rpmbuild &> /dev/null; then
    echo "ERROR: rpmbuild not found."
    echo "Install with:"
    echo "  Fedora/RHEL: sudo dnf install rpm-build rpmdevtools"
    echo "  openSUSE:    sudo zypper install rpm-build"
    exit 1
fi

# Clean previous build
echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Setup RPM build tree
echo "Setting up RPM build tree..."
if command -v rpmdev-setuptree &> /dev/null; then
    rpmdev-setuptree
else
    mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
fi

# Create source tarball
echo "Creating source tarball..."
cd "$PROJECT_ROOT"
tar czf ~/rpmbuild/SOURCES/unitmail-$VERSION.tar.gz \
    --transform "s,^\.,unitmail-$VERSION," \
    --exclude='.git' \
    --exclude='packaging/build' \
    --exclude='dist' \
    --exclude='*.egg-info' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    .

# Update spec file with version
echo "Updating spec file..."
SPEC_FILE="$SCRIPT_DIR/unitmail.spec"
TMP_SPEC=~/rpmbuild/SPECS/unitmail.spec

cp "$SPEC_FILE" "$TMP_SPEC"
sed -i "s/^Version:.*/Version:        $VERSION/" "$TMP_SPEC"

# Update changelog date
CURRENT_DATE=$(date "+%a %b %d %Y")
sed -i "s/^\* .* UnitMail Team/* $CURRENT_DATE UnitMail Team/" "$TMP_SPEC"

# Build the package
echo "Building RPM package..."
rpmbuild -bb "$TMP_SPEC"

# Copy built packages to dist
echo "Copying packages to dist..."
mkdir -p "$PROJECT_ROOT/dist"
find ~/rpmbuild/RPMS -name "*.rpm" -exec cp {} "$PROJECT_ROOT/dist/" \;

echo ""
echo "=========================================="
echo "Build complete!"
echo "Packages available in: $PROJECT_ROOT/dist/"
ls -la "$PROJECT_ROOT/dist/"*.rpm 2>/dev/null || echo "No .rpm files found"
echo "=========================================="
