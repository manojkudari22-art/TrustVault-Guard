# TrustVault Guard

A secure document-sharing platform built for the Snovasys Fresher Hiring Challenge 2026.

## Problem Statement
Securely share confidential documents while maintaining a tamper-evident audit trail.

## Technology Stack
- Python
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-WTF
- Flask-Bcrypt
- SQLite
- Pytest

## Features
- User registration and authentication
- Role-based access control: Administrator, Document Owner, Viewer
- Secure document upload and private storage
- Permission-based document viewing and downloading
- Document sharing, permission updates, and access revocation
- Document editing and replacement
- Audit logging with hash-chain integrity verification
- CSRF protection and secure session configuration
- File validation and security testing

## Installation
1. Create a virtual environment: `python -m venv venv`
2. Activate it: `.\venv\Scripts\Activate.ps1`
3. Install dependencies: `pip install -r requirements.txt`

## Run Locally
`python run.py`

Database tables are created automatically during application initialization.

## Run Tests
`pytest -q`

Latest verified result: **77 tests passed on 2026-11-09 (27.63 seconds).**

## Production Configuration
Set `FLASK_ENV=production` and configure a strong `SECRET_KEY`.

Use HTTPS, a production WSGI server, and persistent storage for the database and uploaded documents.

## Documentation
- Problem statement: `docs/PROBLEM_STATEMENT.md`
- Requirements: `docs/REQUIREMENTS.md`
- Architecture: `docs/ARCHITECTURE.md`
- Threat model: `docs/THREATS.md`
- AI prompt history: `docs/PROMPTS.md`

## Project Status
Core authentication, document management, role-based authorization, audit logging, and automated tests are implemented.

Live deployment verification and AI-assisted permission suggestions with mandatory Document Owner approval remain pending.
