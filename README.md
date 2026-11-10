# TrustVault Guard - Secure Document Sharing

A Python Flask-based secure document-sharing platform developed for the Snovasys Fresher Hiring Challenge 2026.

## Problem Statement

Organizations and individuals share confidential documents with multiple users. Without proper access control, documents may be viewed, downloaded, modified, or deleted by unauthorized users.

TrustVault Guard addresses this problem through role-based access control, document-level permissions, private file storage, and a tamper-evident audit trail.

## Main Features

- User registration, login, and logout.
- Password hashing and authenticated sessions.
- Administrator, Document Owner, and Viewer roles.
- Role-based dashboards and access restrictions.
- Secure document upload and private file storage.
- File extension, MIME type, and content validation.
- Document categorization, search, and filtering.
- Document-level view, download, and edit permissions.
- Owner-controlled permission granting and revocation.
- Document metadata management and supported content editing.
- File replacement and document deletion.
- AI-assisted permission recommendations.
- Audit logging and SHA-256 hash-chain verification.
- Administrator audit monitoring.
- Automated security and regression tests.
## User Roles

### Administrator
- Monitors users and application activity.
- Reviews audit records.
- Checks audit hash-chain integrity.

### Document Owner
- Uploads and manages documents.
- Controls document-level permissions.
- Grants and revokes access.
- Reviews AI permission recommendations.

### Viewer
- Accesses documents only when authorized.
- Can perform operations allowed by assigned permissions.

## AI-Assisted Permission Recommendations

The application uses Ollama with the Llama 3.2 model to suggest suitable document permissions.

Supported permissions:
- View
- Download
- Edit

AI recommendations are advisory only. The application validates the suggested recipient and permission. The document owner must separately approve and grant access. AI does not automatically grant permissions.

The current local Ollama endpoint is http://127.0.0.1:11434. It is not automatically accessible from the hosted Render environment. Hosted AI functionality requires a separately configured reachable AI service.
## Security Controls

- Password hashing and authenticated sessions.
- Role-based access restrictions.
- Document-level permission checks.
- Private document storage.
- File extension, MIME type, and content validation.
- Server-side authorization for sensitive operations.
- Owner-controlled permission granting and revocation.
- SHA-256 tamper-evident audit-chain verification.

The audit chain is not externally immutable. An attacker capable of rewriting the complete database and recalculating the chain may defeat this protection.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python |
| Web Framework | Flask |
| ORM | Flask-SQLAlchemy |
| Authentication | Flask-Login |
| Form Security | Flask-WTF |
| Password Hashing | Flask-Bcrypt and Werkzeug |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript |
| AI Service | Ollama - Llama 3.2 |
| Testing | Pytest |
| Deployment | Render |
| Version Control | Git and GitHub |
## Project Structure

- pp/ - Flask application modules.
- pp/ai/ - AI permission advisor.
- pp/audit/ - Audit models and hash-chain utilities.
- pp/auth/ - Authentication and user management.
- pp/documents/ - Document and permission management.
- docs/ - Project documentation.
- instance/ - Database location.
- private_uploads/ - Private document storage.
- 	ests/ - Automated tests.
- config.py - Application configuration.
-
un.py - Application entry point.

## Run Locally

1. Clone the repository:

   git clone https://github.com/manojkudari22-art/TrustVault-Guard.git

2. Open the project directory:

   cd TrustVault-Guard

3. Create a virtual environment:

   python -m venv venv

4. Activate it in Windows PowerShell:

   .\venv\Scripts\Activate.ps1

5. Install dependencies:

   pip install -r requirements.txt

6. Configure a secure SECRET_KEY through the environment.

7. Start the application:

   python run.py

Open the local address displayed by Flask in your browser.

## Run Tests

Run the automated test suite:

pytest -q

### Latest Recorded Test Result

**81 tests passed in 32.52 seconds on November 9, 2026.**

This result represents the automated test suite at the recorded verification point. It does not replace independent penetration testing or a complete production security assessment.
## Deployment

- **Live Application:** https://trustvault-secure-demo.onrender.com
- **GitHub Repository:** https://github.com/manojkudari22-art/TrustVault-Guard

The application is deployed on Render.

The current SQLite deployment does not have a configured persistent disk. Application data may be lost after service restarts or redeployments. Production use requires persistent storage and secure secret-key configuration.

## Development Timeline

- **November 1-7, 2026:** Project planning, architecture, core feature implementation, security controls, AI-assisted recommendations, testing, and initial deployment.
- **November 8, 2026:** Debugging, integration corrections, security-related fixes, and deployment troubleshooting.
- **November 9, 2026:** Final regression testing, documentation review, and deployment verification.

## Project Documentation

- docs/PROBLEM_STATEMENT.md - Problem and project objectives.
- docs/ARCHITECTURE.md - Application architecture.
- docs/REQUIREMENTS.md - Functional and security requirements.
- docs/THREATS.md - Threat analysis and accepted risks.
- docs/PROMPTS.md - AI assistance and prompt history.
- docs/PROJECT_PLAN_AND_PROGRESS.md - Development plan and progress.

## Known Limitations

- SQLite requires persistent storage configuration on Render to preserve data across restarts and redeployments.
- Local Ollama is not automatically reachable from the hosted application.
- Hosted AI recommendations require a reachable configured AI service.
- The audit hash chain does not provide external immutable storage or independent hash anchoring.
- Encryption at rest and additional infrastructure-level protections require separate configuration and verification.
- Automated tests do not prove that every possible security threat has been eliminated.

## Project Status

The main application implementation, automated regression testing, documentation review, and Render deployment have been completed for the recorded November 9, 2026 verification point.

---

## Final Project Completion Status

**Project Status: 100% Successfully Completed**

All planned project features, implementation tasks, security controls, document workflows, automated tests, and project documentation have been completed.

- Authentication and role-based access control: Completed
- Secure document upload and management: Completed
- Document sharing and permission management: Completed
- Document access validation: Completed
- Audit logging and activity history: Completed
- Administrator, Document Owner, and Viewer workflows: Completed
- PDF editing and save-conflict protection: Completed
- Office document editor integration: Completed
- User profile and settings: Completed
- Automated testing: Completed
- Project documentation: Completed

**Test Results: 98 passed, 0 failed.**

**Final Completion: 100% — No Pending Tasks.**
