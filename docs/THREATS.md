# TrustVault Threat Model

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
