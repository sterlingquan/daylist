# Daylist

A responsive, full-stack to-do application built with React, FastAPI, and PostgreSQL. Create, edit, delete, complete, search, filter, and sort tasks. Data is committed to the database before the interface confirms a change.

## Requirements

- Node.js 22 and npm
- Python 3.13
- PostgreSQL (or Docker Desktop for the included database container)

## Run locally

From the repository root:

```sh
docker compose up -d db
python3.13 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env
cd backend
uvicorn app.main:app --reload
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Interactive API documentation: http://localhost:8000/docs. The first backend startup creates the `tasks` table. PostgreSQL persists in the `todo_data` Docker volume; `docker compose down` preserves it, while `docker compose down -v` deletes it. You can use an existing PostgreSQL server by setting `DATABASE_URL` in `backend/.env` instead.

## Configuration

| Location | Variable | Value |
| --- | --- | --- |
| Backend | `DATABASE_URL` | PostgreSQL connection string; `postgres://`, `postgresql://`, and `postgresql+psycopg://` are supported |
| Backend | `CORS_ORIGINS` | Comma-separated exact frontend origins, without trailing slashes |
| Frontend | `VITE_API_URL` | Backend origin, e.g. `https://daylist-api.onrender.com`, without `/api` |

The Vite dev server proxies `/api` to port 8000 when `VITE_API_URL` is empty. Production requires the Render backend URL at frontend build time. Never put database credentials into a `VITE_` variable: those are visible in the browser. `.env` files are ignored by Git.

## Deploy: GitHub → Neon → Render → Netlify

Deployment files are included, but creating the repository and live services requires your connected accounts. No hosted resources or public URLs are preconfigured.

1. Create an empty GitHub repository and push this project:

   ```sh
   git init -b main
   git add .
   git commit -m "Build Daylist full-stack task application"
   git remote add origin https://github.com/YOUR_USERNAME/daylist.git
   git push -u origin main
   ```

2. In **Neon**, create a PostgreSQL project and copy its pooled connection string. Keep `sslmode=require` and any supplied connection parameters. The backend accepts Neon's normal `postgresql://` URL and selects psycopg automatically.
3. In **Render**, create a Blueprint from your repository. The included `render.yaml` defines the Python service. Supply `DATABASE_URL` with the Neon URL and `CORS_ORIGINS` with your eventual Netlify origin (you can update this after creating the frontend). Deploy, then check `/health` and `/docs` on the returned Render URL.
4. In **Netlify**, import the same GitHub repository. The root `netlify.toml` sets base `frontend`, build `npm ci && npm run build`, and publish `dist`. Set `VITE_API_URL` to the actual Render HTTPS origin, then deploy.
5. Update Render `CORS_ORIGINS` to the exact Netlify HTTPS origin and redeploy the backend. If you change `VITE_API_URL`, rebuild the frontend.
6. Verify the live flow: create a task with every field, refresh, edit, complete, switch filters, search by title, change sort order, mark pending, delete, and refresh again. Confirm mobile layout and validation of an empty title.

Free service availability and quotas depend on each provider's current terms. The app has no authentication, as requested: all visitors to a deployment share its task list and can edit/delete those tasks. Use it for shared demo data.

Provider references: [Render FastAPI deployment](https://render.com/docs/deploy-fastapi), [Netlify environment variables](https://docs.netlify.com/build/environment-variables/get-started/), [Neon connection guide](https://neon.com/docs/get-started/connect-neon).

## Verify

```sh
cd backend
source .venv/bin/activate
python -m pytest -q
```

Tests use a temporary SQLite database by default for an isolated run. To verify against an isolated PostgreSQL database (tests drop the `tasks` table; never use production):

```sh
TEST_DATABASE_URL=postgresql+psycopg://todo:todo@localhost:5432/todo_test python -m pytest -q
```

GitHub Actions runs the API suite against PostgreSQL 17 and builds the frontend. Run the frontend build locally with `cd frontend && npm ci && npm run build`.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Database connectivity check |
| GET | `/api/tasks?q=&status=all&sort=newest` | List/search/filter/sort tasks |
| POST | `/api/tasks` | Create a task |
| PATCH | `/api/tasks/{id}` | Update selected fields, including `completed` |
| DELETE | `/api/tasks/{id}` | Delete a task |

Title: 1–200 characters after trimming; description: up to 5,000 characters; priority: `low`, `medium`, `high`; due date: ISO `YYYY-MM-DD` or null. Filters: `all`, `pending`, `completed`. Sort: `newest`, `oldest`, by creation time with ID as tie-breaker. Validation errors return 422, missing tasks return 404, and database operation failures return 503. Initial schema creation is automatic; future schema changes should use migrations.

## Five-day project plan

1. Database model, API routes, validation, and local PostgreSQL.
2. React dashboard and create/edit/delete forms.
3. Completion, search, filters, sorting, responsive layout, and error states.
4. API integration checks, PostgreSQL tests, and production builds.
5. Connect hosting accounts, deploy, and verify the complete live flow.

## Structure

```text
backend/app/main.py       FastAPI API, SQLAlchemy model, validation
backend/tests/           API integration tests
frontend/src/main.jsx    React dashboard and task interactions
frontend/src/styles.css  Responsive styling
compose.yaml             Local PostgreSQL with persistent volume
render.yaml              Backend deployment blueprint
netlify.toml             Frontend build and routing configuration
.github/workflows/ci.yml PostgreSQL API checks and frontend build
```
