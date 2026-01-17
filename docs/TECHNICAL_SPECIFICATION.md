# unitMail Technical Specification

## Version

Document Version: 1.0  
Last Updated: 2026-01-11  
Target Release: unitMail 1.0

## System Requirements

### Client System

**Operating System**
- Ubuntu 22.04+ / Debian 12+
- Fedora 38+ / RHEL 9+
- Arch Linux (current)
- Other Linux distributions (compatibility not guaranteed)

**Hardware Minimum**
- CPU: x86_64 or ARM64, 1 GHz
- RAM: 1GB available
- Disk: 5GB free space
- Network: Any internet connection

**Hardware Recommended**
- CPU: 2+ cores
- RAM: 2GB available
- Disk: 10GB free space (allows for email storage growth)
- Network: Broadband (5 Mbps+)

**Software Dependencies**
- Python 3.11+
- GTK 4.0+
- SQLite 3.35+ (built into Python)
- OpenSSL 3.0+
- systemd (for service management)

### Gateway System (VPS)

**Minimum Specifications**
- CPU: 1 vCPU
- RAM: 1GB
- Disk: 10GB SSD
- Bandwidth: 1TB/month
- Static IPv4 address
- Port 25 open (both inbound and outbound)

**Recommended Specifications**
- CPU: 2 vCPU
- RAM: 2GB
- Disk: 20GB SSD
- Bandwidth: 2TB/month
- IPv6 support

**Operating System**
- Ubuntu Server 22.04 LTS
- Debian 12
- Other Linux distributions supported but not tested

## Protocol Specifications

### SMTP Implementation

**Supported Standards**
- RFC 5321 (SMTP)
- RFC 5322 (Internet Message Format)
- RFC 6531 (SMTPUTF8)
- RFC 3207 (STARTTLS)
- RFC 4954 (SMTP Authentication)
- RFC 6376 (DKIM)
- RFC 7208 (SPF)
- RFC 7489 (DMARC)

**SMTP Commands**
```
EHLO/HELO     - Required
MAIL FROM     - Required
RCPT TO       - Required
DATA          - Required
STARTTLS      - Required
AUTH          - Optional (for submission)
QUIT          - Required
RSET          - Optional
NOOP          - Optional
VRFY          - Disabled (privacy)
EXPN          - Disabled (privacy)
```

**Response Codes**
```
220 - Service ready
221 - Service closing
250 - Requested action completed
354 - Start mail input
421 - Service not available
450 - Mailbox unavailable (temporary)
451 - Error in processing (temporary)
452 - Insufficient storage
500 - Syntax error
501 - Syntax error in parameters
502 - Command not implemented
503 - Bad sequence of commands
550 - Mailbox unavailable (permanent)
551 - User not local
552 - Exceeded storage allocation
553 - Mailbox name not allowed
554 - Transaction failed
```

**Port Configuration**
- Port 25: SMTP (MTA-to-MTA, STARTTLS required)
- Port 587: Submission (client-to-server, TLS required)
- Port 465: SMTPS (deprecated but supported for compatibility)

### IMAP Implementation (Future)

**Current Status**: Not implemented in v1.0  
**Planned**: v1.2+

Local access only via GTK client. Remote IMAP access planned for mobile clients.

### Gateway API Specification

**Transport Protocol**
- HTTPS only (port 443)
- TLS 1.2 minimum (TLS 1.3 preferred)
- Client certificate authentication (optional)

**Authentication**
```
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@unitmail.com",
  "password": "secure_password"
}

Response:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires": "2026-01-12T00:00:00Z"
}
```

**API Endpoints**

**Send Email**
```
POST /api/v1/messages/send
Authorization: Bearer <token>
Content-Type: application/json

{
  "to": ["recipient@example.com"],
  "cc": ["cc@example.com"],
  "bcc": ["bcc@example.com"],
  "subject": "Test Email",
  "body": "Plain text body",
  "body_html": "<html><body>HTML body</body></html>",
  "attachments": [
    {
      "filename": "document.pdf",
      "content_type": "application/pdf",
      "data": "<base64 encoded data>"
    }
  ]
}

Response:
{
  "message_id": "<unique-id@unitmail.com>",
  "status": "queued",
  "queue_id": "A1B2C3D4"
}
```

