# unitMail API Reference

This document provides complete documentation for the unitMail REST API, including authentication, endpoints, request/response formats, error handling, and rate limits.

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
  - [Authentication Endpoints](#authentication-endpoints)
  - [Message Endpoints](#message-endpoints)
  - [Folder Endpoints](#folder-endpoints)
  - [Contact Endpoints](#contact-endpoints)
  - [Queue Endpoints](#queue-endpoints)
  - [System Endpoints](#system-endpoints)
- [Error Codes](#error-codes)
- [Rate Limits](#rate-limits)
- [WebSocket API](#websocket-api)

---

## Overview

### Base URL

```
https://api.yourdomain.com/api/v1
```

For local development:
```
http://localhost:8000/api/v1
```

### Request Format

- All requests must include `Content-Type: application/json` header
- Request bodies must be valid JSON
- UTF-8 encoding is required

### Response Format

All responses follow this structure:

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "timestamp": "2026-01-11T12:00:00Z",
    "request_id": "req_abc123"
  }
}
```

Error responses:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": { ... }
  },
  "meta": {
    "timestamp": "2026-01-11T12:00:00Z",
    "request_id": "req_abc123"
  }
}
```

---

## Authentication

### Obtaining a Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Response**:

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "expires_at": "2026-01-11T13:00:00Z"
  }
}
```

### Using the Token

Include the token in the `Authorization` header:

```http
GET /api/v1/messages
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Refreshing Tokens

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response**:

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600,
    "expires_at": "2026-01-11T14:00:00Z"
  }
}
```

### Logout

```http
POST /api/v1/auth/logout
Authorization: Bearer <token>
```

**Response**:

```json
{
  "success": true,
  "data": {
    "message": "Successfully logged out"
  }
}
```

---

## API Endpoints

### Authentication Endpoints

#### POST /api/v1/auth/login

Authenticate user and obtain tokens.

**Request**:

```json
{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "expires_at": "2026-01-11T13:00:00Z",
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "name": "John Doe"
    }
  }
}
```

**Error Response** (401 Unauthorized):

```json
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid email or password"
  }
}
```

---

#### POST /api/v1/auth/register

Register a new user account.

**Request**:

```json
{
  "email": "newuser@example.com",
  "password": "secure_password_123",
  "name": "Jane Doe"
}
```

**Response** (201 Created):

```json
{
  "success": true,
  "data": {
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "email": "newuser@example.com",
      "name": "Jane Doe",
      "created_at": "2026-01-11T12:00:00Z"
    },
    "message": "Account created successfully"
  }
}
```

---

#### POST /api/v1/auth/password/reset

Request password reset email.

**Request**:

```json
{
  "email": "user@example.com"
}
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "message": "If an account exists, a reset email has been sent"
  }
}
```

---

### Message Endpoints

#### GET /api/v1/messages

List messages with filtering and pagination.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `folder` | string | inbox | Folder to list (inbox, sent, drafts, trash, or folder ID) |
| `limit` | integer | 50 | Messages per page (max 100) |
| `offset` | integer | 0 | Pagination offset |
| `sort` | string | received_at | Sort field (received_at, from_addr, subject) |
| `order` | string | desc | Sort order (asc, desc) |
| `unread` | boolean | - | Filter by unread status |
| `starred` | boolean | - | Filter by starred status |
| `has_attachments` | boolean | - | Filter by attachment presence |
| `search` | string | - | Search query |

**Request**:

```http
GET /api/v1/messages?folder=inbox&limit=20&unread=true
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "messages": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440010",
        "message_id": "<abc123@example.com>",
        "from_addr": "sender@example.com",
        "to_addr": ["user@example.com"],
        "subject": "Meeting Tomorrow",
        "preview": "Hi, just wanted to confirm our meeting...",
        "flags": {
          "read": false,
          "starred": true,
          "important": false
        },
        "has_attachments": true,
        "attachment_count": 2,
        "encrypted": false,
        "received_at": "2026-01-11T10:30:00Z"
      }
    ],
    "pagination": {
      "total": 150,
      "limit": 20,
      "offset": 0,
      "has_more": true
    }
  }
}
```

---

#### GET /api/v1/messages/{id}

Get full message details.

**Request**:

```http
GET /api/v1/messages/550e8400-e29b-41d4-a716-446655440010
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440010",
    "message_id": "<abc123@example.com>",
    "from_addr": "sender@example.com",
    "to_addr": ["user@example.com"],
    "cc_addr": ["colleague@example.com"],
    "bcc_addr": [],
    "subject": "Meeting Tomorrow",
    "body": "Hi,\n\nJust wanted to confirm our meeting tomorrow at 2 PM.\n\nBest regards,\nSender",
    "body_html": "<html><body><p>Hi,</p><p>Just wanted to confirm our meeting tomorrow at 2 PM.</p><p>Best regards,<br>Sender</p></body></html>",
    "flags": {
      "read": true,
      "starred": true,
      "important": false
    },
    "attachments": [
      {
        "id": "att_001",
        "filename": "agenda.pdf",
        "content_type": "application/pdf",
        "size": 125000
      },
      {
        "id": "att_002",
        "filename": "notes.docx",
        "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size": 45000
      }
    ],
    "encrypted": false,
    "created_at": "2026-01-11T10:28:00Z",
    "received_at": "2026-01-11T10:30:00Z"
  }
}
```

---

#### POST /api/v1/messages/send

Send a new email message.

**Request**:

```json
{
  "to": ["recipient@example.com"],
  "cc": ["cc@example.com"],
  "bcc": [],
  "subject": "Project Update",
  "body": "Hi,\n\nHere's the latest update on the project.\n\nBest,\nYour Name",
  "body_html": "<html><body><p>Hi,</p><p>Here's the latest update on the project.</p><p>Best,<br>Your Name</p></body></html>",
  "attachments": [
    {
      "filename": "report.pdf",
      "content_type": "application/pdf",
      "data": "base64_encoded_content_here"
    }
  ],
  "encrypt": false,
  "sign": true
}
```

**Response** (202 Accepted):

```json
{
  "success": true,
  "data": {
    "message_id": "<generated-id@yourdomain.com>",
    "queue_id": "q_abc123",
    "status": "queued",
    "recipients": [
      {
        "email": "recipient@example.com",
        "status": "queued"
      },
      {
        "email": "cc@example.com",
        "status": "queued"
      }
    ]
  }
}
```

---

#### PUT /api/v1/messages/{id}

Update message properties (flags, folder).

**Request**:

```json
{
  "flags": {
    "read": true,
    "starred": false
  },
  "folder": "550e8400-e29b-41d4-a716-446655440020"
}
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440010",
    "flags": {
      "read": true,
      "starred": false,
      "important": false
    },
    "folder": "550e8400-e29b-41d4-a716-446655440020"
  }
}
```

---

#### DELETE /api/v1/messages/{id}

Delete a message (moves to trash, or permanently deletes if already in trash).

**Request**:

```http
DELETE /api/v1/messages/550e8400-e29b-41d4-a716-446655440010
Authorization: Bearer <token>
```

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `permanent` | boolean | false | Permanently delete (bypass trash) |

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "message": "Message moved to trash",
    "recoverable": true,
    "deleted_at": "2026-01-11T12:00:00Z"
  }
}
```

