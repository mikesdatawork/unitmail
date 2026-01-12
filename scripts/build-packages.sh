#!/bin/bash
#
# Master build script for UnitMail packages
# Builds DEB, RPM, and AppImage packages
#
# Usage:
#   ./build-packages.sh [options] [formats...]
#
# Options:
#   -v, --version VERSION   Specify version (default: from __version__.py)
#   -o, --output DIR        Output directory (default: dist/)
#   -c, --clean             Clean build directories before building
#   -h, --help              Show this help message
#
# Formats:
#   all                     Build all formats (default)
#   deb                     Build DEB package only
#   rpm                     Build RPM package only
#   appimage                Build AppImage only
#   python                  Build Python wheel/sdist only
#
# Examples:
#   ./build-packages.sh                  # Build all formats
#   ./build-packages.sh deb rpm          # Build DEB and RPM only
#   ./build-packages.sh -v 1.0.0 all     # Build all with version 1.0.0
#   ./build-packages.sh -c appimage      # Clean and build AppImage
#

set -e

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default values
VERSION=""
OUTPUT_DIR="$PROJECT_ROOT/dist"
CLEAN=false
FORMATS=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "${BLUE}=========================================="
    echo -e "$1"
    echo -e "==========================================${NC}"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Show help
show_help() {
    head -40 "$0" | tail -35 | sed 's/^#//' | sed 's/^ //'
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        all|deb|rpm|appimage|python)
            FORMATS+=("$1")
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use -h or --help for usage information."
            exit 1
            ;;
    esac
done