**Fetch Messages**
```
GET /api/v1/messages?folder=inbox&limit=50&offset=0
Authorization: Bearer <token>

Response:
{
  "messages": [
    {
      "id": 123,
      "message_id": "<received@example.com>",
      "from": "sender@example.com",
      "to": "user@unitmail.com",
      "subject": "Subject",
      "preview": "First 100 chars of body...",
      "date": "2026-01-11T10:00:00Z",
      "flags": ["seen", "flagged"]
    }
  ],
  "total": 250,
  "has_more": true
}
```

**Get Message Details**
```
GET /api/v1/messages/123
Authorization: Bearer <token>

Response:
{
  "id": 123,
  "message_id": "<received@example.com>",
  "from": "sender@example.com",
  "to": "user@unitmail.com",
  "cc": [],
  "subject": "Subject",
  "body": "Full plain text body",
  "body_html": "<html>...</html>",
  "attachments": [...],
  "date": "2026-01-11T10:00:00Z",
  "flags": ["seen"]
}
```

**WebSocket for Real-time Updates**
```
WSS /api/v1/stream
Authorization: Bearer <token>

Client → Server:
{
  "action": "subscribe",
  "events": ["new_message", "queue_update"]
}

Server → Client (on new message):
{
  "event": "new_message",
  "data": {
    "id": 124,
    "from": "sender@example.com",
    "subject": "New Email",
    "preview": "..."
  }
}
```

### Encryption Specifications

**TLS Configuration**

**Cipher Suites (Allowed)**
```
TLS_AES_256_GCM_SHA384
TLS_CHACHA20_POLY1305_SHA256
TLS_AES_128_GCM_SHA256
ECDHE-RSA-AES256-GCM-SHA384
ECDHE-RSA-AES128-GCM-SHA256
```

**Cipher Suites (Rejected)**
```
All SSL 2.0/3.0
All TLS 1.0/1.1
All RC4 ciphers
All DES/3DES ciphers
All export-grade ciphers
```

**Certificate Requirements**
- 2048-bit RSA minimum (4096-bit recommended)
- SHA-256 signature minimum
- Subject Alternative Names (SAN) for all domains
- OCSP stapling enabled
- Certificate Transparency logging

**DKIM Signing**

**Key Generation**
```bash
openssl genrsa -out dkim_private.pem 2048
openssl rsa -in dkim_private.pem -pubout -out dkim_public.pem
```

**DNS Record Format**
```
default._domainkey.unitmail.com. IN TXT (
  "v=DKIM1; "
  "k=rsa; "
  "p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC..."
)
```

**Signature Headers**
```
DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed;
  d=unitmail.com; s=default;
  h=from:to:subject:date:message-id;
  bh=base64_body_hash;
  b=base64_signature
```

**PGP/GPG Integration**

**Key Management**
- GnuPG 2.2+
- 4096-bit RSA keys
- Subkeys for signing and encryption
- Automatic key refresh from keyservers
- WKD (Web Key Directory) support

**Automatic Encryption**
- If recipient's public key available → encrypt automatically
- Sign all outgoing mail by default
- Verify signatures on incoming mail
- Warn if signature verification fails

### Database Specifications

**SQLite Version**: 3.35+
**Journal Mode**: WAL (Write-Ahead Logging)
**Synchronous Mode**: FULL
**Foreign Keys**: ENABLED

**Full-Text Search**: FTS5 with Porter stemmer

