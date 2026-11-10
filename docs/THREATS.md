# TrustVault Guard - Security Threat Analysis

## 1. Project Information

- **Project:** TrustVault Guard - Secure Document Sharing
- **Challenge:** Snovasys Fresher Hiring Challenge 2026
- **Application:** Python Flask-based document-sharing platform
- **Database:** SQLite
- **AI Service:** Ollama - Llama 3.2
- **Security Review Date:** November 9, 2026

## 2. Security Objective

TrustVault Guard is designed to prevent unauthorized users from accessing confidential documents and to maintain traceable records of important application activities.

This threat analysis identifies security risks affecting authentication, authorization, document storage, permission management, AI-assisted recommendations, and audit integrity.

The objective is to document the implemented security controls, their verification approach, and the remaining limitations.

## 3. Protected Assets

The following assets require protection:

- User accounts and authentication credentials.
- Confidential documents and uploaded files.
- Document ownership and permission records.
- User roles and account information.
- Audit records and hash-chain integrity.
- AI permission recommendation inputs and outputs.
- Application configuration and database contents.

## 4. Threat Actors

Potential threat actors include:

- Unauthenticated visitors attempting to access protected resources.
- Authenticated users attempting to access documents without permission.
- Viewers attempting unauthorized document modifications.
- Malicious users uploading unsafe or unsupported files.
- Users attempting to manipulate document permissions.
- Attackers attempting to modify or delete audit records.
- Users attempting to influence AI recommendations through manipulated input.

## 5. Main Security Threats and Mitigations

### Threat 1: Unauthorized Account Access

**Risk:** An attacker may attempt to access another user's account using stolen or guessed credentials.

**Potential Impact:**
- Unauthorized access to confidential documents.
- Misuse of document permissions.
- Exposure of account information.

**Implemented Mitigations:**
- Passwords are stored using Werkzeug password hashing.
- Password verification uses the stored password hash.
- Registration requires username, email, and password.
- Passwords must contain at least eight characters.
- Login checks whether the account is active.
- Invalid login attempts receive a generic authentication error.
- Password changes require the current password.

**Verification:**
- Authentication tests validate login and password handling.
- Account access is protected through Flask-Login.

### Threat 2: Unauthorized Role Assignment

**Risk:** A user may attempt to register with administrator privileges or access administrator-only functionality.

**Potential Impact:**
- Unauthorized administrative access.
- Exposure of platform activity and user information.
- Abuse of privileged operations.

**Implemented Mitigations:**
- Public registration accepts only Viewer and Document Owner roles.
- Administrator is excluded from the public registration role allowlist.
- Role-based route protection checks the authenticated user's role.
- Administrator-only functionality is protected by server-side authorization.

**Verification:**
- Registration and role authorization tests.
- Role-based route access checks.

### Threat 3: Unauthorized Document Access

**Risk:** A user may attempt to view or download a document without ownership or an active permission.

**Potential Impact:**
- Confidential information disclosure.
- Unauthorized document distribution.
- Loss of document confidentiality.

**Implemented Mitigations:**
- Protected document routes require authentication.
- Document ownership is checked on sensitive operations.
- Document-level permissions are checked before viewing or downloading.
- Download access requires download or edit permission.
- View access accepts the permitted view, download, or edit levels.
- Unauthorized attempts are recorded as access-denied audit events.
- Deleted documents are excluded from normal access.

**Verification:**
- Document authorization tests.
- Unauthorized access and download test cases.

### Threat 4: Unauthorized Document Modification or Deletion

**Risk:** A user may attempt to modify, replace, or delete documents owned by another user.

**Potential Impact:**
- Loss of document integrity.
- Unauthorized changes to confidential information.
- Accidental or malicious document removal.

**Implemented Mitigations:**
- Document ownership is checked before metadata editing and deletion.
- Content editing requires ownership or an active edit permission.
- Direct content editing is restricted to supported TXT and CSV files.
- File replacement requires appropriate authorization.
- Deleted documents are soft-deleted in the database.
- Active document permissions are deactivated when a document is deleted.
- Important modification and deletion events are recorded.

**Verification:**
- Document ownership and edit authorization tests.
- Document lifecycle and permission tests.

### Threat 5: Unsafe File Uploads and Path Manipulation

**Risk:** An attacker may upload unsupported files or attempt to manipulate file paths and filenames.

**Potential Impact:**
- Storage of unexpected file types.
- Unauthorized file access.
- File path manipulation.
- Exposure or corruption of stored files.

**Implemented Mitigations:**
- Uploads are restricted to an application-defined extension and MIME-type allowlist.
- File validation also examines uploaded file content.
- Werkzeug secure_filename is used to sanitize original filenames.
- Stored filenames are generated separately from original filenames.
- Uploaded files are stored in a private application upload directory.
- File access resolves and validates storage paths before serving files.
- Upload size is limited by application configuration.

**Verification:**
- File validation tests.
- Upload and download authorization tests.
- Invalid file and path-handling test cases.

### Threat 6: Unauthorized Permission Changes

**Risk:** A user may attempt to grant, modify, or revoke document permissions without being the document owner.

**Potential Impact:**
- Unauthorized document sharing.
- Privilege escalation.
- Continued access after permission revocation.

**Implemented Mitigations:**
- Permission management is controlled by document ownership.
- Only supported permission levels are accepted: view, download, and edit.
- Recipient validation prevents invalid recipients and self-sharing.
- Permission records maintain an active or revoked state.
- Revocation deactivates the permission and records its revocation time.
- Access checks consider the current active permission.
- Permission grant and revocation activities are recorded in the audit trail.

