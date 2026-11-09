# TrustVault Guard - Project Requirements

## 1. Project Overview

TrustVault Guard is a secure document-sharing application developed for the Snovasys Fresher Hiring Challenge 2026.

The system provides controlled document access, role-based authorization, owner-managed permissions, AI-assisted recommendations, and a tamper-evident audit trail.

## 2. User Roles

### Administrator
- Monitor application users and activity.
- Review audit records.
- Check audit-chain integrity.

### Document Owner
- Upload and manage documents.
- View documents owned by the user.
- Grant and revoke document permissions.
- Review AI-assisted permission recommendations.
- Manage document metadata and supported content operations.

### Viewer
- Access documents only when authorized.
- Perform operations permitted by the assigned document permission.

## 3. Functional Requirements

### Authentication and Account Management

- The application shall support user registration.
- The application shall support login and logout.
- Passwords shall be stored using password hashing.
- Authenticated sessions shall be managed by Flask-Login.
- Public registration shall not allow Administrator role selection.
- Password changes shall require verification of the current password.

### Document Management

- Authorized owners shall be able to upload documents.
- Uploaded files shall be validated before storage.
- Documents shall be stored in private application storage.
- The application shall maintain document metadata and ownership.
- Owners shall be able to search and filter their documents.
- Supported document operations shall include metadata editing, content editing where supported, file replacement, and deletion.

### Permission Management

- Document owners shall control access to their documents.
- The application shall support view, download, and edit permissions.
- Permission grants shall be validated on the server.
- Owners shall be able to revoke active permissions.
- Protected operations shall check ownership or active permissions.
- Unauthorized operations shall be denied.
### AI-Assisted Permission Recommendations

- The application shall provide AI-assisted permission suggestions.
- The advisor shall use eligible recipient information.
- Suggested recipients shall be validated against eligible users.
- Suggested permissions shall be restricted to view, download, and edit.
- AI recommendations shall remain advisory.
- Actual permission granting shall require a separate owner-controlled operation.

### Audit and Administration

- Important document and permission activities shall be recorded.
- Audit events shall include relevant user, document, action, and timestamp information.
- Audit events shall be linked using SHA-256 hashes.
- The application shall verify previous-hash continuity and event hashes.
- Audit-chain integrity status shall be available for administrative monitoring.
- Denied access attempts shall be recorded where implemented.

## 4. Security Requirements

### Authentication Security
- Passwords shall not be stored as plaintext.
- Protected routes shall require authentication.
- Role restrictions shall be enforced by the server.

### Authorization Security
- Access shall be denied unless ownership or an appropriate active permission authorizes the operation.
- Users shall not be able to grant themselves document permissions through unauthorized routes.
- Revoked permissions shall not authorize subsequent access requests.
- Sensitive document operations shall perform server-side authorization checks.

### File Security
- File extensions shall be restricted to the configured allowlist.
- MIME type and file content shall be validated.
- Stored filenames shall be generated safely.
- Uploaded documents shall not be exposed through unrestricted public file paths.
- File access shall remain subject to authorization checks.

### Audit Security
- Audit records shall include hash-chain information.
- Hash-chain verification shall detect mismatched hashes and broken previous-hash links.
- The application shall refuse to append events when existing chain verification fails.

## 5. Non-Functional Requirements

- The application should have a modular Flask structure.
- The user interface should support the defined application roles.
- Sensitive operations should be validated on the server.
- The application should provide understandable error responses.
- Automated tests should cover important application and security behavior.
- Project documentation should describe implemented controls and accepted limitations.

## 6. Testing Requirements

The automated test suite should cover:

- Registration and authentication.
- Role-based access restrictions.
- Document upload validation.
- Document ownership and permission enforcement.
- Permission granting and revocation.
- Denied document access.
- Audit event creation.
- Audit hash-chain verification.
- AI recommendation output validation.
- Regression testing after debugging and integration changes.

### Recorded Test Result

**81 tests passed on November 9, 2026.**

This result records the automated test suite at the final verification point. It is not a guarantee that every possible attack or production scenario has been tested.

## 7. Deployment Requirements

- The application shall run with its required Python dependencies.
- A secure production secret key shall be configured through the deployment environment.
- Persistent storage shall be configured for production database and uploaded-file retention.
- Hosted AI recommendations shall require a reachable configured AI service.

## 8. Known Limitations

- The current Render SQLite deployment does not have a configured persistent disk.
- Local Ollama is not automatically accessible from the hosted application.
- The audit hash chain does not provide external immutable storage.
- Encryption at rest requires separate configuration and verification.
- Automated testing does not replace independent penetration testing.

## 9. Development and Verification Timeline

- **November 1-7, 2026:** Requirements, architecture, implementation, security controls, AI recommendations, testing, and initial deployment.
- **November 8, 2026:** Debugging, integration corrections, security-related fixes, and deployment troubleshooting.
- **November 9, 2026:** Final regression testing, documentation review, and deployment verification.
