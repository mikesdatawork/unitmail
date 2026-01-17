# unitMail Project Overview

## Purpose

unitMail is an independent email system designed to give individuals complete control over their email infrastructure without reliance on cloud service providers like Gmail, Outlook, or other third-party email hosts.

## The Problem

Current email landscape issues:

**Vendor Lock-in**
- Users cannot access email if provider account is suspended
- Service outages affect thousands of users simultaneously
- Terms of service changes can restrict access
- Data scanning and privacy concerns

**Recent Example: Anthropic Email Failures**
- Critical emails to students, researchers, engineers, and scientists were blocked
- Users had no alternative access method
- Complete dependency on third-party infrastructure
- No control over deliverability issues

**Technical Barriers**
- ISPs block port 25 on residential connections
- Running personal mail servers requires significant expertise
- IP reputation systems favor large providers
- Complex DNS and authentication requirements

## The Solution

unitMail provides a self-contained email system where:

**Users Control**
- Email storage (local SQLite database)
- Mail server infrastructure (bundled microservice)
- Access credentials (no third-party authentication)
- Data privacy (no scanning or monitoring)

**System Features**
- Packaged GTK desktop application
- Embedded gateway microservice
- Local message storage
- Standard email compatibility (works with Gmail, Outlook, etc.)
- Optional peer-to-peer mesh networking
- Minimal cloud dependency

## Independence Philosophy

**What "Independent" Means**

1. **Data Sovereignty**: All email stored locally, encrypted at rest
2. **Infrastructure Control**: User owns or controls the mail gateway
3. **No Vendor Lock-in**: Open source, standard protocols, exportable data
4. **Minimal Cloud**: Gateway only converts protocols, never stores mail
5. **Portable**: User can move between ISPs, VPS providers without data loss

**What "Independent" Does NOT Mean**

- Complete isolation (system works with regular email)
- Zero internet dependency (email requires network)
- No costs (infrastructure costs exist but are minimized)
- Peer-to-peer only (hybrid model supports both)

## Target Users

**Primary Audience**
- Researchers and academics
- Privacy-conscious individuals
- Small organizations (5-50 people)
- Anyone burned by provider lockouts
- Linux users comfortable with basic system administration

**Not Designed For**
- Large enterprises (500+ users)
- Users requiring 24/7 commercial support
- Non-technical users unwilling to learn basics
- High-volume email marketers (explicitly blocked)

## Core Principles

**1. User Ownership**
- User owns the software (one-time license)
- User owns the data (local storage)
- User owns the infrastructure (self-hosted or controlled VPS)

**2. Privacy First**
- No email scanning
- No data mining
- No advertising
- Optional end-to-end encryption

**3. Cost Minimization**
- Open source components where possible
- Efficient resource usage (runs on old hardware)
- Low bandwidth requirements
- Transparent pricing (no hidden fees)

**4. Standard Compatibility**
- Works with existing email addresses
- SMTP/IMAP protocols
- Standard authentication (SPF/DKIM/DMARC)
- No proprietary lock-in

**5. Maintainability**
- Simple architecture
- Clear documentation
- Active community support
- Regular security updates

## Success Criteria

The project succeeds when:

1. **Technical**: User can send/receive email without port 25 at home
2. **Privacy**: Mail never stored on systems user doesn't control
3. **Cost**: Total cost under $10/month per user
4. **Reliability**: 99%+ uptime for gateway services
5. **Usability**: Non-expert Linux user can install and use
6. **Community**: Self-sustaining open source ecosystem

## Project Scope

**Phase 1: Minimum Viable Product (6 months)**
- GTK desktop client
- Gateway microservice (SMTP ↔ HTTPS conversion)
- SQLite storage with FTS5 search
- Basic send/receive functionality
- VPS deployment option
- 50 beta users

**Phase 2: Enhanced Features (12 months)**
- End-to-end encryption
- WireGuard mesh networking
- Mobile clients (Android/iOS)
- Backup/restore tools
- 500 active users

**Phase 3: Ecosystem (18+ months)**
- Plugin architecture
- Community-contributed features
- Multiple gateway providers (co-op model)
- Integration with existing tools
- 5000+ active users

## Differentiation

**vs Gmail/Outlook**
- No data mining
- User controls infrastructure
- Cannot be locked out

**vs Protonmail/Tutanota**
- Cheaper (one-time cost vs annual)
- More control (self-hosted option)
- Open source (auditable)

**vs Self-Hosted Postfix**
- Easier (bundled package)
- Works without port 25
- Automatic updates

**vs Peer-to-Peer Systems (Tor/I2P)**
- Faster (hybrid architecture)
- Compatible with regular email
- Better usability

## Business Model

**Software License**
- $99 one-time purchase
- Includes all updates for life
- Open source core (MIT)
- Premium features optional

**Gateway Service** (Optional)
- $5/month for managed gateway
- Or user runs own VPS ($3-5/month)
- Or user self-hosts with static IP

**Support Tiers**
- Community: Free (forums, documentation)
- Email: $50/year (48-hour response)
- Priority: $200/year (4-hour response)

## Revenue Projections

**Year 1**
- 100 users × $99 = $9,900
- 50 gateway users × $5 × 12 = $3,000
- Total: $12,900

**Year 2**
- 500 users × $99 = $49,500
- 250 gateway users × $5 × 12 = $15,000
- Total: $64,500

**Year 3**
- 2000 users × $99 = $198,000
- 1000 gateway users × $5 × 12 = $60,000
- Total: $258,000

## Risk Assessment

**Technical Risks**
- IP reputation challenges (mitigation: managed gateway)
- Spam filtering (mitigation: strict quotas, abuse monitoring)
- Complexity creep (mitigation: strict scope control)

**Business Risks**
- Low adoption (mitigation: target niche market first)
- Support costs (mitigation: strong documentation, community)
- Competition from free providers (mitigation: emphasize control/privacy)

**Legal Risks**
- DMCA liability (mitigation: proper abuse handling)
- Spam complaints (mitigation: enforcement mechanisms)
- Privacy regulations (mitigation: GDPR compliance by design)

## Conclusion

unitMail addresses a real problem: dependence on cloud email providers who can revoke access at will. By providing a self-contained, standards-compatible email system with minimal cloud dependency, users gain true ownership of their communications infrastructure.

The hybrid architecture (local storage + gateway conversion) balances independence with practicality, allowing users to communicate with the existing email ecosystem while maintaining control over their data and infrastructure.

Success depends on execution: building a reliable, usable system that delivers on the promise of independence without sacrificing compatibility or requiring expert knowledge.