**Configuration**
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
PRAGMA foreign_keys = ON;
PRAGMA auto_vacuum = INCREMENTAL;
PRAGMA page_size = 4096;
PRAGMA cache_size = 10000;
```

**Indexes**
```sql
-- Performance-critical indexes
CREATE INDEX idx_messages_folder ON messages(folder);
CREATE INDEX idx_messages_date ON messages(received_at DESC);
CREATE INDEX idx_messages_from ON messages(from_addr);
CREATE INDEX idx_queue_status ON queue(status, created_at);

-- Full-text search
CREATE VIRTUAL TABLE messages_fts USING fts5(
  subject,
  body,
  content=messages,
  content_rowid=id
);
```

**Backup Schedule**
- Full backup: Daily at 2:00 AM local time
- Incremental: Every 6 hours
- Retention: 30 days
- Compression: gzip level 6

### WireGuard Mesh Specifications

**Network Topology**
- Flat peer-to-peer (no central hub)
- Each peer has unique /32 address
- Subnet: 10.0.0.0/24 (254 peers maximum)

**Key Exchange**
- Manual exchange initially
- Automatic distribution via signed messages (future)
- Public key fingerprint verification required

**Configuration Template**
```ini
[Interface]
PrivateKey = <generated on install>
Address = 10.0.0.X/24
ListenPort = 51820

[Peer]
PublicKey = <peer's public key>
AllowedIPs = 10.0.0.Y/32
Endpoint = <peer's public IP or dynamic DNS>:51820
PersistentKeepalive = 25
```

**Routing Rules**
```bash
# Route mesh traffic through WireGuard
ip route add 10.0.0.0/24 dev wg0

# Do NOT route internet traffic through mesh
# Each peer maintains independent internet connection
```

## Performance Specifications

### Response Time Targets

**GTK Client**
- Application launch: <2 seconds
- Open inbox: <500ms (for 1000 messages)
- Compose window: <200ms
- Search results: <1 second (for 10,000 messages)

**Gateway Service**
- API response: <100ms (p95)
- SMTP accept: <50ms
- Queue processing: <5 seconds per message
- DNS updates: <10 seconds

### Throughput Targets

**Single Gateway**
- Inbound: 100 messages/minute
- Outbound: 100 messages/minute
- Concurrent connections: 100
- WebSocket connections: 1000

**Client Application**
- Database queries: 1000/second
- UI refresh: 60 FPS
- Memory usage: <200MB

### Resource Limits

**Per-User Quotas**
- Messages per day: 100 (configurable)
- Recipients per message: 10
- Attachment size: 25MB per file
- Total message size: 35MB
- Storage: Unlimited (local disk)

**Gateway Limits**
- Max message size: 50MB
- Queue depth: 10,000 messages
- Retention: Failed messages kept 7 days
- Connection timeout: 30 seconds
- Idle timeout: 5 minutes

## Error Handling

### SMTP Errors

**Temporary Failures (4xx)**
```
450 - Mailbox busy, retry in 5 minutes
451 - Server error, retry in 15 minutes
452 - Out of storage, notify admin
```
**Action**: Retry with exponential backoff (5m, 15m, 1h, 4h, 24h)

**Permanent Failures (5xx)**
```
550 - User unknown, bounce immediately
551 - User not local, reject
552 - Over quota, bounce
554 - Spam detected, reject
```
**Action**: Return bounce message to sender

### Client-Side Errors

**Network Errors**
```
Connection refused     → Check gateway status
Timeout               → Retry with backoff
SSL error             → Verify certificates
Authentication failed → Prompt for credentials
```

**Database Errors**
```
Locked     → Retry (SQLite WAL mode handles this)
Corrupted  → Restore from backup
Full disk  → Alert user, cleanup
```

### Gateway Errors

**Queue Processing**
```
DNS failure        → Retry 3 times, then defer
Connection refused → Retry with backoff
Greylisting        → Respect retry-after
Blacklisted        → Alert admin, pause sending
```

**System Errors**
```
Out of memory   → Restart service, alert admin
Disk full       → Rotate logs, cleanup queue
Port blocked    → Alert admin, suggest VPS
Certificate expired → Auto-renew via Let's Encrypt
```

## Security Specifications

### Authentication

**Password Requirements**
- Minimum length: 12 characters
- Must contain: uppercase, lowercase, number, special
- Not in common password list (10M entries)
- Not based on username or email
- bcrypt hash with cost factor 12

**Token Security**
- JWT tokens
- HS256 signing algorithm
- 24-hour expiration
- Refresh token: 30 days
- Stored in secure storage (kernel keyring)

### Authorization

**Permission Model**
```
User Roles:
- owner: Full control
- admin: Manage settings, view logs
- user:  Send/receive email only

