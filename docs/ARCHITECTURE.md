# unitMail System Architecture

## Executive Summary

unitMail uses a hybrid architecture combining local client software with a lightweight gateway service to enable independent email infrastructure while maintaining compatibility with standard SMTP/IMAP protocols.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    User's Local System                       │
│  ┌──────────────────┐          ┌──────────────────┐         │
│  │   GTK Client     │◄────────►│ Gateway Service  │         │
│  │   (Frontend)     │  Unix    │   (Backend)      │         │
│  │                  │  Socket  │                  │         │
│  │  - Compose UI    │          │  - SMTP Server   │         │
│  │  - Read UI       │          │  - Queue Manager │         │
│  │  - Settings      │          │  - DNS Updater   │         │
│  │  - Contacts      │          │  - Crypto Engine │         │
│  └────────┬─────────┘          └─────────┬────────┘         │
│           │                               │                  │
│           └───────────┬───────────────────┘                  │
│                       ▼                                      │
│           ┌──────────────────────┐                          │
│           │  SQLite Database     │                          │
│           │  - messages          │                          │
│           │  - contacts          │                          │
│           │  - queue             │                          │
│           │  - config            │                          │
│           └──────────────────────┘                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTPS/TLS (Port 443)
                         │ or Direct SMTP (Port 25/587)
                         │
                         ▼
              ┌──────────────────────┐
              │ Internet / SMTP      │
              │ - Gmail              │
              │ - Outlook            │
              │ - Other Mail Servers │
              └──────────────────────┘
```

## Deployment Models

### Model 1: Direct SMTP (Static IP)

**Architecture**
```
User's Machine (Static IP: 203.0.113.50)
├── GTK Client
├── Gateway Service (ports 25, 587, 993)
└── SQLite Database

DNS:
  mail.example.com  A     203.0.113.50
  example.com       MX    mail.example.com
  example.com       TXT   "v=spf1 ip4:203.0.113.50 -all"
```

**Requirements**
- Business internet or ISP exception
- Static IP address
- Port 25 open (inbound and outbound)
- Domain with DNS control

**Advantages**
- True independence (no intermediary)
- Lowest latency
- No monthly VPS cost

**Disadvantages**
- ISP cooperation required
- IP reputation building needed
- Power/internet outages affect service

### Model 2: VPS Gateway

**Architecture**
```
User's Home Machine                    User's VPS ($5/mo)
┌──────────────────┐                  ┌─────────────────┐
│ GTK Client       │                  │ Gateway Service │
│ SQLite Database  │                  │ (SMTP relay)    │
│                  │                  │                 │
│ Encrypted Store  │◄────HTTPS/TLS───►│ No Storage      │
└──────────────────┘                  │ Port 25 Open    │
                                      └────────┬────────┘
                                               │
                                               │ SMTP
                                               │
                                               ▼
                                          Internet
```

**Requirements**
- VPS with port 25 access ($3-5/month)
- Regular home internet (any ISP)
- Domain with DNS control

**Advantages**
- No ISP cooperation needed
- Works on residential internet
- Gateway IP has reputation
- High availability

**Disadvantages**
- Monthly VPS cost
- Gateway sees metadata
- Single point of failure

### Model 3: Mesh Network

**Architecture**
```
User 1                 User 2                 User 3
┌──────────┐          ┌──────────┐          ┌──────────┐
│ unitMail │          │ unitMail │          │ unitMail │
│ Complete │          │ Complete │          │ unitMail │
└────┬─────┘          └────┬─────┘          └────┬─────┘
     │                     │                     │
     └──────WireGuard──────┴──────WireGuard──────┘
            10.0.0.1       10.0.0.2       10.0.0.3
            
Direct SMTP over encrypted mesh (no internet required)
```

**Requirements**
- WireGuard installed
- Exchanged public keys
- Network connectivity (LAN or internet)

**Advantages**
- Ultra-private (never leaves mesh)
- No external dependencies
- Fast (direct connections)
- Works offline (if same LAN)

**Disadvantages**
- Only works within mesh
- Cannot email external addresses
- Manual key exchange

### Model 4: Hybrid (Recommended)

**Architecture**
```
┌─────────────────────────────────────────────┐
│ User's Machine                              │
│  ┌──────────┐        ┌──────────┐          │
│  │ Client   │◄──────►│ Gateway  │          │
│  └──────────┘        └────┬─────┘          │
└────────────────────────────┼────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
              WireGuard Mesh    VPS Gateway
                    │                 │
                    ▼                 ▼
              Mesh Peers      Internet (SMTP)
