# AI Prompts Log

## Project
TrustVault — Secure Document Sharing with a Real Audit Trail

## Day 1 — 2026-11-01

### Prompt 1 — Problem Analysis

**Tool:** ChatGPT

**Prompt / Summary:**
Analyze the Snovasys TrustVault challenge problem statement. Identify the core problem, functional requirements, security requirements, user roles, and expected deliverables.

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
Suggest a beginner-friendly Flask architecture for TrustVault using SQLite, authentication, role-based access control, private document storage, document permissions, and audit logging.

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
Provide a step-by-step Flask project setup for TrustVault, including a virtual environment, dependencies, application factory, configuration, and a basic route.

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
