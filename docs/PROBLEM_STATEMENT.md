# TrustVault Guard - Secure Document Sharing

## Problem Statement

Organizations and individuals frequently share confidential documents with multiple users. Without proper access control, private documents may be accessed, downloaded, modified, or deleted by unauthorized users. The absence of reliable audit records also makes it difficult to identify who accessed a document and what actions were performed.

TrustVault Guard addresses this problem through role-based access control, document-level permissions, private file storage, and a tamper-evident audit trail.

## Main Goals

- Provide secure user registration and authentication.
- Enforce role-based access control.
- Store uploaded documents in private storage.
- Allow document owners to manage document permissions.
- Support permission granting and revocation.
- Restrict unauthorized document access and operations.
- Record important document and permission-related activities.
- Verify audit log integrity using a SHA-256 hash chain.
- Provide AI-assisted permission recommendations with owner approval.
- Validate security controls through automated testing.

## User Roles

- **Admin:** Monitors platform activity, users, security events, and audit integrity.
- **Document Owner:** Uploads and manages documents, controls permissions, and reviews AI permission recommendations.
- **Viewer:** Accesses documents only when explicitly authorized by the document owner.

## Core Features

- User registration, login, and logout.
- Password hashing and authenticated sessions.
- Role-based dashboards and access restrictions.
- Secure document upload and private file storage.
- Document categorization and search.
- Document-level view, download, and edit permissions.
- Permission granting and revocation.
- Document metadata and content management.
- AI-assisted permission suggestions.
- Audit event recording and hash-chain verification.
- Security-focused automated tests.

## Security Principles

- **Default Deny:** Access is denied unless explicitly authorized.
- **Least Privilege:** Users receive only the permissions required for their tasks.
- **Owner-Controlled Permissions:** AI recommendations never grant access automatically.
- **Immediate Revocation:** Revoked permissions must no longer authorize subsequent access requests.
- **Private File Storage:** Documents are not exposed through unrestricted public file paths.
- **Server-Side Authorization:** Sensitive operations are validated by the application server.
- **Auditability:** Important actions and denied access attempts are recorded.
- **Tamper Evidence:** Audit records are linked using cryptographic hashes to detect unauthorized changes.

## Expected Outcome

A working secure document-sharing application that enables authorized collaboration while restricting unauthorized access and maintaining traceable records of important activities.

The platform demonstrates secure authentication, controlled document sharing, permission management, AI-assisted recommendations, and audit trail integrity.

## Technology Stack

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-WTF
- Flask-Bcrypt
- SQLite
- HTML, CSS, and JavaScript
- Ollama with Llama 3.2
- Pytest

## Development and Verification Timeline

- **November 1–7, 2026:** Project planning, architecture, core feature implementation, security controls, AI-assisted permission recommendations, testing, and initial deployment.
- **November 8, 2026:** Debugging, integration corrections, security fixes, and deployment-related troubleshooting.
- **November 9, 2026:** Final regression testing, documentation review, and deployment verification.

## Project Validation

- Automated test suite: **81 tests passed** on November 9, 2026.
- Live application deployment: Render.
- AI-assisted permission recommendations require document-owner review and approval.

## Scope and Limitations

- AI recommendations are advisory and do not automatically grant permissions.
- The AI service depends on an available Ollama model endpoint.
- Local Ollama configuration is not automatically accessible from the hosted Render environment.
- SQLite deployment requires persistent storage configuration to preserve data across service restarts and redeployments.
- The audit hash chain provides tamper evidence but does not guarantee protection against an attacker capable of rewriting the entire database and recalculating the chain.

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