```

**Routing Logic**
- Recipient in mesh → Direct via WireGuard
- Recipient external → Via VPS gateway
- Automatic failover if gateway down

**Advantages**
- Best of both worlds
- Privacy for mesh traffic
- Compatibility for external
- Redundancy

## Component Details

### GTK Client Application

**Technology Stack**
- Python 3.11+
- GTK 4.0
- PyGObject
- SQLAlchemy (database ORM)
- Requests (HTTP client)
- python-gnupg (encryption)

**Features**
- Email composition (rich text, attachments)
- Folder management (inbox, sent, drafts, trash)
- Contact management
- Search functionality
- Settings panel
- Queue monitoring
- Gateway status display

**File Structure**
```
unitmail-client/
├── ui/
│   ├── main_window.py
│   ├── composer.py
│   ├── reader.py
│   ├── settings.py
│   └── contacts.py
├── models/
│   ├── message.py
│   ├── contact.py
│   └── config.py
├── services/
│   ├── gateway_client.py
│   ├── crypto.py
│   └── search.py
└── resources/
    ├── icons/
    └── templates/
```

**Inter-Process Communication**
- Unix domain socket: `/run/unitmail/gateway.sock`
- JSON-RPC protocol
- D-Bus for notifications

### Gateway Microservice

**Technology Stack**
- Python 3.11+
- Postfix (SMTP MTA)
- Flask (REST API)
- SQLite (local queue)
- python-daemon (service management)

**Components**

**SMTP Server**
- Receives incoming mail (port 25)
- Sends outgoing mail (port 25/587)
- Handles authentication
- Queue management

**API Server**
- HTTPS endpoint for client communication
- Authentication via API tokens
- RESTful interface
- WebSocket for real-time updates

**Protocol Converter**
```python
# Inbound flow
SMTP (external) → Parse → Store in SQLite → Notify client via socket

# Outbound flow
Client request → Queue in SQLite → SMTP delivery → Status update
```

**File Structure**
```
unitmail-gateway/
├── smtp/
│   ├── receiver.py
│   ├── sender.py
│   └── queue.py
├── api/
│   ├── server.py
│   ├── auth.py
│   └── handlers.py
├── dns/
│   ├── updater.py
│   └── checker.py
├── crypto/
│   ├── dkim.py
│   ├── tls.py
│   └── pgp.py
└── config/
    ├── postfix/
    └── settings.py
```

**Service Configuration**
```ini
[Unit]
Description=unitMail Gateway Service
After=network.target

[Service]
Type=notify
User=unitmail
ExecStart=/opt/unitmail/bin/unitmail-gateway
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Database Schema

**SQLite Database**: `/var/lib/unitmail/mail.db`

```sql
-- Messages table
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,
    folder TEXT NOT NULL DEFAULT 'inbox',
    from_addr TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc_addr TEXT,
    bcc_addr TEXT,
    subject TEXT,
    body TEXT,
    body_html TEXT,
    attachments TEXT, -- JSON array
    flags TEXT, -- JSON: seen, answered, flagged, deleted
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    received_at DATETIME,
    INDEX idx_folder (folder),
    INDEX idx_from (from_addr),
    INDEX idx_received (received_at)
);

-- Contacts table
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    pgp_key TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Outbound queue
CREATE TABLE queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,
    to_addr TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- pending, sending, sent, failed
    attempts INTEGER DEFAULT 0,
    last_attempt DATETIME,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status)
);

-- Configuration
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Mesh peers (for WireGuard)
CREATE TABLE mesh_peers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email_domain TEXT UNIQUE NOT NULL,
    public_key TEXT NOT NULL,
    endpoint TEXT, -- IP:port
    allowed_ips TEXT NOT NULL,
    last_seen DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Networking Layer

**WireGuard Configuration**
```ini
[Interface]
PrivateKey = <user's private key>
Address = 10.0.0.X/24
ListenPort = 51820

[Peer]
PublicKey = <peer's public key>
AllowedIPs = 10.0.0.Y/32
Endpoint = <peer's public IP>:51820
PersistentKeepalive = 25
```

**DNS Configuration**
```
; MX Record
example.com.        IN  MX  10 mail.example.com.

; A Record
mail.example.com.   IN  A   203.0.113.50

; SPF Record
example.com.        IN  TXT "v=spf1 ip4:203.0.113.50 -all"

; DKIM Record
default._domainkey.example.com. IN TXT "v=DKIM1; k=rsa; p=MIGfMA0GCS..."

; DMARC Record
_dmarc.example.com. IN TXT "v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com"

