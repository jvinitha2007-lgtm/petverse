# PetVerse

PetVerse is a full-stack pet-care management application. Its current milestones include verified account authentication and password recovery, owner-scoped pet profiles, health records, care tasks, professional verification, provider availability and booking, emergency volunteer dispatch, administrator review, account suspension, private messaging, and role-aware dashboards backed by a relational database.

## What works today

- Registration, login, and authenticated API requests using signed bearer tokens.
- Email verification before sign-in, verification-link resend, and single-use password-reset links delivered through configurable SMTP.
- Role-aware overview metrics for pet owners, providers, volunteers, and administrators.
- Passwords hashed with PBKDF2-HMAC-SHA256; public registration always creates an owner account.
- Pet create, list, edit, and archive operations with ownership enforced by the API.
- Medical/owner-observation records attached to an individual pet.
- Care tasks with due dates, completion state, and pet association.
- Vaccination and medication schedules with optional notes, repeat intervals (including 12-hour/daily cadence), and configurable email reminders. Completing a repeating task advances it to its next scheduled occurrence.
- Operator-run `send-care-reminders` command sends each due reminder once to the verified account email. Run it periodically with your operating system scheduler; SMTP must be configured. Reminder emails repeat the owner-entered schedule and are not veterinary instructions.
- Personalized dashboard totals and upcoming care tasks derived from saved data.
- Professional access requests for veterinarian, groomer, shelter, and volunteer roles. New registrations always remain owners; only an administrator can approve and assign a professional role.
- Administrator review queue, paginated account listing, account suspension/reinstatement, and audit records.
- Operator-only `promote-admin` command for bootstrapping the first administrator without a public privilege-escalation route.
- Approved veterinarians and groomers can publish service profiles and future availability. Owners can discover those verified profiles, request appointments, view history, reschedule, or cancel.
- Provider slots are protected against overlapping availability and simultaneous active bookings. Providers can confirm, decline, and complete bookings; cancellations release the time slot.
- Owners can submit emergency assistance requests, and verified volunteers can set their availability/area, see eligible requests without precise location information, accept or decline requests, and update response status. Owners, assigned volunteers, and administrators have role-appropriate access. Emergency state changes are audited and create persistent in-app notifications.
- Verified shelter accounts can publish and update adoption listings. Signed-in users can report missing pets, share sightings using general areas, and report a pet found; only the report owner or an administrator can change its status. Public listings omit account emails and advise against posting exact home addresses.
- Owners and providers can privately message each other in appointment-linked conversations; owners and their assigned emergency volunteers can message within an assistance request. Conversations are visible only to the two related participants, incoming messages create in-app notifications, and opening a thread marks received messages read.
- An in-app notification center lists persistent emergency and message alerts and lets each account mark its own alerts read. Messaging is HTTP-based with manual refresh; attachments and real-time delivery are not implemented.
- Configurable AI care assistant provides general education through an OpenAI-compatible HTTPS endpoint. Only the submitted question and optional species are sent; stored pet profiles and health records are not included. Urgent symptom keywords trigger immediate veterinary escalation guidance without calling the AI provider.
- The emergency page displays immediate veterinary escalation guidance before any optional request form. Volunteer assistance is explicitly not presented as veterinary care; dispatch, response times, and professional medical services are not guaranteed.
- SQLite for zero-service local development; PostgreSQL and MySQL/MariaDB are supported through `DATABASE_URL`.
- Alembic migrations, API tests, frontend build, and Docker Compose configuration.

