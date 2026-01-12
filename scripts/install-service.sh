#!/bin/bash
#
# unitMail Gateway Service Installation Script
#
# This script installs and configures the unitMail gateway as a systemd service.
# It creates the necessary user, directories, and configuration files.
#
# Usage:
#   sudo ./install-service.sh [options]
#
# Options:
#   --uninstall     Remove the unitMail gateway service
#   --upgrade       Upgrade existing installation
#   --no-start      Install without starting the service
#   --help          Show this help message
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
UNITMAIL_USER="unitmail"
UNITMAIL_GROUP="unitmail"
INSTALL_DIR="/opt/unitmail"
CONFIG_DIR="/etc/unitmail"
DATA_DIR="/var/lib/unitmail"
LOG_DIR="/var/log/unitmail"
SPOOL_DIR="/var/spool/unitmail"
SERVICE_NAME="unitmail-gateway"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Show help
show_help() {
    echo "unitMail Gateway Service Installation Script"
    echo ""
    echo "Usage: sudo $0 [options]"
    echo ""
    echo "Options:"
    echo "  --uninstall     Remove the unitMail gateway service"
    echo "  --upgrade       Upgrade existing installation"
    echo "  --no-start      Install without starting the service"
    echo "  --help          Show this help message"
    echo ""
    echo "Directories:"
    echo "  Install:  $INSTALL_DIR"
    echo "  Config:   $CONFIG_DIR"
    echo "  Data:     $DATA_DIR"
    echo "  Logs:     $LOG_DIR"
    echo "  Spool:    $SPOOL_DIR"
    echo ""
}

# Create unitmail user and group
create_user() {
    log_info "Creating unitmail user and group..."

    # Create group if it doesn't exist
    if ! getent group "$UNITMAIL_GROUP" > /dev/null 2>&1; then
        groupadd --system "$UNITMAIL_GROUP"
        log_success "Created group: $UNITMAIL_GROUP"
    else
        log_info "Group $UNITMAIL_GROUP already exists"
    fi

    # Create user if it doesn't exist
    if ! getent passwd "$UNITMAIL_USER" > /dev/null 2>&1; then
        useradd --system \
            --gid "$UNITMAIL_GROUP" \
            --home-dir "$DATA_DIR" \
            --shell /usr/sbin/nologin \
            --comment "unitMail Gateway Service" \
            "$UNITMAIL_USER"
        log_success "Created user: $UNITMAIL_USER"
    else
        log_info "User $UNITMAIL_USER already exists"
    fi
}

# Create required directories
create_directories() {
    log_info "Creating directories..."

    # Installation directory
    mkdir -p "$INSTALL_DIR"
    log_success "Created: $INSTALL_DIR"

    # Configuration directory
    mkdir -p "$CONFIG_DIR"
    log_success "Created: $CONFIG_DIR"

    # Data directory
    mkdir -p "$DATA_DIR"
    mkdir -p "$DATA_DIR/keys"
    mkdir -p "$DATA_DIR/db"
    log_success "Created: $DATA_DIR"

    # Log directory
    mkdir -p "$LOG_DIR"
    log_success "Created: $LOG_DIR"

    # Spool directory (for mail queue)
    mkdir -p "$SPOOL_DIR"
    mkdir -p "$SPOOL_DIR/incoming"
    mkdir -p "$SPOOL_DIR/outgoing"
    mkdir -p "$SPOOL_DIR/deferred"
    log_success "Created: $SPOOL_DIR"
}

# Set permissions
set_permissions() {
    log_info "Setting permissions..."

    # Installation directory (read-only for service)
    chown -R root:$UNITMAIL_GROUP "$INSTALL_DIR"
    chmod -R 755 "$INSTALL_DIR"

    # Configuration directory
    chown -R root:$UNITMAIL_GROUP "$CONFIG_DIR"
    chmod 750 "$CONFIG_DIR"
    # Secure sensitive config files
    if [[ -f "$CONFIG_DIR/gateway.toml" ]]; then
        chmod 640 "$CONFIG_DIR/gateway.toml"
    fi
    if [[ -f "$CONFIG_DIR/gateway.env" ]]; then
        chmod 640 "$CONFIG_DIR/gateway.env"
    fi

    # Data directory (writable)
    chown -R $UNITMAIL_USER:$UNITMAIL_GROUP "$DATA_DIR"
    chmod 750 "$DATA_DIR"
    chmod 700 "$DATA_DIR/keys"

    # Log directory (writable)
    chown -R $UNITMAIL_USER:$UNITMAIL_GROUP "$LOG_DIR"
    chmod 750 "$LOG_DIR"

    # Spool directory (writable)
    chown -R $UNITMAIL_USER:$UNITMAIL_GROUP "$SPOOL_DIR"
    chmod 750 "$SPOOL_DIR"

    log_success "Permissions set"
}

# Install Python virtual environment
install_venv() {
    log_info "Setting up Python virtual environment..."

    # Check if python3 is available
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed. Please install Python 3.10 or later."
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    log_info "Found Python $PYTHON_VERSION"

    # Create virtual environment
    python3 -m venv "$INSTALL_DIR/venv"
    log_success "Created virtual environment"

    # Upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip setuptools wheel
    log_success "Upgraded pip"

    # Install dependencies
    if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
        "$INSTALL_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
        log_success "Installed dependencies"
    fi

    # Install unitmail package
    if [[ -f "$PROJECT_DIR/setup.py" ]] || [[ -f "$PROJECT_DIR/pyproject.toml" ]]; then
        "$INSTALL_DIR/venv/bin/pip" install -e "$PROJECT_DIR"
        log_success "Installed unitmail package"
    fi
}

