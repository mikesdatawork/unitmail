# Skill: SMTP Email Handling

## What This Skill Does
Implements complete SMTP functionality for receiving, sending, and queuing email.

## Components

### receiver.py - Incoming Mail
- `SMTPReceiver` - aiosmtpd-based async SMTP server
- Listens on port 25 with STARTTLS support
- Validates sender/recipient addresses
- Size limit enforcement (50MB default)
- Stores to Supabase via parser

### parser.py - Email Parsing
- `EmailParser` - Parse raw SMTP messages
- Extract headers, body (text/HTML), attachments
- Handle MIME multipart, base64, quoted-printable
- RFC 2047 encoded header support

### sender.py - Outgoing Mail
- `SMTPSender` - Async SMTP client
- MX record DNS lookup
- STARTTLS encryption
- Retry with exponential backoff
- Relay server support with auth

### composer.py - Message Building
- `EmailComposer` - Build MIME messages
- Headers, attachments, HTML/text bodies
- Message-ID generation
- Reply/forward composition

### queue.py - Queue Management
- `QueueManager` - Worker pool pattern
- Exponential backoff (5m, 15m, 1h, 4h, 24h)
- Dead letter queue after max retries
- Real-time status events

### worker.py - Queue Processing
- `QueueWorker` - Process individual messages
- Atomic message claiming
- Error classification (temp vs permanent)
- Timeout handling

## Usage
```bash
# Run SMTP receiver
python -c "from src.gateway.smtp import run_smtp_receiver; run_smtp_receiver()"

# Run queue worker
python scripts/queue_worker.py --workers 4
```