Operations:
- send_email:    user+
- read_email:    user+
- delete_email:  user+
- modify_config: admin+
- view_logs:     admin+
- add_user:      owner only
```

### Attack Mitigation

**Rate Limiting**
```
Authentication:
- 5 attempts per 15 minutes
- 20 attempts per hour
- 100 attempts per day
- Lockout: 1 hour after limit

API Requests:
- 100 requests per minute
- 1000 requests per hour
- Burst: 20 requests

SMTP:
- 100 messages per day
- 10 recipients per message
- 1 message per 30 seconds (if >3 recipients)
```

**Firewall Rules**
```bash
# Allow SMTP
iptables -A INPUT -p tcp --dport 25 -j ACCEPT
iptables -A INPUT -p tcp --dport 587 -j ACCEPT

# Allow HTTPS
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Allow SSH (rate limited)
iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW \
  -m recent --set --name SSH
iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW \
  -m recent --update --seconds 60 --hitcount 4 --name SSH -j DROP
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Drop everything else
iptables -P INPUT DROP
iptables -P FORWARD DROP
```

**Spam Prevention**

**Rspamd Integration**
```
Spam score thresholds:
0-5:   Pass
5-10:  Mark as spam
10+:   Reject

Checks:
- SPF verification
- DKIM verification
- DMARC policy
- Bayes classifier
- DNS blacklists
- Greylisting
- Rate limiting
```

**Content Filtering**
```
Blocked patterns:
- "unsubscribe" (newsletter indicator)
- "opt-in" (bulk mail indicator)
- Excessive capitals (SPAM INDICATOR)
- Pharmaceutical keywords
- Financial scam keywords

Attachment filtering:
- Block: .exe, .scr, .bat, .cmd
- Warn: .zip, .rar containing executables
- Scan: All attachments with ClamAV
```

## Testing Specifications

### Unit Tests

**Coverage Target**: 80% minimum

**Test Framework**: pytest

**Critical Paths**
- Message parsing and generation
- SMTP protocol implementation
- Database operations
- Encryption/decryption
- API endpoints
- Queue management

### Integration Tests

**Test Scenarios**
- Send email to Gmail (deliverability)
- Receive email from Outlook (compatibility)
- Mesh network communication
- VPS gateway failover
- Database backup/restore
- Certificate renewal

### Performance Tests

**Load Testing**
```
Scenario 1: Peak Load
- 100 concurrent users
- 1000 messages/hour
- Mixed read/write operations
- Duration: 1 hour

Scenario 2: Sustained Load
- 50 concurrent users
- 500 messages/hour
- 80% read, 20% write
- Duration: 24 hours