; Reverse DNS (PTR)
50.113.0.203.in-addr.arpa. IN PTR mail.example.com.
```

## Security Architecture

### Encryption Layers

**1. Transport Layer (TLS)**
- All SMTP connections use STARTTLS or TLS
- Let's Encrypt certificates (auto-renewal)
- Modern cipher suites only (TLS 1.2+)

**2. Storage Layer**
- SQLite database encrypted at rest (SQLCipher)
- User password required to unlock
- Automatic lock after inactivity

**3. End-to-End Layer (Optional)**
- PGP/GPG for message encryption
- Automatic key exchange via WKD
- Seamless integration with GTK client

### Authentication

**Client ↔ Gateway**
- API token authentication
- Token stored in `~/.config/unitmail/token`
- Regenerated on password change

**SMTP Authentication**
- SASL mechanisms: PLAIN, LOGIN (over TLS only)
- Password hashing: Argon2
- Rate limiting: 10 failures → 1 hour lockout

### Anti-Abuse Measures

**Rate Limiting**
- 100 emails/day per user (configurable)
- 10 recipients per message maximum
- 1 email per 30 seconds if >3 recipients

**Content Filtering**
- Rspamd integration for spam scoring
- Keyword detection for bulk mail
- Attachment size limits (25MB default)

**Monitoring**
- Real-time queue inspection
- Bounce rate tracking
- Blacklist monitoring (Spamhaus, SORBS)

## Scalability Considerations

### Single User Performance

**Resources**
- RAM: 256MB (gateway service)
- Disk: 50MB (software) + user data
- CPU: <1% idle, <10% during send/receive
- Bandwidth: Minimal (<1GB/month for typical use)

### Multi-User VPS Gateway

**100 Users**
- VPS: 2GB RAM, 2 vCPU ($10/month)
- Disk: 20GB
- Bandwidth: 500GB/month
- Handles: 10,000 emails/day

**1000 Users**
- VPS: 4GB RAM, 4 vCPU ($20/month)
- Disk: 40GB
- Bandwidth: 2TB/month
- Handles: 100,000 emails/day
- Load balancer recommended

## Deployment Architecture

### Installation Package

**Distribution Format**
- AppImage (universal Linux)
- Debian package (.deb)
- RPM package (Fedora/RHEL)
- Flatpak (sandboxed)

**Package Contents**
```
unitmail-1.0.0/
├── bin/
│   ├── unitmail              # GTK launcher
│   ├── unitmail-gateway      # Service binary
│   └── unitmail-setup        # First-run wizard
├── lib/
│   ├── python3.11/
│   └── libsqlite3.so
├── share/
│   ├── applications/unitmail.desktop
│   ├── icons/
│   └── doc/
└── systemd/
    └── unitmail-gateway.service
```

### First-Run Setup

**Wizard Steps**

1. **Welcome**: Choose deployment model
2. **Network**: Static IP or VPS configuration
3. **Domain**: DNS setup and verification
4. **Email**: Create first account
5. **Security**: Password, optional PGP
6. **Mesh** (Optional): Join or create mesh
7. **Complete**: Start services

**Automated Tasks**
- Generate DKIM keys
- Create SPF/DMARC records (shows DNS entries)
- Request SSL certificate
- Test port 25 connectivity
- Verify DNS propagation

## Backup and Recovery

### Backup Strategy

**What Gets Backed Up**
- SQLite database (messages, contacts, config)
- DKIM private keys
- PGP keys
- Configuration files

**Backup Methods**

**Local Backup**
```bash
# Automated daily backup
0 2 * * * unitmail-backup --output /backup/unitmail/
```

**Remote Backup** (Optional)
- Encrypted upload to Backblaze B2
- Rsync to remote server
- Syncthing to multiple locations

### Disaster Recovery

**Recovery Scenarios**

**Disk Failure**
1. Install unitMail on new system
2. Restore database from backup
3. Restore DKIM/PGP keys
4. Restart services

**VPS Failure**
1. Spin up new VPS
2. Run setup wizard
3. Point DNS to new IP
4. Restore gateway configuration

**Complete Loss**
1. Download fresh unitMail package
2. Create new keys (DKIM, PGP)
3. Update DNS records
4. Email data lost (unless backed up)

## Monitoring and Maintenance

### Health Checks

**Automated Monitoring**
- Port 25 connectivity
- DNS record validity
- SSL certificate expiration
- Disk space usage
- Queue depth
- Blacklist status

**Alerting**
- Email notification (ironic, but works)
- Desktop notification (GTK)
- Optional: Webhook to external service

### Update Mechanism

**Update Process**
1. Check for updates (daily)
2. Download update package
3. Verify signature
4. Backup current state
5. Apply update
6. Restart services
7. Verify functionality

**Rollback**
- Previous version kept for 30 days
- One-click rollback if issues
- Automatic rollback on service failure

## Technology Choices Rationale

**Why Python?**
- Rapid development
- Rich library ecosystem
- Cross-platform
- Easy to audit

**Why GTK?**
- Native Linux integration
- Lightweight
- Active development
- Accessibility support

**Why SQLite?**
- Serverless (no daemon)
- Single-file database
- Fast for single-user
- Built-in backup (copy file)

**Why Postfix?**
- Battle-tested (25+ years)
- Excellent documentation
- Modular architecture
- Industry standard

**Why WireGuard?**
- Modern cryptography
- Minimal attack surface
- Fast (kernel-level)
- Simple configuration

## Conclusion

The unitMail architecture balances independence with practicality. Local storage ensures data sovereignty, while the gateway model maintains compatibility with existing email infrastructure. The hybrid approach allows users to choose their level of independence based on technical capability and budget.

The modular design enables future enhancements without architectural changes. Open protocols ensure no vendor lock-in. Resource efficiency allows deployment on modest hardware.

This architecture delivers on the promise: a truly independent email system that works with the existing internet email ecosystem.
