# unitMail Administrator Guide

This guide covers server deployment, DNS configuration, security hardening, monitoring, backup procedures, and system maintenance for unitMail administrators.

## Table of Contents

- [VPS Setup Guide](#vps-setup-guide)
- [DNS Configuration](#dns-configuration)
- [Gateway Deployment](#gateway-deployment)
- [Security Hardening](#security-hardening)
- [Monitoring and Logs](#monitoring-and-logs)
- [Backup Procedures](#backup-procedures)
- [Upgrade Process](#upgrade-process)

---

## VPS Setup Guide

The unitMail gateway requires a VPS with port 25 access for email relay functionality.

### Recommended VPS Providers

| Provider | Minimum Tier | Monthly Cost | Port 25 Status |
|----------|--------------|--------------|----------------|
| Vultr | 1 vCPU, 1GB RAM | $5 | Open by default |
| DigitalOcean | Basic Droplet | $6 | Request required |
| Linode | Nanode 1GB | $5 | Open by default |
| Hetzner | CX11 | 3.29 EUR | Open by default |

**Note**: Some providers block port 25 by default. Check their documentation or contact support to ensure SMTP access.

### Server Specifications

**Minimum Requirements**:
- 1 vCPU
- 1 GB RAM
- 10 GB SSD
- 1 TB bandwidth
- Static IPv4 address
- Port 25 accessible (inbound and outbound)

**Recommended for 100+ Users**:
- 2 vCPU
- 2 GB RAM
- 20 GB SSD
- 2 TB bandwidth
- IPv6 support

### Initial Server Setup

#### 1. Create the VPS

Choose Ubuntu Server 22.04 LTS for best compatibility.

```bash
# After SSH login, update the system
sudo apt update && sudo apt upgrade -y

# Set hostname
sudo hostnamectl set-hostname mail.yourdomain.com

# Update /etc/hosts
echo "127.0.1.1 mail.yourdomain.com mail" | sudo tee -a /etc/hosts
```

#### 2. Create unitMail User

```bash
# Create dedicated user
sudo useradd -r -s /bin/false -d /var/lib/unitmail unitmail

# Create directories
sudo mkdir -p /var/lib/unitmail /var/log/unitmail /etc/unitmail
sudo chown -R unitmail:unitmail /var/lib/unitmail /var/log/unitmail
```

#### 3. Install Dependencies

```bash
# Install required packages
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postfix \
    opendkim \
    opendkim-tools \
    certbot \
    fail2ban \
    ufw

# Install unitMail gateway
pip3 install unitmail-gateway
```

#### 4. Configure Firewall

```bash
# Enable UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (change port if using non-standard)
sudo ufw allow 22/tcp

# Allow email ports
sudo ufw allow 25/tcp    # SMTP
sudo ufw allow 465/tcp   # SMTPS
sudo ufw allow 587/tcp   # Submission
sudo ufw allow 443/tcp   # HTTPS API

# Enable firewall
sudo ufw enable

# Verify rules
sudo ufw status verbose
```

---

## DNS Configuration

Proper DNS configuration is critical for email deliverability. Misconfigured DNS causes messages to be rejected or marked as spam.

### Required DNS Records

#### MX Record

Specifies the mail server for your domain.

```dns
yourdomain.com.    IN  MX  10 mail.yourdomain.com.
```

- **Priority 10**: Lower numbers = higher priority
- **mail.yourdomain.com**: Hostname of your mail server

#### A Record

Points the mail hostname to your server's IP.

```dns
mail.yourdomain.com.    IN  A    203.0.113.50
```

Replace `203.0.113.50` with your VPS IP address.

#### PTR Record (Reverse DNS)

Maps your IP back to your hostname. Configure this in your VPS provider's control panel.

```dns
50.113.0.203.in-addr.arpa.    IN  PTR  mail.yourdomain.com.
```

**Important**: PTR record must match your mail server's hostname.

### SPF Record

Sender Policy Framework specifies which IPs can send mail for your domain.

```dns
yourdomain.com.    IN  TXT  "v=spf1 ip4:203.0.113.50 -all"
```

| Component | Meaning |
|-----------|---------|
| `v=spf1` | SPF version 1 |
| `ip4:203.0.113.50` | Authorized sending IP |
| `-all` | Reject all others (strict) |
| `~all` | Soft fail others (permissive) |

**Multiple IPs**:
```dns
yourdomain.com.    IN  TXT  "v=spf1 ip4:203.0.113.50 ip4:198.51.100.25 -all"
```

### DKIM Record

DomainKeys Identified Mail adds a cryptographic signature to emails.

#### Generate DKIM Keys

```bash
# Generate 2048-bit RSA key pair
sudo mkdir -p /etc/unitmail/keys
cd /etc/unitmail/keys

openssl genrsa -out dkim.private 2048
openssl rsa -in dkim.private -pubout -out dkim.public

# Set permissions
sudo chown unitmail:unitmail dkim.private dkim.public
sudo chmod 600 dkim.private
```

#### Extract Public Key for DNS

```bash
# Get the key (remove headers and newlines)
cat dkim.public | grep -v "^-" | tr -d '\n'
```

Output will look like:
```
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
```

#### Create DKIM DNS Record

```dns
unitmail._domainkey.yourdomain.com.    IN  TXT  (
    "v=DKIM1; k=rsa; "
    "p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA..."
)
```

- **unitmail**: The selector (matches config)
- **_domainkey**: Required subdomain
- **v=DKIM1**: DKIM version
- **k=rsa**: Key type
- **p=**: Public key

**Note**: If your key is too long, split across multiple strings:
```dns
unitmail._domainkey.yourdomain.com.    IN  TXT  (
    "v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A"
    "MIIBCgKCAQEA1234567890abcdefghijklmnop..."
    "...remainingkeydata"
)
```

### DMARC Record

Domain-based Message Authentication, Reporting and Conformance tells receivers how to handle authentication failures.

```dns
_dmarc.yourdomain.com.    IN  TXT  "v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com; ruf=mailto:dmarc@yourdomain.com; pct=100"
```

| Component | Meaning |
|-----------|---------|
| `v=DMARC1` | DMARC version |
| `p=quarantine` | Policy: quarantine failures |
| `p=reject` | Policy: reject failures (stricter) |
| `p=none` | Policy: monitor only (start here) |
| `rua=` | Aggregate report email |
| `ruf=` | Forensic report email |
| `pct=100` | Apply to 100% of messages |

**Recommended Rollout**:
1. Start with `p=none` to monitor
2. After 2 weeks, move to `p=quarantine`
3. After 1 month, move to `p=reject`

### Verify DNS Configuration

```bash
# Check MX record
dig MX yourdomain.com +short

# Check A record
dig A mail.yourdomain.com +short

# Check SPF
dig TXT yourdomain.com +short

# Check DKIM
dig TXT unitmail._domainkey.yourdomain.com +short

# Check DMARC
dig TXT _dmarc.yourdomain.com +short

# Check PTR (reverse DNS)
dig -x 203.0.113.50 +short
```

Use online tools for comprehensive testing:
- [MXToolbox](https://mxtoolbox.com/)
- [Mail Tester](https://www.mail-tester.com/)
- [DKIM Validator](https://dkimvalidator.com/)

---

## Gateway Deployment

### Configuration File

Create `/etc/unitmail/settings.toml`:

```toml
[app]
app_name = "unitMail Gateway"
environment = "production"
debug = false

[database]
url = "https://your-project.supabase.co"
key = "your-anon-key"
service_role_key = "your-service-role-key"

[smtp]
host = "0.0.0.0"
port = 25
tls_port = 465
submission_port = 587
hostname = "mail.yourdomain.com"
max_message_size = 26214400
timeout = 300
require_auth = true
tls_cert_file = "/etc/letsencrypt/live/mail.yourdomain.com/fullchain.pem"
tls_key_file = "/etc/letsencrypt/live/mail.yourdomain.com/privkey.pem"

[api]
host = "0.0.0.0"
port = 8000
debug = false
cors_origins = ["https://yourdomain.com"]
rate_limit = 100
jwt_secret = "generate-a-long-random-string-here"
jwt_algorithm = "HS256"
jwt_expiration = 3600

[dns]
resolver = "8.8.8.8"
timeout = 5
cache_ttl = 300
dkim_selector = "unitmail"
dkim_private_key_path = "/etc/unitmail/keys/dkim.private"

[logging]
level = "INFO"
file = "/var/log/unitmail/gateway.log"
json = true
```

### SSL Certificate

Obtain a free certificate from Let's Encrypt:

```bash
# Stop any service using port 80
sudo systemctl stop nginx  # if applicable

# Get certificate
sudo certbot certonly --standalone \
    -d mail.yourdomain.com \
    --agree-tos \
    --email admin@yourdomain.com

# Set up auto-renewal
sudo systemctl enable certbot.timer
```

### Systemd Service

Create `/etc/systemd/system/unitmail-gateway.service`:

```ini
[Unit]
Description=unitMail Gateway Service
After=network.target
Wants=network-online.target

[Service]
Type=notify
User=unitmail
Group=unitmail
WorkingDirectory=/var/lib/unitmail
ExecStart=/usr/local/bin/unitmail-gateway --config /etc/unitmail/settings.toml
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
WatchdogSec=60

# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/unitmail /var/log/unitmail

# Resource limits
LimitNOFILE=65536
MemoryMax=1G

# Environment
Environment="UNITMAIL_CONFIG_FILE=/etc/unitmail/settings.toml"

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable unitmail-gateway

# Start service
sudo systemctl start unitmail-gateway

# Check status
sudo systemctl status unitmail-gateway
```

---

## Security Hardening

### SSH Hardening

Edit `/etc/ssh/sshd_config`:

```bash
# Disable root login
PermitRootLogin no

# Use key authentication only
PasswordAuthentication no
PubkeyAuthentication yes

# Change default port (optional)
Port 2222

# Limit users
AllowUsers yourusername

# Idle timeout
ClientAliveInterval 300
ClientAliveCountMax 2
```

Restart SSH:
```bash
sudo systemctl restart sshd
```

### Fail2Ban Configuration

Create `/etc/fail2ban/jail.local`:

```ini
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

[unitmail-smtp]
enabled = true
port = 25,465,587
filter = unitmail-smtp
logpath = /var/log/unitmail/gateway.log
maxretry = 5

[unitmail-api]
enabled = true
port = 8000
filter = unitmail-api
logpath = /var/log/unitmail/gateway.log
maxretry = 10
```

Create `/etc/fail2ban/filter.d/unitmail-smtp.conf`:

```ini
[Definition]
failregex = ^.*SMTP auth failed for <HOST>.*$
            ^.*Rejected connection from <HOST>.*$
ignoreregex =
```

Create `/etc/fail2ban/filter.d/unitmail-api.conf`:

```ini
[Definition]
failregex = ^.*API auth failed from <HOST>.*$
            ^.*Rate limit exceeded for <HOST>.*$
ignoreregex =
```

Start Fail2Ban:
```bash
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Rate Limiting

Built-in rate limits in unitMail:

| Limit Type | Default | Configurable |
|------------|---------|--------------|
| Emails per day | 100 | Yes |
| Recipients per message | 10 | Yes |
| API requests per minute | 100 | Yes |
| Auth attempts per 15 min | 5 | Yes |

### TLS Configuration

Ensure strong TLS settings in `/etc/unitmail/settings.toml`:

```toml
[smtp]
# Require TLS for all connections
require_tls = true
# Minimum TLS version
min_tls_version = "1.2"
# Cipher suites (leave empty for sensible defaults)
cipher_suites = []
```

Test TLS configuration:
```bash
# Test SMTP TLS
openssl s_client -connect mail.yourdomain.com:465

# Test STARTTLS
openssl s_client -connect mail.yourdomain.com:587 -starttls smtp
```

---

## Monitoring and Logs

### Log Locations

| Log | Path | Contents |
|-----|------|----------|
| Gateway | `/var/log/unitmail/gateway.log` | SMTP/API operations |
| System | `/var/log/syslog` | System events |
| Mail | `/var/log/mail.log` | Postfix logs |
| Auth | `/var/log/auth.log` | Authentication attempts |

### Log Rotation

Create `/etc/logrotate.d/unitmail`:

```
/var/log/unitmail/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 unitmail unitmail
    postrotate
        systemctl reload unitmail-gateway > /dev/null 2>&1 || true
    endscript
}
```

### Viewing Logs

```bash
# Real-time gateway logs
sudo journalctl -u unitmail-gateway -f

# Last 100 lines
sudo tail -100 /var/log/unitmail/gateway.log

# Search for errors
sudo grep -i error /var/log/unitmail/gateway.log

# JSON log parsing (if json logging enabled)
sudo cat /var/log/unitmail/gateway.log | jq 'select(.level == "ERROR")'
```

### Monitoring Metrics

#### Queue Monitoring

```bash
# Check queue depth
unitmail-cli queue status

# List queued messages
unitmail-cli queue list

# Retry failed messages
unitmail-cli queue retry --all

# Flush specific message
unitmail-cli queue flush MESSAGE_ID
```

#### Health Checks

Create a health check script `/usr/local/bin/unitmail-health`:

```bash
#!/bin/bash

# Check gateway service
if ! systemctl is-active --quiet unitmail-gateway; then
    echo "CRITICAL: Gateway service not running"
    exit 2
fi

# Check SMTP port
if ! nc -z localhost 25; then
    echo "CRITICAL: SMTP port 25 not responding"
    exit 2
fi

# Check API port
if ! curl -sf http://localhost:8000/health > /dev/null; then
    echo "WARNING: API health check failed"
    exit 1
fi

# Check disk space
DISK_USAGE=$(df /var/lib/unitmail | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_USAGE" -gt 90 ]; then
    echo "WARNING: Disk usage at ${DISK_USAGE}%"
    exit 1
fi

# Check queue depth
QUEUE_DEPTH=$(unitmail-cli queue status --json | jq '.pending')
if [ "$QUEUE_DEPTH" -gt 1000 ]; then
    echo "WARNING: Queue depth is ${QUEUE_DEPTH}"
    exit 1
fi

echo "OK: All checks passed"
exit 0
```

### Alerting

#### Email Alerts (via cron)

```bash
# Add to crontab
*/5 * * * * /usr/local/bin/unitmail-health || echo "unitMail health check failed" | mail -s "unitMail Alert" admin@yourdomain.com
```

#### Integration with Monitoring Systems

For Prometheus, expose metrics endpoint:

```toml
[api]
metrics_enabled = true
metrics_port = 9090
```

For external monitoring (UptimeRobot, Pingdom, etc.):
- Monitor: `https://mail.yourdomain.com:8000/health`
- Expected response: `{"status": "healthy"}`

---

## Backup Procedures

### What to Back Up

| Component | Path | Priority |
|-----------|------|----------|
| Configuration | `/etc/unitmail/` | Critical |
| DKIM Keys | `/etc/unitmail/keys/` | Critical |
| SSL Certificates | `/etc/letsencrypt/` | Important |
| Local Database | `/var/lib/unitmail/` | Important |
| Logs | `/var/log/unitmail/` | Optional |

### Automated Backup Script

Create `/usr/local/bin/unitmail-backup`:

```bash
#!/bin/bash

set -e

BACKUP_DIR="/var/backups/unitmail"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/unitmail_backup_${DATE}.tar.gz"
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Stop gateway for consistent backup
systemctl stop unitmail-gateway

# Create backup
tar -czf "$BACKUP_FILE" \
    /etc/unitmail \
    /var/lib/unitmail \
    /etc/letsencrypt/live/mail.yourdomain.com \
    /etc/letsencrypt/archive/mail.yourdomain.com

# Restart gateway
systemctl start unitmail-gateway

# Encrypt backup (optional)
gpg --symmetric --cipher-algo AES256 "$BACKUP_FILE"
rm "$BACKUP_FILE"
BACKUP_FILE="${BACKUP_FILE}.gpg"

# Remove old backups
find "$BACKUP_DIR" -name "unitmail_backup_*.tar.gz*" -mtime +$RETENTION_DAYS -delete

# Verify backup
if tar -tzf "$BACKUP_FILE" > /dev/null 2>&1 || gpg --list-packets "$BACKUP_FILE" > /dev/null 2>&1; then
    echo "Backup successful: $BACKUP_FILE"
    echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "Backup verification failed!"
    exit 1
fi
```

Make executable and schedule:

```bash
chmod +x /usr/local/bin/unitmail-backup

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /usr/local/bin/unitmail-backup >> /var/log/unitmail/backup.log 2>&1" | sudo crontab -
```

### Remote Backup

#### Rsync to Remote Server

```bash
# Add to backup script
rsync -avz --delete \
    "$BACKUP_FILE" \
    backup-user@backup-server:/backups/unitmail/
```

#### Upload to Backblaze B2

```bash
# Install B2 CLI
pip install b2

# Configure
b2 authorize-account YOUR_KEY_ID YOUR_APP_KEY

# Upload
b2 upload-file unitmail-backups "$BACKUP_FILE" "backups/$(basename "$BACKUP_FILE")"
```

### Restore Procedures

#### Full Restore

```bash
# Stop gateway
sudo systemctl stop unitmail-gateway

# Decrypt backup (if encrypted)
gpg --decrypt unitmail_backup_20260111_020000.tar.gz.gpg > unitmail_backup.tar.gz

# Extract backup
sudo tar -xzf unitmail_backup.tar.gz -C /

# Fix permissions
sudo chown -R unitmail:unitmail /var/lib/unitmail
sudo chmod 600 /etc/unitmail/keys/dkim.private

# Start gateway
sudo systemctl start unitmail-gateway

# Verify
sudo systemctl status unitmail-gateway
```

#### Selective Restore

```bash
# List backup contents
tar -tzf unitmail_backup.tar.gz

# Extract only configuration
tar -xzf unitmail_backup.tar.gz -C /tmp etc/unitmail/

# Restore specific file
sudo cp /tmp/etc/unitmail/settings.toml /etc/unitmail/
```

---

## Upgrade Process

### Pre-Upgrade Checklist

1. [ ] Read release notes for breaking changes
2. [ ] Create full backup
3. [ ] Test upgrade on staging (if available)
4. [ ] Schedule maintenance window
5. [ ] Notify users of potential downtime

### Upgrade Steps

#### Package Upgrade (Recommended)

```bash
# Update package list
sudo apt update

# Check available version
apt-cache policy unitmail

# Upgrade
sudo apt upgrade unitmail

# Restart services
sudo systemctl restart unitmail-gateway

# Verify
sudo systemctl status unitmail-gateway
unitmail-cli --version
```

#### Manual Upgrade

```bash
# Stop gateway
sudo systemctl stop unitmail-gateway

# Backup current installation
sudo cp -r /opt/unitmail /opt/unitmail.backup

# Download new version
wget https://releases.unitmail.org/latest/unitmail-gateway-latest.tar.gz

# Extract
sudo tar -xzf unitmail-gateway-latest.tar.gz -C /opt/

# Run migrations (if any)
sudo /opt/unitmail/bin/unitmail-migrate

# Restart
sudo systemctl start unitmail-gateway

# Verify
sudo systemctl status unitmail-gateway
```

### Rollback Procedure

If upgrade fails:

```bash
# Stop gateway
sudo systemctl stop unitmail-gateway

# Restore backup
sudo rm -rf /opt/unitmail
sudo mv /opt/unitmail.backup /opt/unitmail

# Restore configuration if needed
sudo tar -xzf /var/backups/unitmail/unitmail_backup_XXXXXX.tar.gz -C / etc/unitmail/

# Restart
sudo systemctl start unitmail-gateway
```

### Database Migrations

Migrations run automatically on upgrade. To run manually:

```bash
# Check migration status
unitmail-cli migrate status

# Run pending migrations
unitmail-cli migrate up

# Rollback last migration
unitmail-cli migrate down
```

### Version Compatibility

| Gateway Version | Client Version | Database Schema |
|-----------------|----------------|-----------------|
| 0.1.x | 0.1.x | v1 |
| 0.2.x | 0.1.x - 0.2.x | v2 |
| 1.0.x | 0.2.x - 1.0.x | v3 |

Always upgrade gateway before clients to ensure compatibility.

---

## Additional Resources

- [Technical Specification](/docs/TECHNICAL_SPECIFICATION.md)
- [API Reference](/docs/API_REFERENCE.md)
- [Security Best Practices](https://docs.unitmail.org/security)
- [Community Forum](https://forum.unitmail.org)
- [Issue Tracker](https://github.com/unitmail/unitmail/issues)
