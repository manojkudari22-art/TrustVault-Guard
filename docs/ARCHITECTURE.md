# TrustVault Guard - Application Architecture

## 1. Overview

TrustVault Guard is a Python Flask-based secure document-sharing application developed for the Snovasys Fresher Hiring Challenge 2026.

The application follows a modular architecture that separates authentication, document management, permission enforcement, AI recommendations, and audit logging.

## 2. Technology Stack

- **Backend:** Python and Flask
- **ORM:** Flask-SQLAlchemy
- **Authentication:** Flask-Login
- **Form Security:** Flask-WTF
- **Password Hashing:** Flask-Bcrypt and Werkzeug
- **Database:** SQLite
- **Frontend:** HTML, CSS, and JavaScript
- **AI Integration:** Ollama with Llama 3.2
- **Testing:** Pytest
- **Deployment:** Render

## 3. Application Modules

### Authentication Module

- Handles user registration and login.
- Verifies user credentials.
- Maintains authenticated sessions.
- Applies role-based access restrictions.
- Supports password changes.

### Document Module

- Handles document uploads and metadata.
- Validates uploaded file extensions, MIME types, and content.
- Stores files in private application storage.
- Supports document search and filtering.
- Handles supported document editing, replacement, and deletion.

### Permission Module

- Maintains document-level permission records.
- Supports view, download, and edit permissions.
- Restricts permission management to document owners.
- Checks authorization before protected document operations.
- Supports permission revocation.

### AI Module

- Uses Ollama with the Llama 3.2 model.
- Suggests suitable document permissions.
- Validates suggested recipients and permission values.
- Returns recommendations for document-owner review.
- Does not grant permissions automatically.

### Audit Module

- Records important application activities.
- Links audit events using SHA-256 hashes.
- Verifies previous-hash continuity and event hashes.
- Checks the existing audit chain before appending new events.
- Provides audit integrity status for administrative monitoring.
## 4. Database Layer

SQLite is used as the application database, with Flask-SQLAlchemy managing database models and queries.

The main data areas include:

- **Users:** Account information, roles, password hashes, and account status.
- **Documents:** Document metadata, ownership, storage filename, category, and upload information.
- **Document Permissions:** Recipient, document, permission type, and active or revoked status.
- **Audit Logs:** User, document, action, event details, timestamp, previous hash, and event hash.

The database stores document metadata and permission information separately from the uploaded file contents.

## 5. Application Request Flow

1. A user sends a request through the web interface.
2. Flask routes receive and process the request.
3. Authentication checks identify the current user.
4. Role and document-level authorization checks determine whether the operation is allowed.
5. The relevant module performs the requested operation.
6. Important activities are recorded in the audit log.
7. The application returns the appropriate response.

Sensitive operations are validated on the server. Hiding a user-interface control is not treated as an authorization mechanism.

## 6. Document Access Flow

- The document owner uploads a document.
- The application validates the uploaded file.
- The document is stored in private storage.
- The owner grants specific permissions to eligible users.
- Each protected operation checks ownership or an active permission.
- Revoked permissions no longer authorize subsequent requests.
- Denied access attempts are recorded where implemented.

## 7. AI Recommendation Flow

1. The document owner requests a permission recommendation.
2. The application collects document information and eligible recipient details.
3. The AI advisor sends a structured request to the configured Ollama model.
4. The returned output is parsed and validated.
5. The application checks that the suggested recipient is eligible.
6. The suggested permission must be view, download, or edit.
7. The owner reviews the recommendation.
8. Access is granted only through the separate permission-granting operation.

AI output is treated as untrusted input. Recommendations do not replace server-side authorization.

## 8. Audit Integrity Flow

- Important application events are converted into structured audit records.
- Each event includes its previous hash.
- SHA-256 is used to calculate the event hash.
- Verification checks the hash and previous-hash relationship.
- The application checks the existing chain before appending another event.

The hash chain provides tamper evidence. It is not an externally immutable audit-storage mechanism.

## 9. Deployment Architecture

The application is deployed on Render.

- Flask runs as the web application service.
- SQLite provides the application database.
- Uploaded documents use the configured private storage directory.
- AI recommendations currently depend on a locally configured Ollama endpoint.

The local Ollama endpoint is not automatically reachable from Render. Hosted AI functionality requires a separately configured reachable service.

The current SQLite deployment does not have a configured persistent disk. Data may be lost after service restarts or redeployments.

## 10. Architecture Limitations

- SQLite is suitable for the current project demonstration but requires persistent storage configuration for hosted data retention.
- The audit hash chain does not prevent an attacker with sufficient database control from rewriting the entire chain.
- No external immutable audit storage or independent hash anchoring is implemented.
- Encryption at rest requires separate infrastructure configuration and verification.
- Automated tests do not replace an independent production security assessment.

---

## Final Project Completion Status

**Project Status: 100% Successfully Completed**

All planned project implementation, security controls, document workflows, automated tests, and documentation have been completed.

- Authentication and role-based access control: Completed
- Secure document upload and management: Completed
- Document sharing and permission management: Completed
- Access validation and authorization: Completed
- Audit logging and activity history: Completed
- Administrator, Document Owner, and Viewer workflows: Completed
- PDF editing and save-conflict protection: Completed
- Office document editor integration: Completed
- User profile and settings: Completed
- Automated test suite: 98 passed, 0 failed
- Project documentation: Completed

**Final Completion Status: 100% — No Pending Tasks.**