---

#### GET /api/v1/messages/{id}/attachments/{attachment_id}

Download an attachment.

**Request**:

```http
GET /api/v1/messages/550e8400-e29b-41d4-a716-446655440010/attachments/att_001
Authorization: Bearer <token>
```

**Response** (200 OK):

Returns the raw file content with appropriate Content-Type and Content-Disposition headers.

---

### Folder Endpoints

#### GET /api/v1/folders

List all folders.

**Request**:

```http
GET /api/v1/folders
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "folders": [
      {
        "id": "inbox",
        "name": "Inbox",
        "is_system": true,
        "unread_count": 5,
        "total_count": 150
      },
      {
        "id": "sent",
        "name": "Sent",
        "is_system": true,
        "unread_count": 0,
        "total_count": 75
      },
      {
        "id": "drafts",
        "name": "Drafts",
        "is_system": true,
        "unread_count": 0,
        "total_count": 3
      },
      {
        "id": "trash",
        "name": "Trash",
        "is_system": true,
        "unread_count": 0,
        "total_count": 10
      },
      {
        "id": "550e8400-e29b-41d4-a716-446655440020",
        "name": "Work",
        "is_system": false,
        "parent_id": null,
        "unread_count": 2,
        "total_count": 45
      },
      {
        "id": "550e8400-e29b-41d4-a716-446655440021",
        "name": "Projects",
        "is_system": false,
        "parent_id": "550e8400-e29b-41d4-a716-446655440020",
        "unread_count": 1,
        "total_count": 20
      }
    ]
  }
}
```

