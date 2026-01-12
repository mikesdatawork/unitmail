# Port 25 Bridge Workaround

## Document Information

**Version**: 1.0  
**Date**: 2026-01-11  
**Purpose**: Technical explanation of how the bridge workaround enables email functionality when ISP blocks port 25

---

## The Port 25 Problem

Residential ISPs block port 25 in both directions:

- **Outbound**: Your machine cannot connect to port 25 on other mail servers
- **Inbound**: Other mail servers cannot connect to port 25 on your machine

This exists because spam botnets on home computers would abuse port 25 to send millions of spam messages. ISPs block it by default to prevent this.

**Result**: You cannot run a traditional mail server on residential internet.

---

## The Bridge Solution

A bridge (also called gateway or relay) sits between your home system and the internet. It has port 25 access. Your home system communicates with the bridge using a different protocol (HTTPS, WebSocket, etc.) that ISPs never block.

---

## Complete Architecture

```
YOUR HOME SYSTEM                    BRIDGE SERVER                    INTERNET
(No port 25)                        (Has port 25)                    (Standard SMTP)

┌──────────────┐                   ┌──────────────┐                 ┌──────────────┐
│              │                   │              │                 │              │
│  GTK Client  │                   │  Protocol    │                 │  Gmail       │
│  SQLite DB   │◄─── HTTPS ───────►│  Converter   │◄─── SMTP ──────►│  Outlook     │
│  Local Mail  │     Port 443      │              │     Port 25     │  Yahoo       │
│              │                   │              │                 │  Any Server  │
└──────────────┘                   └──────────────┘                 └──────────────┘
```

**Key Points:**

- Your system uses HTTPS (port 443) which is never blocked
- Bridge converts between HTTPS and SMTP
- Bridge has the port 25 access your home lacks
- Bridge can be a $5/month VPS you control

---

## Outbound Email Flow (Sending)

When you send an email, here is exactly what happens:

### Step 1: User Composes Email

User writes email in GTK client:

- To: recipient@gmail.com
- Subject: Meeting tomorrow
- Body: Let's meet at 2pm

Client stores message in local SQLite database with status "pending".

### Step 2: Client Packages Message

Client converts email into JSON payload:

```json
{
  "message_id": "abc123@unitmail.com",
  "from": "user@unitmail.com",
  "to": ["recipient@gmail.com"],
  "subject": "Meeting tomorrow",
  "body": "Let's meet at 2pm",
  "timestamp": "2026-01-11T15:30:00Z",
  "signature": "<HMAC signature for authentication>"
}
```

### Step 3: Client Sends to Bridge

Client makes HTTPS POST request to bridge:

```
POST https://gateway.unitmail.com/api/v1/send
Authorization: Bearer <user_token>
Content-Type: application/json

<JSON payload>
```

This uses port 443 (HTTPS). Every ISP allows this.

### Step 4: Bridge Authenticates User

Bridge receives request and:

1. Validates the Bearer token
2. Checks user exists and is active
3. Checks daily quota (has user sent 100 emails today?)
4. Validates recipient addresses
5. Checks for spam indicators

If any check fails, bridge returns error to client.

### Step 5: Bridge Converts to SMTP

Bridge constructs proper email message:

```
From: user@unitmail.com
To: recipient@gmail.com
Subject: Meeting tomorrow
Date: Sat, 11 Jan 2026 15:30:00 +0000
Message-ID: <abc123@unitmail.com>
DKIM-Signature: v=1; a=rsa-sha256; d=unitmail.com; ...

Let's meet at 2pm
```

Bridge adds:

- Proper email headers
- DKIM signature (proves message is from unitmail.com)
- Message-ID if not provided
- Date header

### Step 6: Bridge Performs DNS Lookup

Bridge needs to find Gmail's mail server:

```
Query: MX record for gmail.com
Response: gmail-smtp-in.l.google.com (priority 5)
          alt1.gmail-smtp-in.l.google.com (priority 10)
          ...
```

### Step 7: Bridge Connects via SMTP

Bridge opens connection to Gmail on port 25:

```
Bridge → Gmail: <connects to port 25>
Gmail → Bridge: 220 mx.google.com ESMTP ready
Bridge → Gmail: EHLO gateway.unitmail.com
Gmail → Bridge: 250-mx.google.com Hello
                250-STARTTLS
                250 OK
Bridge → Gmail: STARTTLS
<TLS negotiation happens>
Bridge → Gmail: MAIL FROM:<user@unitmail.com>
Gmail → Bridge: 250 OK
Bridge → Gmail: RCPT TO:<recipient@gmail.com>
Gmail → Bridge: 250 OK
Bridge → Gmail: DATA
Gmail → Bridge: 354 Start mail input
Bridge → Gmail: <entire email message>
Bridge → Gmail: .
Gmail → Bridge: 250 OK: Message queued
Bridge → Gmail: QUIT
Gmail → Bridge: 221 Bye
```

### Step 8: Bridge Reports Status

Bridge sends response back to client:

```json
{
  "status": "sent",
  "message_id": "abc123@unitmail.com",
  "remote_id": "gmail-queue-xyz789",
  "timestamp": "2026-01-11T15:30:05Z"
}
```

### Step 9: Client Updates Local Database

Client marks message as "sent" in SQLite. User sees green checkmark.

---

## Inbound Email Flow (Receiving)

When someone sends you an email, here is what happens:

### Step 1: External Sender Initiates

Someone at gmail.com sends to user@unitmail.com.

Gmail's server looks up MX record for unitmail.com:

```
Query: MX record for unitmail.com
Response: gateway.unitmail.com
```

### Step 2: Gmail Connects to Bridge

Gmail connects to your bridge server on port 25:

```
Gmail → Bridge: <connects to port 25>
Bridge → Gmail: 220 gateway.unitmail.com ESMTP ready
Gmail → Bridge: EHLO mail.gmail.com
Bridge → Gmail: 250-gateway.unitmail.com
                250-STARTTLS
                250 OK
Gmail → Bridge: STARTTLS
<TLS negotiation>
Gmail → Bridge: MAIL FROM:<sender@gmail.com>
Bridge → Gmail: 250 OK
Gmail → Bridge: RCPT TO:<user@unitmail.com>
Bridge → Gmail: 250 OK
Gmail → Bridge: DATA
Bridge → Gmail: 354 Start mail input
Gmail → Bridge: <entire email message>
Gmail → Bridge: .
Bridge → Gmail: 250 OK: Message accepted
Gmail → Bridge: QUIT
```

### Step 3: Bridge Receives and Validates

Bridge now has the email. It:

1. Verifies recipient (user@unitmail.com) exists
2. Checks SPF record of sender domain
3. Verifies DKIM signature if present
4. Runs spam scoring (Rspamd or similar)
5. Scans for viruses (ClamAV)
6. Checks sender against blacklists

If email fails checks, bridge rejects or quarantines.

### Step 4: Bridge Identifies Recipient's Home System

Bridge looks up user@unitmail.com in its database:

- User ID: 12345
- Callback URL: https://user.home.unitmail.com/inbox (or WebSocket connection)
- Public key: (for encryption if enabled)

### Step 5: Bridge Converts to JSON

Bridge converts email to JSON:

```json
{
  "message_id": "gmail-msg-456@mail.gmail.com",
  "from": "sender@gmail.com",
  "to": ["user@unitmail.com"],
  "subject": "Re: Meeting tomorrow",
  "body": "2pm works for me",
  "body_html": "<html>...",
  "received_at": "2026-01-11T15:35:00Z",
  "spam_score": 0.2,
  "dkim_valid": true,
  "spf_valid": true
}
```

### Step 6: Bridge Delivers to Home System

Three options:

**Option A: Push via WebSocket (Real-time)**

If user's system maintains persistent WebSocket connection:

```
Bridge → Home: {
  "event": "new_message",
  "data": <JSON email>
}
```

Home system receives instantly. Desktop notification pops up.

**Option B: Pull via Polling**

If user's system polls periodically:

```
Home → Bridge: GET /api/v1/messages?since=2026-01-11T15:30:00Z
Bridge → Home: {
  "messages": [<JSON email>]
}
```

Home system checks every 30 seconds for new mail.

**Option C: Push via HTTPS POST**

If user's home system accepts incoming connections (via port forwarding or tunnel):

```
Bridge → Home: POST https://user.home.unitmail.com/api/incoming
               <JSON email>
Home → Bridge: 200 OK
```

### Step 7: Home System Stores Email

Client receives JSON and:

1. Stores in local SQLite database
2. Shows desktop notification
3. Updates UI with new message
4. Marks as unread

Email is now safely on user's local machine. Bridge can delete its copy.

---

## Security Considerations

### Authentication Between Client and Bridge

Every request from client to bridge must be authenticated:

- OAuth tokens (like cloud services use)
- API keys with HMAC signatures
- Client certificates (mutual TLS)

Without this, anyone could send email as you.

### Encryption in Transit

All communication encrypted:

- Client ↔ Bridge: TLS 1.2+ (HTTPS)
- Bridge ↔ External: TLS via STARTTLS

No plaintext anywhere on the wire.

### Encryption at Rest

Options:

| Level | Bridge Storage | Privacy |
|-------|----------------|---------|
| Pass-through | Nothing stored | High |
| Temporary | Until delivered | Medium |
| End-to-end | Encrypted blob only | Maximum |

### Bridge Trust Level

**If bridge is pass-through:**

- Bridge sees metadata (from, to, subject)
- Bridge sees message body (unless E2E encrypted)
- Bridge does not store anything
- Bridge cannot read old messages

**If you don't trust the bridge, use end-to-end encryption:**

- Client encrypts message with recipient's public key
- Bridge relays encrypted blob
- Only recipient can decrypt

### Rate Limiting and Abuse Prevention

Bridge must prevent abuse:

| Limit | Value | Purpose |
|-------|-------|---------|
| Daily emails | 100 per user | Prevent spam |
| Recipients per message | 10 maximum | Prevent bulk mail |
| Identical messages | Blocked | Prevent campaigns |
| Keyword filtering | Active | Block bulk indicators |
| Account suspension | Automatic | Handle violations |

This keeps the bridge's IP reputation clean.

---

## Protocol Conversion Details

### SMTP to JSON (Inbound)

Bridge parses raw SMTP message:

```
Received: from mail.gmail.com ...
From: sender@gmail.com
To: user@unitmail.com
Subject: Hello
Date: Sat, 11 Jan 2026 15:00:00 +0000
Content-Type: text/plain; charset=utf-8

This is the message body.
```

Converts to structured JSON:

```json
{
  "headers": {
    "received": ["from mail.gmail.com ..."],
    "from": "sender@gmail.com",
    "to": ["user@unitmail.com"],
    "subject": "Hello",
    "date": "2026-01-11T15:00:00Z",
    "content_type": "text/plain"
  },
  "body": "This is the message body.",
  "body_html": null,
  "attachments": []
}
```

### JSON to SMTP (Outbound)

Bridge takes JSON from client:

```json
{
  "to": ["recipient@gmail.com"],
  "subject": "Reply",
  "body": "Got it, thanks"
}
```

Constructs proper email:

```
From: user@unitmail.com
To: recipient@gmail.com
Subject: Reply
Date: Sat, 11 Jan 2026 15:30:00 +0000
Message-ID: <unique-id@unitmail.com>
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
DKIM-Signature: v=1; a=rsa-sha256; d=unitmail.com; s=default;
    h=from:to:subject:date:message-id;
    bh=base64hash;
    b=base64signature

Got it, thanks
```

Bridge adds all required headers and signatures.

---

## Handling Edge Cases

### What if Bridge is Down?

Client queues message locally. Retries periodically. User sees "pending" status.

**Recovery:**

1. Client detects connection failure
2. Message remains in local queue
3. Client retries every 5 minutes
4. When bridge recovers, queue drains automatically
5. User notified of successful delivery

### What if Delivery Fails?

Bridge retries with exponential backoff:

| Attempt | Wait Time |
|---------|-----------|
| 1 | 5 minutes |
| 2 | 15 minutes |
| 3 | 1 hour |
| 4 | 4 hours |
| 5 | 24 hours |

After 7 days, gives up. Returns bounce message to sender.

### What if Home System is Offline?

Bridge queues incoming messages with limits:

- Maximum queue time: 7 days
- Maximum queue size: 1000 messages per user

When home system reconnects, it pulls all queued messages.

### What if Bridge IP Gets Blacklisted?

Response procedure:

1. Monitor blacklists automatically (Spamhaus, SORBS, Barracuda)
2. Alert admin immediately upon listing
3. Request delisting through proper channels
4. Rotate to backup IP if available
5. Investigate which user caused the issue
6. Suspend offending account if found

