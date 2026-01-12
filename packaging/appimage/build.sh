#!/bin/bash
#
# Build script for UnitMail AppImage
# Usage: ./build.sh [version]
#
# Requirements:
#   - linuxdeploy-x86_64.AppImage
#   - linuxdeploy-plugin-python-x86_64.AppImage (optional, for bundling Python)
#   - appimagetool (optional, for manual AppImage creation)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/packaging/build/appimage"
APPDIR="$BUILD_DIR/AppDir"

# Extract version from source if not provided
if [ -z "$VERSION" ] && [ -z "$1" ]; then
    VERSION=$(grep -oP '__version__\s*=\s*"\K[^"]+' "$PROJECT_ROOT/src/unitmail/__version__.py" 2>/dev/null || echo "0.1.0")
elif [ -n "$1" ]; then
    VERSION="$1"
fi

APPIMAGE_NAME="UnitMail-$VERSION-x86_64.AppImage"

echo "=========================================="
echo "Building UnitMail AppImage"
echo "Version: $VERSION"
echo "=========================================="

# Clean previous build
echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$APPDIR"

# Create AppDir structure
echo "Creating AppDir structure..."
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib/python3/site-packages"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR/usr/share/metainfo"

# Install the application
echo "Installing UnitMail..."
cd "$PROJECT_ROOT"

# Create a virtual environment for bundling
python3 -m venv "$BUILD_DIR/venv"
source "$BUILD_DIR/venv/bin/activate"

# Install dependencies and the package
pip install --upgrade pip setuptools wheel
pip install .

# Copy Python and site-packages to AppDir
echo "Copying Python environment..."
cp -r "$BUILD_DIR/venv/lib/python"*"/site-packages/"* "$APPDIR/usr/lib/python3/site-packages/"

# Copy the source directly as well for module imports
cp -r "$PROJECT_ROOT/src/"* "$APPDIR/usr/lib/python3/site-packages/"

deactivate

# Copy Python interpreter (use system Python as base)
PYTHON_PATH=$(which python3)
cp "$PYTHON_PATH" "$APPDIR/usr/bin/python3"

# Create a wrapper script
cat > "$APPDIR/usr/bin/unitmail" << 'WRAPPER_EOF'
#!/bin/bash
SELF_DIR="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$SELF_DIR/../lib/python3/site-packages:$PYTHONPATH"
exec "$SELF_DIR/python3" -m unitmail "$@"
WRAPPER_EOF
chmod +x "$APPDIR/usr/bin/unitmail"

# Copy desktop file
echo "Installing desktop file..."
cp "$SCRIPT_DIR/unitmail.desktop" "$APPDIR/usr/share/applications/"
cp "$SCRIPT_DIR/unitmail.desktop" "$APPDIR/"

# Copy AppRun
echo "Installing AppRun..."
cp "$SCRIPT_DIR/AppRun" "$APPDIR/"
chmod +x "$APPDIR/AppRun"

# Create/copy icon
echo "Creating icon..."
if [ -f "$SCRIPT_DIR/unitmail.png" ]; then
    cp "$SCRIPT_DIR/unitmail.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/"
    cp "$SCRIPT_DIR/unitmail.png" "$APPDIR/"
else
    # Create a placeholder icon (simple SVG converted to PNG would be better)
    # For now, create a simple placeholder
    cat > "$APPDIR/unitmail.svg" << 'ICON_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg width="256" height="256" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg">
  <rect width="256" height="256" rx="32" fill="#4A90D9"/>
  <path d="M48 80 L128 140 L208 80 L208 176 L48 176 Z" fill="white" stroke="white" stroke-width="8" stroke-linejoin="round"/>
  <path d="M48 80 L128 140 L208 80" fill="none" stroke="white" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
ICON_EOF
    # Try to convert to PNG if convert is available
    if command -v convert &> /dev/null; then
        convert "$APPDIR/unitmail.svg" -resize 256x256 "$APPDIR/unitmail.png"
        cp "$APPDIR/unitmail.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/"
    else
        # Just use the SVG
        cp "$APPDIR/unitmail.svg" "$APPDIR/usr/share/icons/hicolor/256x256/apps/unitmail.svg"
    fi
fi

