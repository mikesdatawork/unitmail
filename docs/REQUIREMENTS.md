# unitMail Requirements Document

## Document Information

**Version**: 1.0  
**Date**: 2026-01-11  
**Status**: Draft  
**Target Release**: unitMail 1.0

## Overview

This document defines the requirements for unitMail, an independent email system designed to give users complete control over their email infrastructure while maintaining compatibility with standard SMTP/IMAP protocols.

## Stakeholders

**Primary Users**
- Researchers and academics
- Privacy-conscious individuals
- Small organizations
- Linux enthusiasts
- Anyone affected by email provider lockouts

**Secondary Users**
- System administrators
- Open source contributors
- Documentation writers

**External Dependencies**
- ISPs (for internet connectivity)
- VPS providers (for gateway hosting)
- DNS registrars (for domain management)
- Certificate authorities (Let's Encrypt)

## Functional Requirements

### FR-1: Email Composition and Sending

**FR-1.1: Compose Email**
- **Priority**: MUST
- **Description**: User must be able to compose email messages with recipient, subject, and body
- **Acceptance Criteria**:
  - User can enter one or more recipients (To, CC, BCC)
  - User can enter subject line (unlimited length)
  - User can compose plain text message
  - User can compose HTML message
  - User can switch between plain text and HTML
  - User can save draft
  - User can discard draft

**FR-1.2: Attachments**
- **Priority**: MUST
- **Description**: User must be able to attach files to email
- **Acceptance Criteria**:
  - User can attach multiple files
  - Maximum file size: 25MB per file
  - Maximum total size: 35MB per message
  - Supported formats: All common file types
  - User can remove attached files before sending
  - File names preserved, including non-ASCII characters

**FR-1.3: Send Email**
- **Priority**: MUST
- **Description**: System must send email to recipient via SMTP
- **Acceptance Criteria**:
  - Email delivered within 5 minutes (under normal conditions)
  - DKIM signature applied automatically
  - SPF record verified
  - TLS encryption used for transmission
  - Delivery status tracked
  - User notified of delivery failure

**FR-1.4: Quota Enforcement**
- **Priority**: MUST
- **Description**: System must enforce daily sending quota
- **Acceptance Criteria**:
  - Default quota: 100 emails/day
  - Warning at 80% of quota
  - Sending disabled at 100% until midnight UTC
  - Quota resets daily at 00:00 UTC
  - Admin can adjust quota
  - Quota displayed in UI

### FR-2: Email Receiving and Reading

**FR-2.1: Receive Email**
- **Priority**: MUST
- **Description**: System must receive email from external senders
- **Acceptance Criteria**:
  - Receives email via SMTP on port 25
  - Stores email in local database
  - Notifies user of new email (desktop notification)
  - Accepts email from any sender
  - Rejects email if over size limit (50MB)
  - Spam filtering applied

**FR-2.2: Read Email**
- **Priority**: MUST
- **Description**: User must be able to read received email
- **Acceptance Criteria**:
  - Displays sender, subject, date, body
  - Renders plain text correctly
  - Renders HTML safely (no script execution)
  - Shows attachments with download option
  - Marks email as read when opened
  - Displays inline images (optional)

**FR-2.3: Folder Management**
- **Priority**: MUST
- **Description**: User must be able to organize email into folders
- **Acceptance Criteria**:
  - Default folders: Inbox, Sent, Drafts, Trash
  - User can create custom folders
  - User can rename folders (except defaults)
  - User can delete folders (except defaults)
  - User can move email between folders
  - Folder contents persist across sessions

**FR-2.4: Search**
- **Priority**: SHOULD
- **Description**: User should be able to search email
- **Acceptance Criteria**:
  - Search by sender
  - Search by subject
  - Search by body content
  - Search by date range
  - Search results sorted by relevance
  - Search completes within 1 second (for 10,000 messages)

### FR-3: Contact Management

**FR-3.1: Add Contact**
- **Priority**: SHOULD
- **Description**: User should be able to save contacts
- **Acceptance Criteria**:
  - User can add contact with name and email
  - Email address validated
  - Optional fields: phone, notes, PGP key
  - Duplicate detection
  - Contact list sortable

**FR-3.2: Auto-complete**
- **Priority**: SHOULD
- **Description**: Recipient fields should auto-complete from contacts
- **Acceptance Criteria**:
  - Suggests contacts as user types
  - Shows name and email
  - Selectable via keyboard or mouse
  - Learns from sent email

### FR-4: Security and Encryption

**FR-4.1: Transport Encryption**
- **Priority**: MUST
- **Description**: All email transmission must be encrypted
- **Acceptance Criteria**:
  - STARTTLS required for SMTP
  - TLS 1.2 minimum
  - Valid SSL certificate
  - Certificate auto-renewal
  - Reject connections without TLS

**FR-4.2: Storage Encryption**
- **Priority**: SHOULD
- **Description**: Local email storage should be encrypted
- **Acceptance Criteria**:
  - SQLite database encrypted with SQLCipher
  - User password required to unlock
  - Automatic lock after 30 minutes inactivity
  - Secure password storage (not plaintext)

**FR-4.3: PGP Support**
- **Priority**: SHOULD
- **Description**: System should support PGP encryption
- **Acceptance Criteria**:
  - User can generate PGP key pair
  - User can import existing keys
  - Auto-encrypt if recipient key available
  - Auto-decrypt received encrypted mail
  - Sign all outgoing mail (optional)
  - Verify signatures on incoming mail

### FR-5: Gateway Management

**FR-5.1: Gateway Status**
- **Priority**: MUST
- **Description**: User must see gateway connectivity status
- **Acceptance Criteria**:
  - Status indicator: Online/Offline/Error
  - Last successful connection timestamp
  - Current queue depth
  - Failed delivery count
  - Bandwidth usage (optional)

**FR-5.2: Queue Monitoring**
- **Priority**: SHOULD
- **Description**: User should be able to view outbound queue
- **Acceptance Criteria**:
  - List of queued messages
  - Delivery status per message
  - Retry count
  - Error messages (if failed)
  - Ability to remove from queue
  - Ability to retry failed messages

**FR-5.3: DNS Management**
- **Priority**: SHOULD
- **Description**: System should assist with DNS configuration
- **Acceptance Criteria**:
  - Generate SPF record
  - Generate DKIM record
  - Generate DMARC record
  - Verify DNS propagation
  - Display current DNS status
  - Instructions for manual DNS update

### FR-6: Mesh Networking

**FR-6.1: Join Mesh**
- **Priority**: COULD
- **Description**: User could join a WireGuard mesh network
- **Acceptance Criteria**:
  - User can import mesh invitation
  - WireGuard automatically configured
  - Mesh peers listed
  - Peer online status shown
  - Can remove from mesh

**FR-6.2: Mesh Communication**
- **Priority**: COULD
- **Description**: Email to mesh peers should route directly
- **Acceptance Criteria**:
  - Detect recipient is mesh peer
  - Route via WireGuard instead of internet
  - Faster delivery than internet route
  - Fallback to internet if mesh down

### FR-7: Backup and Restore

**FR-7.1: Backup**
- **Priority**: MUST
- **Description**: User must be able to backup email data
- **Acceptance Criteria**:
  - One-click backup to local file
  - Backup includes: messages, contacts, config, keys
  - Backup encrypted with password
  - Backup scheduled automatically (daily)
  - Old backups auto-deleted (30 day retention)

**FR-7.2: Restore**
- **Priority**: MUST
- **Description**: User must be able to restore from backup
- **Acceptance Criteria**:
  - One-click restore from backup file
  - Password required to decrypt
  - Option to restore selectively (messages only, contacts only, etc.)
  - Current data backed up before restore
  - Restore completes within 5 minutes (for 10,000 messages)

### FR-8: User Interface

**FR-8.1: Main Window**
- **Priority**: MUST
- **Description**: Application must have clear, functional UI
- **Acceptance Criteria**:
  - Three-pane layout: folders, message list, message view
  - Resizable panes
  - Folder tree on left
  - Message list with columns: from, subject, date, flags
  - Message preview pane
  - Toolbar with common actions
  - Status bar with queue/connection status

**FR-8.2: Accessibility**
- **Priority**: SHOULD
- **Description**: UI should be accessible
- **Acceptance Criteria**:
  - Keyboard navigation for all functions
  - Screen reader compatible
  - High contrast mode
  - Configurable font size
  - No color-only indicators

**FR-8.3: Settings Panel**
- **Priority**: MUST
- **Description**: User must be able to configure system
- **Acceptance Criteria**:
  - Account settings (name, email, password)
  - Server settings (gateway URL, ports)
  - Security settings (encryption, PGP)
  - Appearance settings (theme, font)
  - Notification settings
  - Quota settings
  - Backup settings

### FR-9: Installation and Setup

**FR-9.1: Installation**
- **Priority**: MUST
- **Description**: User must be able to install software easily
- **Acceptance Criteria**:
  - Single package for major distributions (deb, rpm, AppImage)
  - Installation completes in under 5 minutes
  - No manual dependency resolution required
  - Post-install configuration wizard
  - Uninstaller removes all components

**FR-9.2: First-Run Wizard**
- **Priority**: MUST
- **Description**: First launch must guide user through setup
- **Acceptance Criteria**:
  - Welcome screen with deployment options
  - Network configuration (static IP or VPS)
  - Domain and DNS setup
  - Email account creation
  - Password setup
  - Optional: PGP key generation
  - Optional: Mesh network join
  - Setup completes in under 10 minutes
  - Can skip and configure later

**FR-9.3: VPS Provisioning**
- **Priority**: SHOULD
- **Description**: Wizard should help provision VPS gateway
- **Acceptance Criteria**:
  - List of supported providers (Vultr, DigitalOcean, Linode)
  - API key input
  - One-click VPS creation
  - Automatic gateway deployment
  - DNS automatically configured
  - Progress tracking
  - Cost estimate shown before creation

### FR-10: Updates and Maintenance

**FR-10.1: Update Check**
- **Priority**: MUST
- **Description**: System must check for updates
- **Acceptance Criteria**:
  - Daily update check
  - User notified if update available
  - Changelog displayed
  - One-click update
  - Backup before update
  - Rollback if update fails

**FR-10.2: Diagnostics**
- **Priority**: SHOULD
- **Description**: System should include diagnostic tools
- **Acceptance Criteria**:
  - Port 25 connectivity test
  - DNS record validation
  - SSL certificate check
  - Database integrity check
  - Log viewer
  - Export diagnostic report

## Non-Functional Requirements

### NFR-1: Performance

**NFR-1.1: Application Startup**
- **Requirement**: Application must start in under 2 seconds
- **Measurement**: Time from launch to main window displayed
- **Priority**: MUST

**NFR-1.2: Email Sending**
- **Requirement**: Email must be queued within 500ms of user clicking send
- **Measurement**: Time from send click to queue confirmation
- **Priority**: MUST

**NFR-1.3: Email Delivery**
- **Requirement**: Queued email must be delivered within 5 minutes under normal conditions
- **Measurement**: Time from queue to successful delivery
- **Priority**: SHOULD

**NFR-1.4: Search Performance**
- **Requirement**: Search must return results within 1 second for 10,000 messages
- **Measurement**: Time from search query to results displayed
- **Priority**: SHOULD

**NFR-1.5: UI Responsiveness**
- **Requirement**: UI must remain responsive during all operations
- **Measurement**: No blocking operations >100ms on main thread
- **Priority**: MUST

### NFR-2: Scalability

**NFR-2.1: Message Storage**
- **Requirement**: System must handle 100,000+ messages without degradation
- **Measurement**: Performance tests with large datasets
- **Priority**: SHOULD

**NFR-2.2: Gateway Capacity**
- **Requirement**: Single gateway must support 100 concurrent users
- **Measurement**: Load testing with 100 simulated users
- **Priority**: SHOULD

**NFR-2.3: Mesh Network**
- **Requirement**: Mesh network must support up to 250 peers
- **Measurement**: WireGuard /24 network full capacity
- **Priority**: COULD

### NFR-3: Reliability

**NFR-3.1: Uptime**
- **Requirement**: Gateway service must achieve 99% uptime
- **Measurement**: Downtime tracking over 30 days
- **Priority**: SHOULD

**NFR-3.2: Data Integrity**
- **Requirement**: Zero data loss under normal operating conditions
- **Measurement**: No corruption in 10,000 send/receive cycles
- **Priority**: MUST

**NFR-3.3: Queue Persistence**
- **Requirement**: Outbound queue must survive system crashes
- **Measurement**: Messages not lost during forced shutdown
- **Priority**: MUST

**NFR-3.4: Automatic Recovery**
- **Requirement**: Services must auto-restart after failure
- **Measurement**: systemd watchdog triggers restart within 30 seconds
- **Priority**: SHOULD

### NFR-4: Security

**NFR-4.1: Password Security**
- **Requirement**: Passwords must be hashed with bcrypt cost factor 12
- **Measurement**: Code review and security audit
- **Priority**: MUST

**NFR-4.2: Transport Security**
- **Requirement**: All network communication must use TLS 1.2+
- **Measurement**: SSL Labs scan grade A or higher
- **Priority**: MUST

**NFR-4.3: Storage Security**
- **Requirement**: Email database must be encrypted at rest
- **Measurement**: File system examination shows encrypted data
- **Priority**: SHOULD

**NFR-4.4: Vulnerability Response**
- **Requirement**: Security patches must be released within 24 hours of disclosure
- **Measurement**: Time from CVE publication to patch release
- **Priority**: MUST

### NFR-5: Usability

**NFR-5.1: Learning Curve**
- **Requirement**: User should be able to send first email within 10 minutes of installation
- **Measurement**: User testing with non-experts
- **Priority**: SHOULD

**NFR-5.2: Error Messages**
- **Requirement**: Error messages must be clear and actionable
- **Measurement**: User testing and feedback
- **Priority**: MUST

**NFR-5.3: Documentation**
- **Requirement**: All features must be documented
- **Measurement**: Documentation coverage audit
- **Priority**: MUST

**NFR-5.4: Consistency**
- **Requirement**: UI must follow GNOME Human Interface Guidelines
- **Measurement**: Design review
- **Priority**: SHOULD

### NFR-6: Portability

**NFR-6.1: Distribution Support**
- **Requirement**: Must support Ubuntu 22.04+, Debian 12+, Fedora 38+
- **Measurement**: Installation tests on each distribution
- **Priority**: MUST

**NFR-6.2: Architecture Support**
- **Requirement**: Must support x86_64 and ARM64
- **Measurement**: Compilation and testing on both architectures
- **Priority**: SHOULD

**NFR-6.3: Hardware Requirements**
- **Requirement**: Must run on systems with 1GB RAM and 1 GHz CPU
- **Measurement**: Performance testing on minimum hardware
- **Priority**: MUST

### NFR-7: Maintainability

**NFR-7.1: Code Quality**
- **Requirement**: Code must maintain 80%+ test coverage
- **Measurement**: pytest-cov report
- **Priority**: SHOULD

**NFR-7.2: Documentation**
- **Requirement**: All public APIs must be documented
- **Measurement**: Documentation coverage tool
- **Priority**: MUST

**NFR-7.3: Code Style**
- **Requirement**: Code must follow PEP 8 style guide
- **Measurement**: flake8 and black checks
- **Priority**: SHOULD

**NFR-7.4: Logging**
- **Requirement**: All errors must be logged with context
- **Measurement**: Log review during testing
- **Priority**: MUST

### NFR-8: Compliance

**NFR-8.1: Email Standards**
- **Requirement**: Must comply with RFC 5321 (SMTP)
- **Measurement**: Protocol testing against reference implementation
- **Priority**: MUST

**NFR-8.2: Privacy**
- **Requirement**: Must comply with GDPR if handling EU users
- **Measurement**: Legal review
- **Priority**: SHOULD

**NFR-8.3: Accessibility**
- **Requirement**: Should comply with WCAG 2.1 Level AA
- **Measurement**: Accessibility audit
- **Priority**: SHOULD

### NFR-9: Resource Efficiency

**NFR-9.1: Memory Usage**
- **Requirement**: Client application must use <200MB RAM
- **Measurement**: Memory profiling under normal use
- **Priority**: SHOULD

**NFR-9.2: CPU Usage**
- **Requirement**: Idle CPU usage must be <1%
- **Measurement**: CPU monitoring over 1 hour idle
- **Priority**: SHOULD

**NFR-9.3: Disk Usage**
- **Requirement**: Application files must be <100MB
- **Measurement**: Package size measurement
- **Priority**: SHOULD

**NFR-9.4: Bandwidth**
- **Requirement**: Email delivery must use <150% of message size in bandwidth
- **Measurement**: Network monitoring during transmission
- **Priority**: SHOULD

### NFR-10: Cost Efficiency

**NFR-10.1: VPS Cost**
- **Requirement**: Gateway must run on $5/month VPS
- **Measurement**: Testing on minimum tier VPS instances
- **Priority**: MUST

**NFR-10.2: Bandwidth Cost**
- **Requirement**: 100 users must fit within 1TB/month bandwidth
- **Measurement**: Bandwidth usage extrapolation
- **Priority**: SHOULD

**NFR-10.3: Software Cost**
- **Requirement**: Core dependencies must be open source (zero cost)
- **Measurement**: License audit
- **Priority**: MUST

## Constraints

### Technical Constraints

**TC-1: Linux Only**
- **Description**: System will only support Linux operating systems
- **Rationale**: Resource constraints, target audience primarily uses Linux
- **Impact**: Windows and macOS users excluded

**TC-2: Python 3.11+**
- **Description**: System requires Python 3.11 or later
- **Rationale**: Modern language features and security improvements
- **Impact**: Older distributions may need Python upgrade

**TC-3: Port 25 Requirement**
- **Description**: Gateway must have port 25 access for receiving email
- **Rationale**: SMTP standard requires port 25 for MTA-to-MTA communication
- **Impact**: VPS or business internet required, residential internet insufficient

**TC-4: Domain Requirement**
- **Description**: User must own or control a domain name
- **Rationale**: Required for DNS records (MX, SPF, DKIM)
- **Impact**: Additional cost (~$12/year), technical knowledge needed

### Business Constraints

**BC-1: Budget**
- **Description**: Development budget: $50,000 for year 1
- **Rationale**: Self-funded project
- **Impact**: Limited scope, phased releases

**BC-2: Timeline**
- **Description**: MVP release target: 6 months
- **Rationale**: Market need is immediate
- **Impact**: Feature prioritization required

**BC-3: Team Size**
- **Description**: Development team: 1-2 people
- **Rationale**: Budget constraint
- **Impact**: Longer development time, narrower scope

### Legal Constraints

**LC-1: Anti-Spam Compliance**
- **Description**: Must implement anti-spam measures
- **Rationale**: CAN-SPAM Act and similar laws
- **Impact**: Quota enforcement, content filtering required

**LC-2: DMCA Compliance**
- **Description**: Must have abuse reporting mechanism
- **Rationale**: Safe harbor provisions
- **Impact**: Abuse contact required, takedown procedures needed

**LC-3: Data Privacy**
- **Description**: Must protect user privacy
- **Rationale**: GDPR, CCPA regulations
- **Impact**: No data mining, encryption required, export functionality

## Assumptions

**A-1: User Technical Skill**
- Users have basic Linux command line knowledge
- Users can follow installation instructions
- Users can configure DNS records (or will learn)

**A-2: Infrastructure Access**
- Users have reliable internet connection
- Users can obtain static IP or rent VPS
- ISPs allow outbound SMTP (port 587 minimum)

**A-3: Market Demand**
- Sufficient demand exists for independent email
- Users willing to pay one-time license fee
- Privacy concerns will drive adoption

**A-4: Technology Stability**
- Python 3.11+ will remain supported
- GTK 4.0 will remain stable
- SMTP protocol will not change significantly
- Let's Encrypt will continue free service

## Dependencies

### Software Dependencies

**Required**
- Python 3.11+
- GTK 4.0
- Postfix 3.5+
- SQLite 3.35+
- OpenSSL 3.0+

**Optional**
- WireGuard (for mesh networking)
- GnuPG 2.2+ (for PGP)
- SQLCipher 4.0+ (for database encryption)
- Rspamd (for spam filtering)

### Service Dependencies

**Critical**
- DNS registrar (for domain management)
- Let's Encrypt (for SSL certificates)
- VPS provider (for gateway hosting)

**Optional**
- Backblaze B2 (for remote backups)
- Vultr/DigitalOcean API (for automated provisioning)

## Acceptance Criteria

The project will be considered successful when:

**Milestone 1: MVP (Month 6)**
- [ ] User can install on Ubuntu 22.04
- [ ] User can send email to Gmail
- [ ] User can receive email from Outlook
- [ ] Sent/received email stored locally
- [ ] Gateway service runs on $5/month VPS
- [ ] 50 beta users successfully deployed

**Milestone 2: Public Beta (Month 9)**
- [ ] 500 active users
- [ ] <5% support ticket rate
- [ ] 99% uptime for managed gateways
- [ ] All MUST requirements implemented
- [ ] Documentation complete

**Milestone 3: 1.0 Release (Month 12)**
- [ ] 2000+ active users
- [ ] All MUST and SHOULD requirements implemented
- [ ] Security audit passed
- [ ] Performance targets met
- [ ] Community forum active
- [ ] Sustainable revenue model

## Out of Scope

The following are explicitly NOT included in version 1.0:

**OS-1: Mobile Clients**
- Android and iOS apps planned for v1.2
- Web interface planned for v1.3

**OS-2: Calendar Integration**
- CalDAV support planned for v1.5
- Not critical for email functionality

**OS-3: Corporate Features**
- Shared mailboxes
- Distribution lists
- Advanced delegation
- Centralized management

**OS-4: Migration Tools**
- Import from Gmail, Outlook, etc.
- May be added based on user demand

**OS-5: Advanced Filtering**
- Sieve scripting
- Complex rules
- Basic filtering sufficient for v1.0

## Glossary

**ASN**: Autonomous System Number - Unique identifier for network operators  
**DKIM**: DomainKeys Identified Mail - Email authentication method  
**DMARC**: Domain-based Message Authentication, Reporting and Conformance  
**GTK**: GIMP Toolkit - UI framework for Linux  
**MTA**: Mail Transfer Agent - Server that transfers email  
**MX Record**: Mail Exchange record - DNS record for email routing  
**NAT**: Network Address Translation  
**PGP**: Pretty Good Privacy - Encryption program  
**PTR Record**: Pointer record - Reverse DNS lookup  
**SPF**: Sender Policy Framework - Email authentication  
**TLS**: Transport Layer Security - Encryption protocol  
**VPS**: Virtual Private Server  

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-11 | Initial | First draft |

## Approval

This requirements document requires approval from:

- [ ] Product Owner
- [ ] Technical Lead
- [ ] Security Reviewer
- [ ] Legal Reviewer

## Conclusion

These requirements define the scope and criteria for unitMail version 1.0. Meeting the MUST requirements will produce a functional, independent email system. The SHOULD requirements enhance usability and competitiveness. COULD requirements provide differentiation but are not essential.

Success depends on delivering a reliable, secure system that genuinely gives users control over their email infrastructure while remaining practical and affordable.
