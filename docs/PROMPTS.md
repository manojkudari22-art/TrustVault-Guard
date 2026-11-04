# AI Prompts Log

## Project
TrustVault Guard — Secure Document Sharing with a Real Audit Trail

## Day 1 — 2026-11-01

### Prompt 1 — Problem Analysis

**Tool:** ChatGPT

**Prompt / Summary:**
Analyze the Snovasys TrustVault Guard challenge problem statement. Identify the core problem, functional requirements, security requirements, user roles, and expected deliverables.

**What it produced:**
- Initial problem statement
- Functional and security requirements
- User roles: Admin, Document Owner, Viewer
- Initial project scope

**What was wrong:**
The initial analysis was high-level. It did not fully map realistic attacks to security controls and automated tests. The first threat list was also too generic for the challenge's security expectations.

**What I did instead:**
Created initial documentation in docs/PROBLEM_STATEMENT.md and docs/REQUIREMENTS.md. I will expand the threat analysis alongside implementation and map each threat to security tests.

**Fix / Follow-up commit:**
Pending — will link the commit after updating the threat model and tests.

---

### Prompt 2 — Architecture Planning

**Tool:** ChatGPT

**Prompt / Summary:**
Suggest a beginner-friendly Flask architecture for TrustVault Guard using SQLite, authentication, role-based access control, private document storage, document permissions, and audit logging.

**What it produced:**
- Suggested technology stack
- Initial application modules
- Request flow
- Initial security design principles

**What was wrong:**
The architecture was a starting point, not a verified secure implementation. It did not yet demonstrate that authorization would be enforced on every document operation or that audit records would be tamper-evident.

**What I did instead:**
Created docs/ARCHITECTURE.md as an initial design. I will verify the security design during implementation and automated testing.

**Fix / Follow-up commit:**
Pending — will link the commit after implementing and testing the security controls.

---

### Prompt 3 — Initial Threat Modeling

**Tool:** ChatGPT

**Prompt / Summary:**
Identify possible threats to a secure document-sharing platform, including unauthorized document access, permission misuse, malicious uploads, and audit log tampering. Suggest practical mitigations.

**What it produced:**
- Initial asset list
- Basic threat scenarios
- Initial mitigation suggestions
- Default-deny principle

**What was wrong:**
The first threat model did not cover enough realistic attack scenarios, such as IDOR, privilege escalation, permission revocation bypass, unauthorized metadata search, and session abuse. It also did not map each threat to a specific automated test.

**What I did instead:**
Created an initial docs/THREATS.md. I will expand it as development progresses and link each threat to its implemented protection and test.

**Fix / Follow-up commit:**
Pending — will link the commit after the threat model and corresponding tests are updated.

---

### Prompt 4 — Initial Project Setup

**Tool:** ChatGPT

**Prompt / Summary:**
Provide a step-by-step Flask project setup for TrustVault Guard, including a virtual environment, dependencies, application factory, configuration, and a basic route.

**What it produced:**
- Initial project folder structure
- Flask application setup
- Dependency list
- Basic application startup instructions

**What was wrong:**
The initial setup only verified that Flask could run. It did not implement authentication, authorization, secure document handling, or audit logging.

**What I did instead:**
Created the initial project files, installed dependencies, ran the Flask application locally, and verified the startup page. I will implement the actual challenge features in subsequent development days.

**Fix / Follow-up commit:**
Initial setup commit: 717c82b

---

## AI Usage Review

AI was used for initial analysis, architecture suggestions, threat modeling, and setup guidance. AI-generated suggestions were treated as a starting point, not proof of security.

The initial Day 1 implementation is only project setup and documentation. Security protections and automated tests are not yet implemented.

This log will be updated daily with dated entries, specific shortcomings, and links to commits containing corrections or improvements.

## Day 2 — 2026-11-02

### Prompt 5 — Authentication and Roles
**Tool:** ChatGPT

**Prompt / Summary:**
I am building TrustVault Guard for the Snovasys Fresher Hiring Challenge. For Day 2, help me implement authentication and role-based access control from scratch. I need user registration, login, logout, password hashing, and three roles: Administrator, Document Owner, and Viewer. New users should get the Viewer role by default. Protect the dashboards based on user roles and create tests to verify that users cannot access dashboards they are not authorized to use. I also want the login and registration pages to have a modern, attractive interface with a logo instead of a plain design.

**What it produced:**
- User model and password hashing
- Registration, login, and logout routes
- Role-protected dashboards
- Login and registration interface
- Automated authentication tests

**What was wrong:**
The initial test run failed because of the Python import path and template location. Two role access tests also failed because the role was updated after login.

**What I did instead:**
Fixed the Python import path, moved templates to the Flask app's template directory, and updated the tests to assign roles before login.

**Validation:**
8 authentication tests passed.

**Security note:**
New registrations receive the Viewer role. Secure administrator-managed role assignment and additional authentication hardening are still pending.

**Commit:**
Pending.


## Day 4 — 2026-11-04

### Prompt 6 — Secure Document Management

**Tool:** ChatGPT

**Prompt / Summary:**
Help implement secure document management in the existing Flask TrustVault Guard project. Add document upload handling, file extension and MIME-type validation, UUID-based server-side filenames, role restrictions for uploads, document database records, and audit logging. Improve the dashboard upload interface with file selection, drag-and-drop interaction, and selected-file feedback. Preserve the existing authentication and role structure.

**What it produced:**
- Document model and document module structure
- Document upload route
- Extension and MIME-type validation
- UUID-based stored filenames
- Upload restrictions for Document Owner and Administrator
- Upload audit-event integration
- Dashboard upload interface improvements

**What was wrong / limitations:**
The initial upload implementation did not yet demonstrate complete document lifecycle security. The dashboard did not initially display Flask flash notifications. Browser-based drag-and-drop, document-list visibility, download behavior, and audit-event persistence still require verification.

**What I did instead:**
Integrated document management into the existing Flask application, improved the upload interface, and recorded the remaining validation tasks instead of treating untested behavior as complete.

**Validation:**
Implementation committed and pushed. Browser-based upload, document listing, download, and audit verification remain pending.

**Security note:**
Server-side validation and role checks are implemented in the upload flow. File-size limits, comprehensive document authorization tests, and further security hardening still need verification.

**Commit:** c23490c