### What if Message is Too Large?

Bridge enforces limits:

| Limit | Value |
|-------|-------|
| Maximum message size | 35 MB |
| Maximum attachment | 25 MB |
| Maximum attachments | 20 files |

Rejects with clear error message. Client shows user-friendly explanation.

---

## Delivery Methods Comparison

### WebSocket (Recommended)

```
Home System                              Bridge
     │                                      │
     │◄──────── Persistent Connection ─────►│
     │                                      │
     │      (new email arrives at bridge)   │
     │                                      │
     │◄──────── Push: new_message ──────────│
     │                                      │
     │────────── ACK ──────────────────────►│
```

**Pros:**
- Real-time delivery (sub-second)
- Low bandwidth (single connection)
- Efficient for frequent updates

**Cons:**
- Requires persistent connection
- May need reconnection logic
- More complex implementation

### HTTP Polling

```
Home System                              Bridge
     │                                      │
     │────────── GET /messages ────────────►│
     │◄─────────── (empty) ─────────────────│
     │                                      │
     │       (30 seconds pass)              │
     │                                      │
     │────────── GET /messages ────────────►│
     │◄─────────── (1 new message) ─────────│
```

**Pros:**
- Simple implementation
- Works through any firewall
- Stateless

**Cons:**
- Delayed delivery (up to polling interval)
- Wastes bandwidth on empty polls
- Higher server load

### HTTP Push (Callback)

```
Home System                              Bridge
     │                                      │
     │  (email arrives, bridge pushes)      │
     │                                      │
     │◄──────── POST /incoming ─────────────│
     │────────── 200 OK ───────────────────►│
```

**Pros:**
- Real-time delivery
- Efficient (only when needed)
- Simple protocol

**Cons:**
- Home system needs public endpoint
- Requires port forwarding or tunnel
- Firewall complications

---

## Implementation Options

### Option 1: Self-Hosted Bridge (Full Control)

You run your own bridge on a $5/month VPS.

**Setup:**
- Rent VPS (Vultr, DigitalOcean, Linode)
- Install bridge software
- Configure DNS (MX, SPF, DKIM)
- Connect client to your bridge

**Pros:**
- Complete control
- No third-party sees your mail
- Can customize everything
- No monthly service fee beyond VPS

**Cons:**
- You manage the server
- You handle security updates
- You deal with blacklisting
- You provide your own uptime

**Cost:** $5-10/month for VPS

### Option 2: Managed Bridge (Convenience)

unitMail provides bridge service.

**Setup:**
- Sign up for service
- Configure client with provided credentials
- Done

**Pros:**
- No server management
- Shared IP reputation (already established)
- Automatic updates
- Professional support

**Cons:**
- Third party sees metadata
- Monthly fee
- Dependent on service availability
- Less customization

**Cost:** $5/month service fee

### Option 3: Federated Bridges (Community)

Multiple community members run bridges. Users choose which to trust.

**Setup:**
- Browse list of community bridges
- Select trusted bridge operator
- Configure client
- Optional: Run your own and join federation

**Pros:**
- Decentralized
- No single point of failure
- Community oversight
- Multiple options

**Cons:**
- Variable reliability
- Complex trust model
- Harder to maintain
- Requires coordination

**Cost:** Free to $5/month depending on operator

---

## DNS Configuration for Bridge

### Required Records

**MX Record (Mail Exchanger)**

```
unitmail.com.    IN  MX  10 gateway.unitmail.com.
```

Tells other mail servers where to deliver email for your domain.

**A Record (Bridge IP)**

```
gateway.unitmail.com.    IN  A    203.0.113.50
```

Points to bridge server's IP address.

**SPF Record (Sender Policy Framework)**

```
unitmail.com.    IN  TXT  "v=spf1 ip4:203.0.113.50 -all"
```

Tells receivers that only the bridge IP can send mail for this domain.

**DKIM Record (DomainKeys Identified Mail)**

```
default._domainkey.unitmail.com.  IN  TXT  "v=DKIM1; k=rsa; p=MIGfMA0..."
```

Public key for verifying email signatures.

**DMARC Record**

```
_dmarc.unitmail.com.  IN  TXT  "v=DMARC1; p=quarantine; rua=mailto:dmarc@unitmail.com"
```

Policy for handling authentication failures.

**PTR Record (Reverse DNS)**

