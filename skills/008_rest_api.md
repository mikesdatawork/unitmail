# Skill: REST API Endpoints

## What This Skill Does
Creates complete REST API endpoints for the unitMail Gateway service with JWT authentication.

## Endpoints

### Authentication (/api/v1/auth)
- `POST /login` - Login, returns JWT tokens
- `POST /logout` - Invalidate token
- `POST /refresh` - Refresh access token
- `GET /me` - Current user info
- `POST /password` - Change password

### Messages (/api/v1/messages)
- `GET /` - List with pagination, filters
- `GET /<id>` - Single message
- `POST /` - Send or save draft
- `PUT /<id>` - Update (move, flags)
- `DELETE /<id>` - Delete
- `POST /<id>/star` - Toggle star
- `POST /<id>/read` - Mark read/unread

### Contacts (/api/v1/contacts)
- Full CRUD operations
- Search and favorites filter

### Folders (/api/v1/folders)
- CRUD with system folder protection
- Message count summaries

### Queue (/api/v1/queue)
- List items, statistics
- Retry failed, batch operations

## Authentication
- JWT access tokens (15min)
- Refresh tokens (7 days)
- bcrypt password hashing
- Token blacklisting for revocation

## Decorators
- `@require_auth` - Require valid token
- `@require_admin` - Admin role required
- `@optional_auth` - Load user if present

## Schemas
Pydantic models for all requests/responses with validation.