---

#### POST /api/v1/folders

Create a new folder.

**Request**:

```json
{
  "name": "Personal",
  "parent_id": null
}
```

**Response** (201 Created):

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440025",
    "name": "Personal",
    "is_system": false,
    "parent_id": null,
    "created_at": "2026-01-11T12:00:00Z"
  }
}
```

---

#### PUT /api/v1/folders/{id}

Rename a folder.

**Request**:

```json
{
  "name": "Personal Projects"
}
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440025",
    "name": "Personal Projects",
    "is_system": false
  }
}
```

---

#### DELETE /api/v1/folders/{id}

Delete a folder (messages are moved to Inbox).

**Request**:

```http
DELETE /api/v1/folders/550e8400-e29b-41d4-a716-446655440025
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "message": "Folder deleted",
    "messages_moved": 15
  }
}
```

---

### Contact Endpoints

#### GET /api/v1/contacts

List contacts with search and pagination.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Contacts per page |
| `offset` | integer | 0 | Pagination offset |
| `search` | string | - | Search by name or email |

**Request**:

```http
GET /api/v1/contacts?search=john&limit=10
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "contacts": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440030",
        "name": "John Doe",
        "email": "john@example.com",
        "has_pgp_key": true,
        "notes": "Met at conference",
        "created_at": "2025-06-15T10:00:00Z"
      },
      {
        "id": "550e8400-e29b-41d4-a716-446655440031",
        "name": "Johnny Smith",
        "email": "johnny@example.com",
        "has_pgp_key": false,
        "notes": null,
        "created_at": "2025-08-20T14:30:00Z"
      }
    ],
    "pagination": {
      "total": 2,
      "limit": 10,
      "offset": 0,
      "has_more": false
    }
  }
}
```

---

#### POST /api/v1/contacts

Create a new contact.

**Request**:

```json
{
  "name": "Jane Smith",
  "email": "jane@example.com",
  "notes": "Colleague from marketing",
  "pgp_key": "-----BEGIN PGP PUBLIC KEY BLOCK-----\n..."
}
```

**Response** (201 Created):

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440035",
    "name": "Jane Smith",
    "email": "jane@example.com",
    "has_pgp_key": true,
    "notes": "Colleague from marketing",
    "created_at": "2026-01-11T12:00:00Z"
  }
}
```

---

#### GET /api/v1/contacts/{id}

Get contact details.

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440035",
    "name": "Jane Smith",
    "email": "jane@example.com",
    "pgp_key": "-----BEGIN PGP PUBLIC KEY BLOCK-----\n...",
    "pgp_fingerprint": "ABCD 1234 EFGH 5678 IJKL 9012 MNOP 3456 QRST 7890",
    "notes": "Colleague from marketing",
    "created_at": "2026-01-11T12:00:00Z"
  }
}
```

---

#### PUT /api/v1/contacts/{id}

Update a contact.

**Request**:

```json
{
  "name": "Jane Smith-Johnson",
  "notes": "Now in sales department"
}
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440035",
    "name": "Jane Smith-Johnson",
    "email": "jane@example.com",
    "notes": "Now in sales department"
  }
}
```

---

#### DELETE /api/v1/contacts/{id}

Delete a contact.

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "message": "Contact deleted"
  }
}
```

---

### Queue Endpoints

#### GET /api/v1/queue

List messages in the outbound queue.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | all | Filter by status (pending, processing, sent, failed, deferred) |
| `limit` | integer | 50 | Items per page |
| `offset` | integer | 0 | Pagination offset |

**Request**:

```http
GET /api/v1/queue?status=pending
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "q_abc123",
        "message_id": "<msg123@yourdomain.com>",
        "to_addr": "recipient@example.com",
        "subject": "Project Update",
        "status": "pending",
        "attempts": 0,
        "last_attempt": null,
        "error_message": null,
        "created_at": "2026-01-11T12:00:00Z"
      }
    ],
    "summary": {
      "pending": 1,
      "processing": 0,
      "sent": 45,
      "failed": 2,
      "deferred": 0
    },
    "pagination": {
      "total": 1,
      "limit": 50,
      "offset": 0
    }
  }
}
```

---

#### POST /api/v1/queue/{id}/retry

Retry a failed message.

**Request**:

```http
POST /api/v1/queue/q_abc123/retry
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": "q_abc123",
    "status": "pending",
    "message": "Message queued for retry"
  }
}
```

---

#### DELETE /api/v1/queue/{id}

Remove a message from the queue (cancel sending).

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "message": "Message removed from queue"
  }
}
```

---

### System Endpoints

#### GET /api/v1/health

Health check endpoint (no authentication required).

**Response** (200 OK):

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-01-11T12:00:00Z",
  "components": {
    "database": "healthy",
    "smtp": "healthy",
    "queue": "healthy"
  }
}
```

---

#### GET /api/v1/status

Get detailed system status (requires authentication).

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "gateway": {
      "status": "online",
      "uptime": 86400,
      "version": "0.1.0"
    },
    "queue": {
      "depth": 5,
      "processing": 1,
      "failed_24h": 2
    },
    "quota": {
      "used": 15,
      "limit": 100,
      "resets_at": "2026-01-12T00:00:00Z"
    },
    "dns": {
      "spf": "valid",
      "dkim": "valid",
      "dmarc": "valid",
      "mx": "valid"
    }
  }
}
```

---

#### GET /api/v1/user

Get current user information.

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2025-01-01T00:00:00Z",
    "quota": {
      "daily_limit": 100,
      "used_today": 15
    },
    "settings": {
      "signature": "Best regards,\nJohn",
      "default_folder": "inbox"
    }
  }
}
```

---

#### PUT /api/v1/user

Update user settings.

**Request**:

```json
{
  "name": "John D. Doe",
  "settings": {
    "signature": "Regards,\nJohn D."
  }
}
```

**Response** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "John D. Doe",
    "settings": {
      "signature": "Regards,\nJohn D."
    }
  }
}
```

---

## Error Codes

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request succeeded |
| 201 | Created - Resource created |
| 202 | Accepted - Request accepted for processing |
| 400 | Bad Request - Invalid request format |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Resource conflict (e.g., duplicate) |
| 422 | Unprocessable Entity - Validation error |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |
| 503 | Service Unavailable - Service temporarily down |

### Application Error Codes

| Code | Description |
|------|-------------|
| `INVALID_CREDENTIALS` | Email or password incorrect |
| `TOKEN_EXPIRED` | Authentication token has expired |
| `TOKEN_INVALID` | Authentication token is invalid |
| `VALIDATION_ERROR` | Request validation failed |
| `RESOURCE_NOT_FOUND` | Requested resource not found |
| `DUPLICATE_RESOURCE` | Resource already exists |
| `PERMISSION_DENIED` | User lacks permission |
| `QUOTA_EXCEEDED` | Daily sending quota exceeded |
| `RATE_LIMITED` | Too many requests |
| `MESSAGE_TOO_LARGE` | Message exceeds size limit |
| `INVALID_RECIPIENT` | Recipient address invalid |
| `ATTACHMENT_ERROR` | Attachment processing failed |
| `ENCRYPTION_ERROR` | Encryption/decryption failed |
| `SMTP_ERROR` | SMTP operation failed |
| `DATABASE_ERROR` | Database operation failed |
| `INTERNAL_ERROR` | Unexpected server error |

### Error Response Examples

**Validation Error**:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": {
      "email": ["Invalid email format"],
      "password": ["Password must be at least 12 characters"]
    }
  }
}
```

**Quota Exceeded**:

```json
{
  "success": false,
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "Daily sending quota exceeded",
    "details": {
      "limit": 100,
      "used": 100,
      "resets_at": "2026-01-12T00:00:00Z"
    }
  }
}
```

---

## Rate Limits

### Default Limits

