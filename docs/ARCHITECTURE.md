# TrustVault Architecture

## Technology Stack
- Backend: Python Flask
- Database: SQLite for development
- ORM: Flask-SQLAlchemy
- Authentication: Flask-Login
- Password Hashing: Flask-Bcrypt
- Forms and CSRF: Flask-WTF
- Testing: Pytest

## Application Modules
- Authentication
- Document Management
- Permission Management
- Audit Logging
- Admin

## Request Flow
1. User sends a request.
2. Flask route receives the request.
3. Authentication verifies the user identity.
4. Authorization checks the requested action.
5. The application performs the action only if permitted.
6. The audit module records the action.
7. The response is returned to the user.

## Security Design
- Default deny
- Centralized authorization checks
- Private file storage
- Permission checks on every document request
- Tamper-evident audit trail