# Default to all formats if none specified
if [ ${#FORMATS[@]} -eq 0 ]; then
    FORMATS=("all")
fi

# Expand "all" to individual formats
if [[ " ${FORMATS[*]} " =~ " all " ]]; then
    FORMATS=("python" "deb" "rpm" "appimage")
fi

# Extract version from source if not provided
if [ -z "$VERSION" ]; then
    VERSION_FILE="$PROJECT_ROOT/src/unitmail/__version__.py"
    if [ -f "$VERSION_FILE" ]; then
        VERSION=$(grep -oP '__version__\s*=\s*"\K[^"]+' "$VERSION_FILE" 2>/dev/null || echo "0.1.0")
    else
        VERSION="0.1.0"
    fi
fi

print_header "UnitMail Package Builder"
echo ""
print_info "Version: $VERSION"
print_info "Output: $OUTPUT_DIR"
print_info "Formats: ${FORMATS[*]}"
echo ""

# Clean if requested
if [ "$CLEAN" = true ]; then
    print_info "Cleaning build directories..."
    rm -rf "$PROJECT_ROOT/packaging/build"
    rm -rf "$PROJECT_ROOT/dist"
    rm -rf "$PROJECT_ROOT/build"
    rm -rf "$PROJECT_ROOT"/*.egg-info
    rm -rf "$PROJECT_ROOT/src"/*.egg-info
    find "$PROJECT_ROOT" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    print_success "Clean complete"
    echo ""
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Track results
declare -A BUILD_RESULTS

# Build Python package
build_python() {
    print_header "Building Python Package"

    cd "$PROJECT_ROOT"

    # Check for build module
    if ! python3 -c "import build" 2>/dev/null; then
        print_info "Installing build module..."
        pip install build
    fi

    # Build
    python3 -m build

    # Copy to output
    cp dist/*.whl "$OUTPUT_DIR/" 2>/dev/null || true
    cp dist/*.tar.gz "$OUTPUT_DIR/" 2>/dev/null || true

    if ls "$OUTPUT_DIR"/*.whl 1> /dev/null 2>&1; then
        print_success "Python package built successfully"
        BUILD_RESULTS["python"]="SUCCESS"
    else
        print_error "Python package build failed"
        BUILD_RESULTS["python"]="FAILED"
        return 1
    fi
}

# Build DEB package
build_deb() {
    print_header "Building DEB Package"

    # Check for required tools
    if ! command -v dpkg-buildpackage &> /dev/null; then
        print_warning "dpkg-buildpackage not found. Skipping DEB build."
        print_info "Install with: sudo apt-get install devscripts debhelper dh-python"
        BUILD_RESULTS["deb"]="SKIPPED"
        return 0
    fi

    # Run DEB build script
    if [ -f "$PROJECT_ROOT/packaging/deb/build.sh" ]; then
        "$PROJECT_ROOT/packaging/deb/build.sh" "$VERSION"

        if ls "$OUTPUT_DIR"/*.deb 1> /dev/null 2>&1; then
            print_success "DEB package built successfully"
            BUILD_RESULTS["deb"]="SUCCESS"
        else
            print_error "DEB package build failed"
            BUILD_RESULTS["deb"]="FAILED"
            return 1
        fi
    else
        print_error "DEB build script not found"
        BUILD_RESULTS["deb"]="FAILED"
        return 1
    fi
}

# Build RPM package
build_rpm() {
    print_header "Building RPM Package"

    # Check for required tools
    if ! command -v rpmbuild &> /dev/null; then
        print_warning "rpmbuild not found. Skipping RPM build."
        print_info "Install with: sudo dnf install rpm-build rpmdevtools"
        BUILD_RESULTS["rpm"]="SKIPPED"
        return 0
    fi

    # Run RPM build script
    if [ -f "$PROJECT_ROOT/packaging/rpm/build.sh" ]; then
        "$PROJECT_ROOT/packaging/rpm/build.sh" "$VERSION"

        if ls "$OUTPUT_DIR"/*.rpm 1> /dev/null 2>&1; then
            print_success "RPM package built successfully"
            BUILD_RESULTS["rpm"]="SUCCESS"
        else
            print_error "RPM package build failed"
            BUILD_RESULTS["rpm"]="FAILED"
            return 1
        fi
    else
        print_error "RPM build script not found"
        BUILD_RESULTS["rpm"]="FAILED"
        return 1
    fi
}

# Build AppImage
build_appimage() {
    print_header "Building AppImage"

    # Run AppImage build script
    if [ -f "$PROJECT_ROOT/packaging/appimage/build.sh" ]; then
        VERSION="$VERSION" "$PROJECT_ROOT/packaging/appimage/build.sh"

        if ls "$OUTPUT_DIR"/*.AppImage 1> /dev/null 2>&1; then
            print_success "AppImage built successfully"
            BUILD_RESULTS["appimage"]="SUCCESS"
        else
            # Check if AppDir was created (tool might not be available)
            if [ -d "$PROJECT_ROOT/packaging/build/appimage/AppDir" ]; then
                print_warning "AppImage tool not available, but AppDir was created"
                BUILD_RESULTS["appimage"]="PARTIAL"
            else
                print_error "AppImage build failed"
                BUILD_RESULTS["appimage"]="FAILED"
                return 1
            fi
        fi
    else
        print_error "AppImage build script not found"
        BUILD_RESULTS["appimage"]="FAILED"
        return 1
    fi
}

# Run builds
FAILED=false
for format in "${FORMATS[@]}"; do
    case $format in
        python)
            build_python || FAILED=true
            ;;
        deb)
            build_deb || FAILED=true
            ;;
        rpm)
            build_rpm || FAILED=true
            ;;
        appimage)
            build_appimage || FAILED=true
            ;;
    esac
    echo ""
done

# Generate checksums
print_header "Generating Checksums"
cd "$OUTPUT_DIR"
if ls *.whl *.tar.gz *.deb *.rpm *.AppImage 1> /dev/null 2>&1; then
    sha256sum *.whl *.tar.gz *.deb *.rpm *.AppImage 2>/dev/null > SHA256SUMS.txt || true
    print_success "Checksums written to SHA256SUMS.txt"
else
    print_warning "No packages found for checksum generation"
fi

# Summary
print_header "Build Summary"
echo ""
echo "Version: $VERSION"
echo "Output: $OUTPUT_DIR"
echo ""
echo "Results:"
for format in "${!BUILD_RESULTS[@]}"; do
    result="${BUILD_RESULTS[$format]}"
    case $result in
        SUCCESS)
            echo -e "  ${format}: ${GREEN}${result}${NC}"
            ;;
        PARTIAL|SKIPPED)
            echo -e "  ${format}: ${YELLOW}${result}${NC}"
            ;;
        FAILED)
            echo -e "  ${format}: ${RED}${result}${NC}"
            ;;
    esac
done

echo ""
echo "Packages:"
ls -la "$OUTPUT_DIR" 2>/dev/null || echo "  (no packages)"

echo ""
if [ "$FAILED" = true ]; then
    print_warning "Some builds failed. Check the output above for details."
    exit 1
else
    print_success "All requested builds completed!"
fi
