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


## 2026-11-05 — Day 5: Document Listing and Search Security

### Threat: Unauthorized document metadata disclosure
**Risk:** A user may attempt to discover another user's document names, categories, or upload information through the listing and search interface.

**Mitigation:** The document listing query is scoped to the authenticated user's owner ID. The route is restricted to Document Owner and Administrator roles. Category options and document counts are also scoped to the current owner.

**Status:** Owner-scoped listing and filtering implemented. Dedicated cross-user access tests are pending.

### Threat: Invalid search and filter input
**Risk:** Unexpected date or page values may cause application errors or unintended query behavior.

**Mitigation:** Search input length is limited. Date values are parsed using the expected date format, and page values are converted and validated before pagination. Invalid date and page values are rejected.

**Status:** Input validation implemented. Dedicated invalid-input tests are pending.

### Threat: Document metadata exposure through pagination
**Risk:** Pagination counts or result pages may reveal records belonging to other users if ownership restrictions are applied incorrectly.

**Mitigation:** The owner restriction is applied to the document query before calculating counts, categories, and paginated results.

**Status:** Owner-scoped pagination implemented. Automated isolation tests are pending.

### Threat: Incorrect owner dashboard document count
**Risk:** A dashboard may display document totals belonging to other users.

**Mitigation:** The owner dashboard count query filters documents using the authenticated user's ID.

**Status:** Owner-specific document count implemented. Multi-user verification is pending.

### Day 5 Security Validation
- Owner-scoped document listing and search implemented.
- Category and date filtering implemented.
- Pagination and query-parameter validation implemented.
- Owner-specific document count implemented.
- Dedicated document authorization and filter tests remain to be performed.

## 2026-11-06 — Day 6: Dashboard and Role-Based Access Security

### Threat: Unauthorized access to the Upload page
**Risk:** A Viewer may attempt to open the document upload page directly instead of using dashboard navigation.

**Mitigation:** The GET upload route requires authentication and permits only Document Owner and Administrator roles. The existing POST upload route retains its role check.

**Validation:** Administrator access returned HTTP 200. Viewer direct access returned HTTP 302 and redirected to `/dashboard`.

**Status:** Role restriction verified.

### Threat: Unauthorized access to My Documents
**Risk:** A Viewer may attempt to access the owner-specific document listing by entering its URL directly.

**Mitigation:** The My Documents route checks the authenticated user's role and permits only Document Owner and Administrator roles. The document query is scoped to the current user's owner ID.

**Validation:** Viewer direct access returned HTTP 302 and redirected to `/dashboard`.

**Status:** Role restriction verified. Dashboard response also contained the My Documents URL despite the visible link text being absent; this requires further investigation.

### Threat: Unauthenticated access to document-management pages
**Risk:** An unauthenticated visitor may attempt to access protected document-management routes.

**Mitigation:** Flask-Login authentication protection is applied to the Upload and My Documents routes.

**Validation:** An unauthenticated Upload page request redirected to the Login page.

**Status:** Basic authentication protection verified.

### Day 6 Security Validation and Remaining Gaps
- Administrator dashboard and Upload page access verified.
- Viewer Upload and My Documents route access blocked.
- Unauthenticated Upload access redirected to the Login page.
- Full automated test suite completed successfully: 77 tests passed.
- Existing user and database records preserved during test-client checks.
- Dashboard response contained the My Documents URL despite the visible link text being absent; further investigation is required.
- Live production deployment and deployed-environment verification remain pending.
- AI-assisted permission suggestions with mandatory Document Owner approval remain to be implemented.
