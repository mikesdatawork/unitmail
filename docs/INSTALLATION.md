# unitMail Installation Guide

This guide covers the installation of unitMail on Linux systems. unitMail provides an independent email system with a GTK desktop client and optional gateway service.

## Table of Contents

- [System Requirements](#system-requirements)
- [Installation Methods](#installation-methods)
  - [Package Installation (Recommended)](#package-installation-recommended)
  - [AppImage Installation](#appimage-installation)
  - [Building from Source](#building-from-source)
- [Dependencies](#dependencies)
- [First-Run Setup](#first-run-setup)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Hardware

| Component | Requirement |
|-----------|-------------|
| CPU | x86_64 or ARM64, 1 GHz |
| RAM | 1 GB available |
| Disk | 5 GB free space |
| Network | Any internet connection |

### Recommended Hardware

| Component | Recommendation |
|-----------|----------------|
| CPU | 2+ cores |
| RAM | 2 GB available |
| Disk | 10 GB free space |
| Network | Broadband (5 Mbps+) |

### Supported Operating Systems

- **Ubuntu** 22.04 LTS or later
- **Debian** 12 (Bookworm) or later
- **Fedora** 38 or later
- **RHEL/CentOS** 9 or later
- **Arch Linux** (current)
- Other Linux distributions may work but are not officially tested

### Software Requirements

- Python 3.11 or later
- GTK 4.0 or later
- SQLite 3.35 or later
- OpenSSL 3.0 or later
- systemd (for service management)

---

## Installation Methods

### Package Installation (Recommended)

#### Ubuntu/Debian

```bash
# Add the unitMail repository
curl -fsSL https://packages.unitmail.org/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/unitmail-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/unitmail-archive-keyring.gpg] https://packages.unitmail.org/apt stable main" | sudo tee /etc/apt/sources.list.d/unitmail.list

# Update package list and install
sudo apt update
sudo apt install unitmail
```

#### Fedora/RHEL

```bash
# Add the unitMail repository
sudo dnf config-manager --add-repo https://packages.unitmail.org/rpm/unitmail.repo

# Install unitMail
sudo dnf install unitmail
```

#### Arch Linux (AUR)

```bash
# Using yay (or your preferred AUR helper)
yay -S unitmail

# Or manually
git clone https://aur.archlinux.org/unitmail.git
cd unitmail
makepkg -si
```

### AppImage Installation

AppImage provides a single-file executable that works on most Linux distributions.

```bash
# Download the AppImage
wget https://releases.unitmail.org/latest/unitmail-latest-x86_64.AppImage

# Make it executable
chmod +x unitmail-latest-x86_64.AppImage

# Run unitMail
./unitmail-latest-x86_64.AppImage
```

To integrate with your desktop environment:

```bash
# Move to a permanent location
sudo mv unitmail-latest-x86_64.AppImage /opt/unitmail/

# Create a desktop entry
cat << 'EOF' | sudo tee /usr/share/applications/unitmail.desktop
[Desktop Entry]
Name=unitMail
Comment=Independent Email Client
Exec=/opt/unitmail/unitmail-latest-x86_64.AppImage
Icon=unitmail
Type=Application
Categories=Network;Email;
EOF
```

### Building from Source

Building from source gives you the latest development version and allows for customization.

#### Prerequisites

Install build dependencies:

```bash
# Ubuntu/Debian
sudo apt install python3.11 python3.11-venv python3.11-dev \
    libgirepository1.0-dev libcairo2-dev pkg-config \
    libgtk-4-dev gir1.2-gtk-4.0 git build-essential

# Fedora/RHEL
sudo dnf install python3.11 python3.11-devel \
    gobject-introspection-devel cairo-devel pkg-config \
    gtk4-devel git gcc make

# Arch Linux
sudo pacman -S python python-pip gtk4 gobject-introspection \
    cairo pkgconf git base-devel
```

#### Clone and Build

```bash
# Clone the repository
git clone https://github.com/unitmail/unitmail.git
cd unitmail

# Create and activate virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run the application
python -m unitmail
```

#### System-Wide Installation from Source

```bash
# Build the package
pip install build
python -m build

# Install the built package
sudo pip install dist/unitmail-*.whl

# Or use the setup script
sudo python setup.py install
```

---

## Dependencies

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Runtime environment |
| Flask | 3.0+ | API server framework |
| PyGObject | 3.46+ | GTK bindings |
| python-gnupg | 0.5.2+ | PGP encryption |
| PyJWT | 2.8+ | JWT authentication |
| cryptography | 41.0+ | Cryptographic operations |
| aiosmtpd | 1.4+ | SMTP server |
| requests | 2.31+ | HTTP client |
| pydantic | 2.0+ | Configuration validation |
| pydantic-settings | 2.0+ | Settings management |

### Optional Dependencies

| Package | Purpose |
|---------|---------|
| WireGuard | Mesh networking |
| SQLCipher | Database encryption |
| Rspamd | Spam filtering |
| ClamAV | Antivirus scanning |

### Installing Optional Dependencies

```bash
# WireGuard (for mesh networking)
sudo apt install wireguard  # Ubuntu/Debian
sudo dnf install wireguard-tools  # Fedora

# SQLCipher (for encrypted database)
sudo apt install sqlcipher libsqlcipher-dev  # Ubuntu/Debian
sudo dnf install sqlcipher sqlcipher-devel  # Fedora
```

---

## First-Run Setup

When you launch unitMail for the first time, the setup wizard guides you through configuration.

### Step 1: Welcome and Deployment Model

Choose your deployment model:

1. **VPS Gateway** (Recommended) - Uses a cloud server for email relay
2. **Direct SMTP** - For users with static IP and port 25 access
3. **Mesh Only** - For private mesh network communication

### Step 2: Network Configuration

#### For VPS Gateway:

1. Enter your VPS IP address or hostname
2. Provide API credentials if using managed gateway
3. The wizard tests connectivity automatically

#### For Direct SMTP:

1. Verify port 25 is accessible
2. Enter your static IP address
3. Configure firewall rules if prompted

### Step 3: Domain Configuration

You need a domain name to send and receive email.

1. Enter your domain (e.g., `yourdomain.com`)
2. The wizard generates required DNS records:

```dns
# MX Record
yourdomain.com.        IN  MX  10 mail.yourdomain.com.

# A Record
mail.yourdomain.com.   IN  A   YOUR_SERVER_IP

# SPF Record
yourdomain.com.        IN  TXT "v=spf1 ip4:YOUR_SERVER_IP -all"

# DKIM Record (generated automatically)
unitmail._domainkey.yourdomain.com. IN TXT "v=DKIM1; k=rsa; p=..."

# DMARC Record
_dmarc.yourdomain.com. IN TXT "v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com"
```

3. Add these records to your DNS provider
4. Click "Verify DNS" to confirm propagation

### Step 4: Account Creation

1. Enter your display name
2. Enter your email address (e.g., `you@yourdomain.com`)
3. Create a strong password (minimum 12 characters)
4. Optionally enable two-factor authentication

### Step 5: Security Settings (Optional)

- **PGP Key Generation**: Create a new key pair for end-to-end encryption
- **Database Encryption**: Enable SQLCipher for encrypted local storage
- **Mesh Network**: Join or create a private mesh network

### Step 6: Complete Setup

The wizard performs final checks:

- Port connectivity test
- DNS record validation
- SSL certificate request (Let's Encrypt)
- Service startup

---

## Troubleshooting

### Common Installation Issues

#### Python Version Error

**Problem**: "Python 3.11 or later required"

**Solution**:
```bash
# Ubuntu/Debian
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11

# Or use pyenv
curl https://pyenv.run | bash
pyenv install 3.11.7
pyenv global 3.11.7
```

#### GTK 4 Not Found

**Problem**: "Gtk 4.0 typelib not found"

**Solution**:
```bash
# Ubuntu/Debian
sudo apt install gir1.2-gtk-4.0 libgtk-4-dev

# Fedora
sudo dnf install gtk4-devel

# Arch
sudo pacman -S gtk4
```

#### Permission Denied on Port 25

**Problem**: "Permission denied: cannot bind to port 25"

**Solution**: Port 25 requires root or special capabilities:
```bash
# Option 1: Run gateway as root (not recommended for production)
sudo unitmail-gateway

# Option 2: Use capabilities (recommended)
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/unitmail-gateway

# Option 3: Use a VPS gateway (recommended for most users)
# Configure unitMail to use external gateway instead
```

#### Database Connection Error

**Problem**: "Unable to connect to Supabase"

**Solution**:
1. Verify your Supabase URL and API key in `~/.config/unitmail/settings.toml`
2. Check internet connectivity
3. Ensure your Supabase project is active

```bash
# Test connectivity
curl -I https://your-project.supabase.co/rest/v1/

# Check configuration
cat ~/.config/unitmail/settings.toml
```

### Startup Issues

#### Service Won't Start

**Problem**: unitmail-gateway service fails to start

**Solution**:
```bash
# Check service status
sudo systemctl status unitmail-gateway

# View detailed logs
sudo journalctl -u unitmail-gateway -n 50

# Common fixes:
# 1. Check port conflicts
sudo ss -tlnp | grep -E ':(25|587|465)'

# 2. Verify configuration
unitmail-gateway --check-config

# 3. Restart with debug logging
sudo systemctl stop unitmail-gateway
sudo UNITMAIL_DEBUG=true unitmail-gateway
```

#### Application Crashes on Launch

**Problem**: GTK client crashes immediately

**Solution**:
```bash
# Run with debug output
GTK_DEBUG=interactive unitmail

# Check for missing libraries
ldd $(which unitmail) | grep "not found"

# Reinstall GTK dependencies
sudo apt install --reinstall libgtk-4-1 gir1.2-gtk-4.0
```

### Network Issues

#### DNS Verification Fails

**Problem**: "DNS records not found"

**Solution**:
1. Wait for DNS propagation (up to 48 hours)
2. Verify records with external tools:

```bash
# Check MX record
dig MX yourdomain.com

# Check SPF record
dig TXT yourdomain.com

# Check DKIM record
dig TXT unitmail._domainkey.yourdomain.com

# Use online tools
# - https://mxtoolbox.com/
# - https://www.mail-tester.com/
```

#### SSL Certificate Error

**Problem**: "SSL certificate verification failed"

**Solution**:
```bash
# Renew Let's Encrypt certificate
sudo certbot renew

# Verify certificate
openssl s_client -connect mail.yourdomain.com:465

# Check certificate expiry
openssl x509 -noout -dates -in /etc/unitmail/certs/fullchain.pem
```

### Getting Help

If you continue to experience issues:

1. **Check the FAQ**: https://docs.unitmail.org/faq
2. **Search Issues**: https://github.com/unitmail/unitmail/issues
3. **Community Forum**: https://forum.unitmail.org
4. **Email Support**: support@unitmail.org (for license holders)

When reporting issues, include:

```bash
# Generate diagnostic report
unitmail --diagnostics > unitmail-diagnostics.txt
```

This includes:
- System information
- unitMail version
- Configuration (with secrets redacted)
- Recent log entries
- Network connectivity tests