| Endpoint Category | Limit | Window |
|-------------------|-------|--------|
| Authentication | 5 requests | 15 minutes |
| Messages (read) | 100 requests | 1 minute |
| Messages (send) | 100 messages | 24 hours |
| Contacts | 100 requests | 1 minute |
| General API | 100 requests | 1 minute |

### Rate Limit Headers

All responses include rate limit information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704974400
X-RateLimit-Window: 60
```

### Exceeded Rate Limit Response

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45

{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded",
    "details": {
      "limit": 100,
      "window": 60,
      "retry_after": 45
    }
  }
}
```

---

## WebSocket API

Real-time updates are available via WebSocket connection.

### Connection

```javascript
const ws = new WebSocket('wss://api.yourdomain.com/api/v1/stream');

// Authenticate after connection
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'your_access_token'
  }));
};
```

### Subscribe to Events

```javascript
// Subscribe to events
ws.send(JSON.stringify({
  type: 'subscribe',
  events: ['new_message', 'queue_update', 'message_status']
}));
```

### Event Types

#### new_message

Received when a new email arrives.

```json
{
  "type": "new_message",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440010",
    "from_addr": "sender@example.com",
    "subject": "New Email",
    "preview": "First 100 characters...",
    "received_at": "2026-01-11T12:00:00Z"
  }
}
```

#### queue_update

Received when queue status changes.

```json
{
  "type": "queue_update",
  "data": {
    "queue_id": "q_abc123",
    "status": "sent",
    "message": "Message delivered successfully"
  }
}
```

#### message_status

Received when a message status changes (read, starred, etc.).

```json
{
  "type": "message_status",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440010",
    "flags": {
      "read": true
    }
  }
}
```

### Heartbeat

The server sends periodic heartbeats:

```json
{
  "type": "heartbeat",
  "timestamp": "2026-01-11T12:00:00Z"
}
```

Respond with:

```json
{
  "type": "pong"
}
```

### Disconnect

```javascript
ws.send(JSON.stringify({
  type: 'disconnect'
}));
ws.close();
```

---

## SDK Examples

### Python

```python
import requests

class UnitMailClient:
    def __init__(self, base_url, email, password):
        self.base_url = base_url
        self.session = requests.Session()
        self._login(email, password)

    def _login(self, email, password):
        response = self.session.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password}
        )
        data = response.json()
        self.token = data["data"]["access_token"]
        self.session.headers["Authorization"] = f"Bearer {self.token}"

    def list_messages(self, folder="inbox", limit=50):
        response = self.session.get(
            f"{self.base_url}/messages",
            params={"folder": folder, "limit": limit}
        )
        return response.json()["data"]["messages"]

    def send_message(self, to, subject, body):
        response = self.session.post(
            f"{self.base_url}/messages/send",
            json={
                "to": to if isinstance(to, list) else [to],
                "subject": subject,
                "body": body
            }
        )
        return response.json()["data"]

# Usage
client = UnitMailClient(
    "https://api.yourdomain.com/api/v1",
    "user@example.com",
    "password"
)

messages = client.list_messages()
client.send_message("recipient@example.com", "Hello", "Message body")
```

### JavaScript/TypeScript

```typescript
class UnitMailClient {
  private baseUrl: string;
  private token: string = '';

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async login(email: string, password: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await response.json();
    this.token = data.data.access_token;
  }

  async listMessages(folder = 'inbox', limit = 50): Promise<any[]> {
    const response = await fetch(
      `${this.baseUrl}/messages?folder=${folder}&limit=${limit}`,
      { headers: { 'Authorization': `Bearer ${this.token}` } }
    );
    const data = await response.json();
    return data.data.messages;
  }

  async sendMessage(to: string[], subject: string, body: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/messages/send`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ to, subject, body })
    });
    return (await response.json()).data;
  }
}

// Usage
const client = new UnitMailClient('https://api.yourdomain.com/api/v1');
await client.login('user@example.com', 'password');
const messages = await client.listMessages();
await client.sendMessage(['recipient@example.com'], 'Hello', 'Message body');
```

---

## Additional Resources

- [Architecture Documentation](/docs/ARCHITECTURE.md)
- [Admin Guide](/docs/ADMIN_GUIDE.md)
- [GitHub Repository](https://github.com/unitmail/unitmail)
- [Community Forum](https://forum.unitmail.org)