```
50.113.0.203.in-addr.arpa.  IN  PTR  gateway.unitmail.com.
```

Reverse lookup must match forward lookup. Set by VPS provider.

---

## Bridge API Specification

### Authentication

**Request Token**

```
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@unitmail.com",
  "password": "secure_password"
}

Response:
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_at": "2026-01-12T15:30:00Z",
  "refresh_token": "abc123..."
}
```

### Send Email

```
POST /api/v1/messages/send
Authorization: Bearer <token>
Content-Type: application/json

{
  "to": ["recipient@example.com"],
  "cc": ["cc@example.com"],
  "subject": "Subject line",
  "body": "Plain text body",
  "body_html": "<html>HTML body</html>",
  "attachments": [
    {
      "filename": "file.pdf",
      "content_type": "application/pdf",
      "data": "<base64>"
    }
  ]
}

Response:
{
  "status": "queued",
  "message_id": "<unique-id@unitmail.com>",
  "queue_position": 1
}
```

### Fetch Messages

```
GET /api/v1/messages?since=2026-01-11T00:00:00Z&limit=50
Authorization: Bearer <token>

Response:
{
  "messages": [...],
  "total": 150,
  "has_more": true,
  "next_cursor": "abc123"
}
```

### Message Status

```
GET /api/v1/messages/<message_id>/status
Authorization: Bearer <token>

Response:
{
  "message_id": "<id>",
  "status": "delivered",
  "delivered_at": "2026-01-11T15:35:00Z",
  "recipient_server": "mx.google.com"
}
```

### WebSocket Connection

```
WSS /api/v1/stream
Authorization: Bearer <token>

→ {"action": "subscribe", "events": ["new_message", "status_update"]}
← {"event": "subscribed", "events": ["new_message", "status_update"]}

← {"event": "new_message", "data": {...}}
→ {"action": "ack", "message_id": "..."}
```

---

## Error Handling

### Client-Side Errors

| Error | Cause | Resolution |
|-------|-------|------------|
| Connection refused | Bridge down | Retry later, queue locally |
| 401 Unauthorized | Bad token | Re-authenticate |
| 403 Forbidden | Account suspended | Contact support |
| 429 Too Many Requests | Rate limited | Wait and retry |
| 500 Server Error | Bridge issue | Retry with backoff |

### Delivery Errors

| SMTP Code | Meaning | Action |
|-----------|---------|--------|
| 250 | Success | Mark delivered |
| 421 | Service unavailable | Retry in 5 min |
| 450 | Mailbox unavailable | Retry in 15 min |
| 550 | User unknown | Bounce immediately |
| 552 | Over quota | Bounce immediately |
| 554 | Spam rejected | Alert user, review content |

---

## Privacy Considerations

### What Bridge Sees

**Always visible to bridge:**
- Sender address
- Recipient address(es)
- Subject line
- Message timestamps
- Attachment filenames and sizes
- Your IP address

**Visible unless E2E encrypted:**
- Message body
- Attachment contents

### What Bridge Does NOT See (with E2E encryption)

- Decrypted message content
- Decrypted attachments
- Private encryption keys

### Minimizing Bridge Access

**Option 1: Run your own bridge**
- You are the only one with access
- Full control over data

**Option 2: Use E2E encryption**
- Bridge sees only encrypted blob
- Only recipient can decrypt

**Option 3: Ephemeral storage**
- Bridge deletes immediately after delivery
- No persistent storage

---

## Summary

The bridge workaround is simple in concept:

1. **Outbound**: Use HTTPS (port 443) to send email data to bridge
2. **Bridge converts**: Bridge converts to SMTP and delivers via port 25
3. **Inbound**: Bridge receives SMTP on port 25
4. **Bridge converts**: Bridge converts to HTTPS/WebSocket for delivery to you

Your home system never touches port 25. The bridge handles all SMTP. This bypasses ISP restrictions completely while maintaining compatibility with all existing email infrastructure.

**The key trade-off is trust:**

You must trust the bridge with your email metadata (and content unless using E2E encryption). Mitigate this by:

- Running your own bridge on a VPS you control
- Using end-to-end encryption
- Choosing a trusted community bridge operator

**Result:**

Full email functionality without port 25 access. Works on any residential internet connection. Compatible with Gmail, Outlook, and every other email provider.
