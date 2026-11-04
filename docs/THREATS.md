# TrustVault Guard Threat Model

## Assets
- Confidential documents
- User credentials
- Document permissions
- Audit records

## Threats
1. Unauthorized user reads a confidential document.
2. User downloads a document after permission is revoked.
3. Attacker uploads a malicious file.
4. User changes document permissions without authorization.
5. Attacker tampers with audit records.
6. Attacker accesses another user's account.

## Mitigations
1. Check permissions on every document request.
2. Store files outside the public web directory.
3. Hash passwords using a secure password hashing algorithm.
4. Validate uploaded file types and sizes.
5. Use centralized authorization logic.
6. Record security-sensitive actions in audit logs.
7. Test access control with automated tests.

## Security Principle
Default deny: Unless access is explicitly granted, the user must not access the document.

## 2026-11-02 — Day 2: Authentication and Roles

### Threat: Unauthorized account access
**Risk:** An attacker may try to access another user's account using incorrect credentials.

**Mitigation:** Passwords are stored as hashes. Login validates the submitted password against the stored hash.

**Status:** Basic protection implemented. Account lockout and rate limiting are pending.

### Threat: Privilege escalation
**Risk:** A Viewer may attempt to access Administrator or Document Owner routes.

**Mitigation:** Protected routes check the authenticated user's role on the server.

**Validation:** Tests confirm that Viewers receive HTTP 403 when accessing protected Admin and Owner routes.

### Threat: Unauthorized role assignment
**Risk:** A user may attempt to register with elevated privileges.

**Mitigation:** New registrations receive the Viewer role by default. Role selection is not exposed in the registration form.

**Status:** Implemented. Secure administrator-managed role assignment is pending.

### Threat: Session misuse
**Risk:** An unauthenticated user may attempt to access protected dashboards.

**Mitigation:** Flask-Login requires authentication before protected dashboard access.

**Validation:** Authentication tests verify protected route access.

### Day 2 Security Validation
- Authentication tests passed: 8/8.
- Role-based access checks are enforced server-side.
- Further security hardening is pending.


## 2026-11-04 — Day 4: Document Management

### Threat: Malicious or invalid file uploads
**Risk:** An attacker may upload an unsupported file type disguised with a misleading filename or MIME type.

**Mitigation:** The upload route checks the file extension and MIME type against an allowed-file list.

**Status:** Basic server-side validation implemented. Additional content inspection and security testing are pending.

### Threat: Stored filename collision or filename manipulation
**Risk:** User-controlled filenames may cause collisions or create unsafe storage paths.

**Mitigation:** The application generates UUID-based server-side filenames and uses sanitized original filenames for document metadata.

**Status:** Implemented in the upload flow. Path-handling security testing is pending.

### Threat: Unauthorized document upload
**Risk:** A Viewer may attempt to upload documents without the required role.

**Mitigation:** The upload route checks the authenticated user's role and permits only Document Owner and Administrator roles.

**Status:** Implemented. Negative authorization tests are pending.

### Threat: Missing document audit trail
**Risk:** Document upload activity may not be traceable during a security review.

**Mitigation:** The upload flow integrates audit-event logging for document uploads.

**Status:** Integrated. Audit-record persistence and completeness must still be verified.

### Day 4 Security Validation
- Extension and MIME-type checks added to the upload route.
- UUID-based server-side filenames implemented.
- Upload role restrictions added.
- Upload audit-event integration added.
- Browser upload, document-list visibility, download authorization, and audit persistence verification remain pending.