# Create AppStream metadata
echo "Creating AppStream metadata..."
cat > "$APPDIR/usr/share/metainfo/unitmail.appdata.xml" << APPDATA_EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>io.unitmail.UnitMail</id>
  <name>UnitMail</name>
  <summary>Modern email client with encryption support</summary>
  <metadata_license>MIT</metadata_license>
  <project_license>MIT</project_license>
  <description>
    <p>
      UnitMail is a modern email client that provides end-to-end encryption
      support using GPG/PGP. It features a GTK-based graphical interface,
      integrated SMTP server capabilities, and seamless encryption/decryption
      of messages.
    </p>
    <p>Features:</p>
    <ul>
      <li>End-to-end encryption with GPG/PGP</li>
      <li>Modern GTK3 user interface</li>
      <li>Built-in SMTP server and client</li>
      <li>Contact management</li>
      <li>Folder organization</li>
      <li>Search functionality</li>
    </ul>
  </description>
  <launchable type="desktop-id">unitmail.desktop</launchable>
  <url type="homepage">https://github.com/unitmail/unitmail</url>
  <url type="bugtracker">https://github.com/unitmail/unitmail/issues</url>
  <provides>
    <binary>unitmail</binary>
  </provides>
  <releases>
    <release version="$VERSION" date="$(date +%Y-%m-%d)"/>
  </releases>
  <content_rating type="oars-1.1"/>
</component>
APPDATA_EOF

# Build the AppImage
echo "Building AppImage..."
cd "$BUILD_DIR"

# Check for linuxdeploy
LINUXDEPLOY=""
TOOLS_DIR="$PROJECT_ROOT/tools"

if [ -f "$TOOLS_DIR/linuxdeploy-x86_64.AppImage" ]; then
    LINUXDEPLOY="$TOOLS_DIR/linuxdeploy-x86_64.AppImage"
elif command -v linuxdeploy &> /dev/null; then
    LINUXDEPLOY="linuxdeploy"
elif [ -f "./linuxdeploy-x86_64.AppImage" ]; then
    LINUXDEPLOY="./linuxdeploy-x86_64.AppImage"
fi

if [ -n "$LINUXDEPLOY" ]; then
    echo "Using linuxdeploy: $LINUXDEPLOY"

    # Use linuxdeploy to create AppImage
    ARCH=x86_64 "$LINUXDEPLOY" \
        --appdir "$APPDIR" \
        --desktop-file "$APPDIR/usr/share/applications/unitmail.desktop" \
        --output appimage

    # Rename the output
    mv UnitMail*.AppImage "$APPIMAGE_NAME" 2>/dev/null || \
    mv *.AppImage "$APPIMAGE_NAME" 2>/dev/null || true
else
    echo "linuxdeploy not found. Trying appimagetool..."

    # Check for appimagetool
    APPIMAGETOOL=""
    if [ -f "$TOOLS_DIR/appimagetool-x86_64.AppImage" ]; then
        APPIMAGETOOL="$TOOLS_DIR/appimagetool-x86_64.AppImage"
    elif command -v appimagetool &> /dev/null; then
        APPIMAGETOOL="appimagetool"
    fi

    if [ -n "$APPIMAGETOOL" ]; then
        echo "Using appimagetool: $APPIMAGETOOL"
        ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_NAME"
    else
        echo ""
        echo "WARNING: Neither linuxdeploy nor appimagetool found."
        echo "The AppDir has been created but no AppImage was generated."
        echo ""
        echo "To create the AppImage, install one of:"
        echo "  1. linuxdeploy: https://github.com/linuxdeploy/linuxdeploy/releases"
        echo "  2. appimagetool: https://github.com/AppImage/AppImageKit/releases"
        echo ""
        echo "Then run:"
        echo "  linuxdeploy --appdir $APPDIR --output appimage"
        echo "  OR"
        echo "  appimagetool $APPDIR $APPIMAGE_NAME"
    fi
fi

# Copy to dist
echo "Copying to dist..."
mkdir -p "$PROJECT_ROOT/dist"
if [ -f "$APPIMAGE_NAME" ]; then
    cp "$APPIMAGE_NAME" "$PROJECT_ROOT/dist/"
fi

echo ""
echo "=========================================="
echo "Build complete!"
echo "AppDir: $APPDIR"
if [ -f "$PROJECT_ROOT/dist/$APPIMAGE_NAME" ]; then
    echo "AppImage: $PROJECT_ROOT/dist/$APPIMAGE_NAME"
    ls -la "$PROJECT_ROOT/dist/$APPIMAGE_NAME"
else
    echo "AppDir created at: $APPDIR"
    echo "(No AppImage tool found - AppImage not created)"
fi
echo "=========================================="