Scenario 3: Spike Test
- 0 to 200 users in 1 minute
- Maintain for 10 minutes
- Return to baseline
```

**Acceptance Criteria**
- p95 response time <500ms
- Zero message loss
- No database corruption
- Memory usage stable

### Security Tests

**Penetration Testing**
- SQL injection attempts
- XSS in email rendering
- CSRF in web interface
- Authentication bypass attempts
- Rate limit evasion
- Email spoofing

**Compliance Checks**
- TLS configuration (ssllabs.com)
- SPF/DKIM/DMARC verification
- Open relay test
- Blacklist status
- Port scanning (nmap)

## Compliance and Standards

### Email Standards Compliance

**Must Support**
- RFC 5321 (SMTP)
- RFC 5322 (Message Format)
- RFC 6376 (DKIM)
- RFC 7208 (SPF)
- RFC 7489 (DMARC)
- RFC 3207 (STARTTLS)

**Should Support**
- RFC 6531 (SMTPUTF8)
- RFC 2045-2049 (MIME)
- RFC 2183 (Content-Disposition)
- RFC 2822 (Message Format)

### Privacy Compliance

**GDPR (if operating in EU)**
- Data minimization
- Right to access
- Right to deletion
- Data portability
- Consent management
- Breach notification

**CCPA (if operating in California)**
- Privacy policy disclosure
- Opt-out mechanisms
- Data access requests
- Data deletion requests

**Implementation**
- No user tracking
- No email scanning
- No data sharing
- Encryption at rest
- Secure deletion
- Export functionality

## Versioning and Compatibility

### Semantic Versioning

**Format**: MAJOR.MINOR.PATCH

**Rules**
- MAJOR: Breaking API changes
- MINOR: New features, backward compatible
- PATCH: Bug fixes, backward compatible

**Current Version**: 1.0.0

### API Versioning

**URL Format**: `/api/v1/...`

**Version Support**
- Current version: Full support
- Previous version: Security updates only (12 months)
- Older versions: No support

### Database Migration

**Migration Strategy**
- Automatic migrations on upgrade
- Backup before migration
- Rollback capability
- Version tracking in database

**Migration Example**
```python
def upgrade_v1_to_v2(db):
    """Add encryption column to messages table"""
    db.execute('''
        ALTER TABLE messages 
        ADD COLUMN encrypted BOOLEAN DEFAULT 0
    ''')
    db.execute('''
        UPDATE config 
        SET value = '2' 
        WHERE key = 'schema_version'
    ''')
```

## Build and Release Process

### Build System

**Language**: Python 3.11
**Build Tool**: setuptools
**Package Format**: wheel (.whl)

**Dependencies Management**
```
requirements.txt      - Core dependencies
requirements-dev.txt  - Development dependencies
requirements-test.txt - Testing dependencies
```

### Release Checklist

**Pre-Release**
- [ ] All tests pass
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Version number bumped
- [ ] Changelog updated
- [ ] Security scan clean

**Release**
- [ ] Build packages (deb, rpm, AppImage)
- [ ] Sign packages with GPG
- [ ] Upload to distribution servers
- [ ] Update website
- [ ] Announce release
- [ ] Monitor for issues

**Post-Release**
- [ ] Tag repository
- [ ] Create GitHub release
- [ ] Update roadmap
- [ ] Close milestone

## Documentation Requirements

### User Documentation

**Required Documents**
- Installation guide
- Quick start tutorial
- User manual
- FAQ
- Troubleshooting guide

**Format**: Markdown + HTML

### Developer Documentation

**Required Documents**
- API reference
- Architecture overview
- Database schema
- Contributing guide
- Code style guide

**Format**: Markdown + auto-generated API docs

### Admin Documentation

**Required Documents**
- VPS setup guide
- DNS configuration guide
- Security hardening guide
- Backup procedures
- Monitoring setup

**Format**: Markdown

## Support and Maintenance

### Update Frequency

**Security Updates**: Within 24 hours of disclosure
**Bug Fixes**: Weekly (if critical), monthly (if minor)
**Feature Releases**: Quarterly

### End-of-Life Policy

**Version Support**
- Latest major version: 36 months
- Previous major version: 12 months
- Older versions: No support

**End-of-Life Process**
1. Announce EOL 12 months in advance
2. Security updates only for final 6 months
3. No updates after EOL date
4. Migration guide provided

## Conclusion

This technical specification provides the foundation for implementing unitMail. All components must adhere to these specifications to ensure consistency, security, and compatibility.

Deviations from this specification require approval and documentation. As the project evolves, this document will be updated to reflect architectural decisions and lessons learned.