# Copy application files
copy_files() {
    log_info "Copying application files..."

    # Copy source files
    if [[ -d "$PROJECT_DIR/src" ]]; then
        cp -r "$PROJECT_DIR/src"/* "$INSTALL_DIR/"
        log_success "Copied source files"
    fi

    # Copy configuration templates
    if [[ -f "$PROJECT_DIR/config/settings.example.toml" ]]; then
        if [[ ! -f "$CONFIG_DIR/gateway.toml" ]]; then
            cp "$PROJECT_DIR/config/settings.example.toml" "$CONFIG_DIR/gateway.toml"
            log_success "Created configuration file"
        else
            log_info "Configuration file already exists"
        fi
    fi

    # Create environment file template
    if [[ ! -f "$CONFIG_DIR/gateway.env" ]]; then
        cat > "$CONFIG_DIR/gateway.env" << 'EOF'
# unitMail Gateway Environment Configuration
# This file contains sensitive configuration values
# Ensure this file has restricted permissions (640)

# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# API Security
API_JWT_SECRET=change-this-to-a-secure-random-string

# SMTP Settings
SMTP_HOSTNAME=mail.yourdomain.com

# DNS Settings
DNS_DKIM_SELECTOR=unitmail

# Optional: Custom paths
# UNITMAIL_DATA_DIR=/var/lib/unitmail
# UNITMAIL_LOG_DIR=/var/log/unitmail
EOF
        chmod 640 "$CONFIG_DIR/gateway.env"
        log_success "Created environment file template"
    fi
}

# Install systemd service
install_service() {
    log_info "Installing systemd service..."

    # Copy service file
    if [[ -f "$PROJECT_DIR/config/unitmail-gateway.service" ]]; then
        cp "$PROJECT_DIR/config/unitmail-gateway.service" "$SERVICE_FILE"
    else
        log_error "Service file not found: $PROJECT_DIR/config/unitmail-gateway.service"
        exit 1
    fi

    # Reload systemd
    systemctl daemon-reload
    log_success "Installed systemd service"

    # Enable service
    systemctl enable "$SERVICE_NAME"
    log_success "Enabled $SERVICE_NAME service"
}

# Start the service
start_service() {
    log_info "Starting $SERVICE_NAME service..."

    systemctl start "$SERVICE_NAME"

    # Wait for startup
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_success "$SERVICE_NAME is running"
        systemctl status "$SERVICE_NAME" --no-pager
    else
        log_error "$SERVICE_NAME failed to start"
        journalctl -u "$SERVICE_NAME" --no-pager -n 20
        exit 1
    fi
}

# Uninstall function
uninstall() {
    log_info "Uninstalling unitMail gateway service..."

    # Stop and disable service
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl stop "$SERVICE_NAME"
        log_success "Stopped service"
    fi

    if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl disable "$SERVICE_NAME"
        log_success "Disabled service"
    fi

    # Remove service file
    if [[ -f "$SERVICE_FILE" ]]; then
        rm "$SERVICE_FILE"
        systemctl daemon-reload
        log_success "Removed service file"
    fi

    # Ask about removing data
    read -p "Remove configuration and data directories? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$CONFIG_DIR"
        rm -rf "$DATA_DIR"
        rm -rf "$LOG_DIR"
        rm -rf "$SPOOL_DIR"
        rm -rf "$INSTALL_DIR"
        log_success "Removed data directories"
    else
        log_info "Data directories preserved"
    fi

    # Ask about removing user
    read -p "Remove unitmail user and group? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if getent passwd "$UNITMAIL_USER" > /dev/null 2>&1; then
            userdel "$UNITMAIL_USER"
            log_success "Removed user: $UNITMAIL_USER"
        fi
        if getent group "$UNITMAIL_GROUP" > /dev/null 2>&1; then
            groupdel "$UNITMAIL_GROUP"
            log_success "Removed group: $UNITMAIL_GROUP"
        fi
    fi

    log_success "Uninstallation complete"
}

# Upgrade function
upgrade() {
    log_info "Upgrading unitMail gateway..."

    # Stop service if running
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl stop "$SERVICE_NAME"
        log_info "Stopped service for upgrade"
    fi

    # Update files
    copy_files
    install_venv

    # Update service file
    if [[ -f "$PROJECT_DIR/config/unitmail-gateway.service" ]]; then
        cp "$PROJECT_DIR/config/unitmail-gateway.service" "$SERVICE_FILE"
        systemctl daemon-reload
        log_success "Updated service file"
    fi

    # Restart service
    systemctl start "$SERVICE_NAME"
    log_success "Upgrade complete"
}

# Main installation function
install() {
    local no_start=false

    # Parse options
    for arg in "$@"; do
        case $arg in
            --no-start)
                no_start=true
                ;;
        esac
    done

    log_info "Starting unitMail gateway installation..."
    echo ""

    create_user
    create_directories
    copy_files
    install_venv
    set_permissions
    install_service

    if [[ "$no_start" = false ]]; then
        start_service
    else
        log_info "Service installed but not started (--no-start)"
    fi

    echo ""
    log_success "Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Edit configuration: $CONFIG_DIR/gateway.toml"
    echo "  2. Set environment variables: $CONFIG_DIR/gateway.env"
    echo "  3. Generate DKIM keys and configure DNS"
    echo "  4. Start the service: sudo systemctl start $SERVICE_NAME"
    echo ""
    echo "Useful commands:"
    echo "  sudo systemctl status $SERVICE_NAME    # Check status"
    echo "  sudo systemctl restart $SERVICE_NAME   # Restart service"
    echo "  sudo journalctl -u $SERVICE_NAME -f    # View logs"
    echo ""
}

# Main entry point
main() {
    check_root

    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --uninstall)
            uninstall
            ;;
        --upgrade)
            upgrade
            ;;
        *)
            install "$@"
            ;;
    esac
}

main "$@"
