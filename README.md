# Alive App Backend

Backend service for **Alive App**, a safety-focused check-in system that allows users to periodically confirm they are active. If a user misses their configured check-in window, the backend can trigger follow-up workflows for their registered emergency contacts.

## Overview

Alive App Backend is built with **FastAPI** and exposes a versioned REST API under `/api/v1`.

The service is responsible for:

- user authentication
- user check-ins and status tracking
- emergency contact management
- account and settings management
- background trigger processing for missed deadlines
- email notification workflows

This project is designed to run on a Linux VM with **MySQL**, **systemd**, and **Nginx** in front of the API.

---

## Tech Stack

- **Python 3.12+**
- **FastAPI**
- **Uvicorn**
- **SQLAlchemy (async)**
- **MySQL**
- **systemd**
- **Nginx**
- **SMTP**
- **Google Sign-In**
- **Sign in with Apple**

---

## Features

### Authentication
- Email/password authentication
- Google OAuth support
- Apple Sign-In support
- JWT-based session handling
- Development auth endpoint for local testing

### Check-In Flow
- Users can submit a check-in to confirm activity
- Backend updates the user’s latest active timestamp
- User status is derived from their configured check-in interval
- Missed check-ins can escalate into trigger events

### Trigger Worker
- Background worker checks for users who miss their deadlines
- Trigger events are processed outside the request/response cycle
- Worker can be run manually or on a schedule via `systemd` timer

### Emergency Contact Management
- Create and manage emergency contacts
- Store user safety configuration and escalation settings

### Operational Support
- Health check endpoint
- Structured deployment for Linux VM environments
- Service-based startup and background job scheduling

---

## API Structure

Base path:

```bash
/api/v1
```

Main route groups:

```bash
/api/v1/auth
/api/v1/check-in
/api/v1/contacts
/api/v1/settings
/api/v1/logs
/api/v1/account
```

Health check:

```bash
GET /health
```

Example response:

```JSON
{ "ok": true }
```

## Project Structure:

```bash
alive-api/
├── app/
│   ├── api/
│   │   ├── routes_auth.py
│   │   ├── routes_checkin.py
│   │   ├── routes_contacts.py
│   │   ├── routes_settings.py
│   │   ├── routes_logs.py
│   │   └── routes_account.py
│   ├── core/
│   ├── db/
│   │   └── migrations/
│   ├── worker/
│   └── main.py
├── deploy/
│   ├── systemd/
│   └── DEPLOY.md
├── requirements.txt
└── .env.example
```
## Local Development
1. Clone the repository

```bash
git clone https://github.com/Tung-Phan-Dinh/alive-app.git
cd alive-app/alive-api
```

2. Create and activate a virtual environment

```bash
python3 -m venv alive_venv
source alive_venv/bin/activate
```

3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. Configure environment variables

```bash
cp .env.example .env
nano .env
```

5. Set up the database

```bash
mysql -u root -p < app/db/database.sql
mysql -u root -p alive_app < app/db/migrations/001_trigger_notifications.sql
mysql -u root -p alive_app < app/db/migrations/002_email_provider_unique.sql
mysql -u root -p alive_app < app/db/migrations/005_add_apple_refresh_token.sql
```

7. Run the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

8. Verify the service

```bash
curl http://localhost:8000/health
```

## Production Deployment
This backend is intended to run on an Ubuntu Linux VM.

Typical production architecture:

```bash
Internet
   ↓
Nginx :80 / :443
   ↓
FastAPI (Uvicorn)
   ↓
MySQL
```
# Author
Dinh Tung Phan

Backend for the Alive App project, focused on authentication, user safety check-ins, emergency contact flows, and automated trigger handling for missed activity windows.