Credential document upload and external license checks are not implemented; administrators review applicant-entered summaries. Emergency dispatch is a local in-app volunteer coordination feature; it does not contact emergency veterinary services and does not provide encrypted location storage, emergency email/push delivery, or real-time messaging. Provider booking covers profiles, availability, appointment state, and appointment-linked messaging only—payment, automated reminders, and map-based clinic discovery are not included. RAG over a veterinary knowledge base, secure document storage, and external map/video integrations are not implemented yet. No external service is represented as connected. See [the roadmap](#roadmap).

## Requirements

- Python 3.11+
- Node.js 20+
- npm
- Docker Compose is optional; Docker is not needed for the SQLite development path.

## Run locally (SQLite)

In one terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL printed by npm (usually `http://localhost:5173`). The API runs at `http://localhost:8000`; interactive OpenAPI docs are at `/docs`. The frontend uses that API URL by default.

### Use XAMPP MariaDB locally

Start MySQL in the XAMPP Control Panel and create a `petverse` database using `utf8mb4`. In `backend/.env`, set `DATABASE_URL` to a MySQL/MariaDB SQLAlchemy URL, for example `mysql+pymysql://petverse_app:YOUR_LOCAL_PASSWORD@127.0.0.1:3306/petverse?charset=utf8mb4`, then apply migrations with `alembic upgrade head`. Run the API as usual and open `http://localhost/phpmyadmin/` to inspect the `petverse` database and its tables. Use a dedicated local database user with a password; do not expose XAMPP or use its default root account for production.

Set `JWT_SECRET` to a unique random value in `backend/.env` before using any non-disposable data. For example, generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never reuse the example development key in production.

Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, and `SMTP_STARTTLS` in `backend/.env` for verification and password-recovery email. `FRONTEND_URL` must point to the frontend origin so the one-time links return to the app. Account creation and email recovery return a service-unavailable error when SMTP delivery fails; configure a valid sender address for your mail service.

To enable the care assistant, set `AI_API_KEY`, `AI_API_BASE_URL` (HTTPS, OpenAI-compatible `/chat/completions` API), and `AI_MODEL` in `backend/.env`. Keep the key server-side and review your provider's data-retention policy before enabling this feature. Without a key, the assistant remains unavailable except for local emergency escalation guidance.

Care reminders use the same SMTP settings. Apply migrations, then schedule the following command to run periodically from the `backend` directory (for example, hourly with Task Scheduler or cron):

```powershell
python -m app.cli send-care-reminders
```

### Create the first administrator

Register an ordinary account, stop the API, then grant it administrator access from the backend directory:

```powershell
python -m app.cli promote-admin your-account@example.com
```

This command requires local access to the configured database. There is intentionally no public administrator-registration endpoint. The command is idempotent and writes an audit record.

## PostgreSQL / Docker Compose

The backend accepts a PostgreSQL SQLAlchemy URL, for example:

```env
DATABASE_URL=postgresql+psycopg://petverse:replace-me@localhost:5432/petverse
```

To start PostgreSQL with Compose, run `docker compose up -d db`, set the URL above in `backend/.env`, then run `alembic upgrade head`. This repository does not include seeded or default administrator credentials.

## Azure deployment configuration (manual)

Deployment files are prepared, but no Azure resources have been created and nothing has been deployed. The frontend can be published to an existing Azure Static Web Apps Free site by manually running the `Deploy frontend to Azure Static Web Apps` GitHub Actions workflow. Configure the repository secret `AZURE_STATIC_WEB_APPS_API_TOKEN` and repository variable `VITE_API_URL` (the HTTPS API origin, without `/api/v1`). The workflow is manual-only and does not provision resources.

The API has a root-level [Dockerfile](Dockerfile) for hosts that build from the repository root, plus [backend/Dockerfile](backend/Dockerfile) for hosts configured with `backend` as the build context. Both run Alembic migrations before starting FastAPI. Configure production `DATABASE_URL`, `JWT_SECRET`, `APP_ENV=production`, and `CORS_ORIGINS` (the deployed frontend origin); set SMTP and AI variables only if those features are used. Do not use container-local SQLite or the local XAMPP database for a public deployment; use a database reachable by the host. The frontend is a separate static site and needs its own build configuration.

Azure's free quotas and offers can change, and usage beyond a quota can be billed. A persistent production database and backend are not guaranteed to cost zero. Since this deployment was requested with a strict no-charges requirement, provision neither until the selected Azure services and their current pricing have been confirmed. These files alone do not mean PetVerse is live.

## Tests and production build

```powershell
cd backend
python -m pip install -r requirements.txt
pytest
```

```powershell
cd frontend
npm run build
```

## Configuration

Backend configuration is read from `backend/.env`; see [backend/.env.example](backend/.env.example). The frontend can use `VITE_API_URL` at build/dev time. Production deployment must configure HTTPS, a strong JWT secret, a production database, restricted CORS origins, backups, and operational monitoring. Private uploads and external integrations are not enabled in this milestone.

## Roadmap

1. Foundation and owner workflows (implemented).
2. Professional role applications, administrator verification review, suspension, and audit records (implemented; document/license verification remains).
3. Verified vet/groomer profiles, availability, booking, and appointment-linked messaging (implemented; payments, reminders, and real-time appointment availability remain).
4. Account recovery, email verification, and role-specific dashboards (implemented).
5. Vaccination/medication schedules and reminder delivery (implemented; external email service configuration and scheduler operation are deployment responsibilities).
6. Emergency request, verified volunteer assignment, status tracking, audit, in-app alerts, and assigned-participant messaging (implemented; external emergency integrations remain).
7. Shelter adoption listings, missing-pet reports, and sightings (implemented; identity verification and external shelter integrations remain).
8. Authorized messaging and in-app notification center (implemented; secure document storage remains).
9. Configurable AI assistant (implemented; RAG remains), maps, email, and optional payment integrations.
10. Community, education, analytics, accessibility, security hardening, and deployment automation.

The roadmap is not a claim that those features are already available.
