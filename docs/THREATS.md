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