**Verification:**
- Permission grant and revocation tests.
- Unauthorized permission-management tests.
- Access checks after permission revocation.

### Threat 7: Audit Log Manipulation

**Risk:** An attacker with database access may attempt to modify audit records or remove evidence of important activities.

**Potential Impact:**
- Loss of accountability.
- Manipulated activity history.
- Reduced reliability of security investigations.

**Implemented Mitigations:**
- Important application activities are recorded as audit events.
- Each audit event contains a SHA-256 hash.
- Each event references the previous event hash.
- Hash calculation includes relevant event fields and timestamps.
- Audit-chain verification checks previous-hash continuity.
- Event hashes are recalculated and compared during verification.
- New audit events are not appended when existing chain verification fails.
- Audit integrity status is exposed through administrator monitoring.

**Verification:**
- Audit event creation tests.
- Hash-chain verification tests.
- Modified event and broken-chain detection tests.

**Security Limitation:**
The SHA-256 hash chain provides tamper evidence. It does not provide independent immutability against an attacker who can rewrite the complete database and recalculate the entire chain. External anchoring or write-once audit storage is not currently implemented.

### Threat 8: Unsafe AI Permission Recommendations

**Risk:** AI may recommend an unsuitable recipient or excessive permission, or return malformed output.

**Potential Impact:**
- Over-privileged sharing recommendations.
- Incorrect recipient selection.
- Misleading permission suggestions.

**Implemented Mitigations:**
- AI recommendations are generated only for eligible recipients.
- The prompt instructs the model to prefer least-privilege access.
- Document metadata and sharing reasons are supplied as data rather than instructions.
- The application validates the recommended username against the eligible recipient list.
- Only view, download, and edit permissions are accepted.
- Invalid or malformed AI responses are rejected.
- The AI advisor returns a recommendation only.
- Actual permission granting is handled by a separate owner-controlled operation.
- Document owners must review and approve sharing decisions.

**Verification:**
- AI recommendation validation tests.
- Invalid recipient and permission rejection tests.
- Owner-controlled permission granting tests.

**Security Limitation:**
AI output is not treated as an authorization decision. Prompt instructions alone cannot guarantee that a model will always behave correctly; application-side validation and owner approval remain essential.

### Threat 9: Unauthorized Access After Revocation

**Risk:** A previously authorized user may attempt to access a document after their permission has been revoked.

**Potential Impact:**
- Continued unauthorized access.
- Exposure of confidential documents.

**Implemented Mitigations:**
- Permission revocation updates the permission's active state.
- Document access routes check the current permission record.
- Revoked permissions are excluded from active access queries.
- Document deletion also deactivates associated active permissions.

**Verification:**
- Permission revocation tests.
- Post-revocation access-denial tests.

## 6. Security Controls Summary

| Security Area | Implemented Control |
|---|---|
| Authentication | Password hashing and Flask-Login |
| Registration | Restricted public role selection |
| Authorization | Server-side role and ownership checks |
| File Upload | Extension, MIME-type, and content validation |
| File Storage | Private directory and generated filenames |
| Document Access | Document-level permission checks |
| Permission Management | Owner-controlled grant and revocation |
| Audit Logging | SHA-256 linked audit events |
| Audit Verification | Hash and previous-hash validation |
| AI Recommendations | Output validation and owner approval |

## 7. Security Verification Approach

Security validation focuses on the following areas:

- Authentication and account handling.
- Role-based access restrictions.
- Document ownership enforcement.
- Unauthorized document access prevention.
- File upload validation.
- Document permission granting and revocation.
- Access denial after revocation.
- Audit event creation and hash-chain verification.
- AI recommendation output validation.
- Regression testing after debugging and integration changes.

**Latest Automated Test Result:** 81 tests passed on November 9, 2026.

This result represents the automated test suite at the recorded verification point. It should not be interpreted as proof that every possible attack or production environment scenario has been tested.

## 8. Accepted Risks and Remaining Limitations

The following limitations are acknowledged:

- SQLite without a configured persistent disk on Render may lose application data after restarts or redeployments.
- Production deployment requires appropriate secret-key and persistent-storage configuration.
- The local Ollama endpoint at 127.0.0.1:11434 is not automatically accessible from the hosted Render service.
- Hosted AI recommendations require an appropriately configured reachable AI service.
- The audit hash chain does not protect against complete database and chain reconstruction by a sufficiently privileged attacker.
- No external immutable audit storage or independent hash anchoring is currently implemented.
- Automated tests do not replace an independent penetration test or production security assessment.
- Encryption at rest and additional infrastructure-level protections require separate production configuration and verification.

## 9. Development and Security Review Timeline

- **November 1–7, 2026:** Threat identification, architecture planning, authentication, authorization, private document storage, permission management, audit logging, AI recommendation controls, and initial testing.
- **November 8, 2026:** Debugging, integration corrections, security-related fixes, and deployment troubleshooting.
- **November 9, 2026:** Final regression testing, audit and permission verification, documentation review, and deployment validation.

## 10. Conclusion

TrustVault Guard applies layered security controls to protect confidential documents and maintain accountability for important application activities.

The application combines authentication, role-based authorization, document-level permissions, private file storage, validated AI recommendations, and a SHA-256 tamper-evident audit chain.

The documented limitations identify areas requiring additional infrastructure hardening and independent security assessment before use with highly sensitive production documents.

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
