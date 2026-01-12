#!/bin/bash
#
# Build script for UnitMail DEB package
# Usage: ./build.sh [version]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/packaging/build/deb"

# Extract version from source if not provided
if [ -z "$1" ]; then
    VERSION=$(grep -oP '__version__\s*=\s*"\K[^"]+' "$PROJECT_ROOT/src/unitmail/__version__.py" 2>/dev/null || echo "0.1.0")
else
    VERSION="$1"
fi

echo "=========================================="
echo "Building UnitMail DEB package"
echo "Version: $VERSION"
echo "=========================================="

# Clean previous build
echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Create source directory
SOURCE_DIR="$BUILD_DIR/unitmail-$VERSION"
echo "Creating source directory: $SOURCE_DIR"

# Copy source files
cp -r "$PROJECT_ROOT"/* "$SOURCE_DIR/" 2>/dev/null || true
cp -r "$PROJECT_ROOT"/.* "$SOURCE_DIR/" 2>/dev/null || true

# Remove git and build artifacts
rm -rf "$SOURCE_DIR/.git"
rm -rf "$SOURCE_DIR/packaging/build"
rm -rf "$SOURCE_DIR/dist"
rm -rf "$SOURCE_DIR/*.egg-info"
rm -rf "$SOURCE_DIR/src/*.egg-info"
find "$SOURCE_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$SOURCE_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

# Copy debian directory to source
cp -r "$SCRIPT_DIR/debian" "$SOURCE_DIR/"

# Create orig tarball
echo "Creating orig tarball..."
cd "$BUILD_DIR"
tar czf "unitmail_$VERSION.orig.tar.gz" "unitmail-$VERSION"

# Update changelog with version
echo "Updating changelog..."
cd "$SOURCE_DIR"
export DEBEMAIL="${DEBEMAIL:-noreply@unitmail.io}"
export DEBFULLNAME="${DEBFULLNAME:-UnitMail Team}"

# Check if dch is available
if command -v dch &> /dev/null; then
    dch --newversion "$VERSION-1" --distribution stable "Release $VERSION" 2>/dev/null || true
else
    # Manual changelog update
    sed -i "s/^unitmail ([^)]*)/unitmail ($VERSION-1)/" debian/changelog
fi

# Build the package
echo "Building DEB package..."
if command -v dpkg-buildpackage &> /dev/null; then
    dpkg-buildpackage -us -uc -b
else
    echo "ERROR: dpkg-buildpackage not found. Install devscripts and debhelper packages."
    echo "  sudo apt-get install devscripts debhelper dh-python"
    exit 1
fi

# Copy built packages to dist
echo "Copying packages to dist..."
mkdir -p "$PROJECT_ROOT/dist"
cp "$BUILD_DIR"/*.deb "$PROJECT_ROOT/dist/" 2>/dev/null || true

echo ""
echo "=========================================="
echo "Build complete!"
echo "Packages available in: $PROJECT_ROOT/dist/"
ls -la "$PROJECT_ROOT/dist/"*.deb 2>/dev/null || echo "No .deb files found"
echo "=========================================="
