# Starter Web App CI/CD Boilerplate

This repo is a beginner-friendly monorepo for a React frontend, FastAPI backend, SQLite demo database, Playwright end-to-end tests, and GitHub Actions deployment to Vercel and Render.

The goal is simple: teammates can clone the repo, run the app locally, create pull requests, and let CI/CD check the work before anything deploys.

## What You Need Installed

Before running the project, install:

- Git
- Node.js 20 or newer
- npm, included with Node.js
- Python 3.11 or newer

Check your versions:

```bash
node --version
npm --version
python --version
git --version
```

## Quick Start

Install backend dependencies:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Start the backend:

```bash
python -m uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000`.

In a second terminal, install and start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Environment Files

This repo includes safe example files:

- `backend/.env.example`
- `frontend/.env.example`

If you need local environment variables, copy the example file and rename it to `.env` in the same folder.

Example:

```bash
cd frontend
copy .env.example .env
```

Do not commit real `.env` files. They are ignored by Git.

## How The App Fits Together

The frontend and backend are separate apps:

- The frontend is the user interface. It runs in the browser with React.
- The backend is the API. It runs with FastAPI and stores demo data in SQLite.
- The frontend talks to the backend through `VITE_API_BASE_URL`.
- Playwright opens the frontend in a real browser and checks that the full app works.
- GitHub Actions runs tests automatically when code is pushed or a pull request is opened.

Local flow:

```text
Browser -> React frontend -> FastAPI backend -> SQLite database
```

CI/CD flow:

```text
Pull request -> GitHub Actions tests -> merge to main -> Vercel frontend deploy + Render backend deploy
```

## Tests

Run backend tests:

```bash
cd backend
pytest
```

Run the frontend production build:

```bash
cd frontend
npm run build
```

Run end-to-end tests:

```bash
npm install
npm run install:browsers
npm run e2e
```

## How Playwright Works

Playwright is used for end-to-end testing. That means it tests the app like a real user would:

1. It starts the FastAPI backend.
2. It starts the Vite frontend.
3. It opens a Chromium browser.
4. It visits `http://127.0.0.1:5173`.
5. It checks that the page loads and displays data from the backend.

The main Playwright files are:

- `playwright.config.js`: Defines how Playwright starts the backend and frontend.
- `e2e/app.spec.js`: Contains the browser test.

When adding a new user flow, add a new test in `e2e/`.

Good examples:

- Test that a page loads.
- Test that a button creates an item.
- Test that form validation appears.
- Test that the frontend displays API data correctly.

## How To Work In This Repo

Use existing files when the change belongs to an existing feature. Add new files when the feature becomes large enough to deserve its own place.

Frontend:

- Add reusable API calls in `frontend/src/api.js`.
- Add page or UI behavior in `frontend/src/App.jsx`.
- Add global styles in `frontend/src/index.css`.
- Add new React components under `frontend/src/` when `App.jsx` becomes too crowded.

Backend:

- Add new API endpoints in `backend/app/routes.py`.
- Add request and response models in `backend/app/models.py`.
- Add database setup or helper functions in `backend/app/database.py`.
- Add backend tests in `backend/tests/`.

Testing:

- Add backend unit/API tests in `backend/tests/`.
- Add browser tests in `e2e/`.
- Run tests before opening a pull request.

Documentation:

- Update this README when setup steps or file responsibilities change.
- Update `docs/ci-cd.md` when deployment or GitHub Secrets change.

## GitHub Secrets

Add these repository secrets in GitHub under **Settings > Secrets and variables > Actions**:

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
- `RENDER_DEPLOY_HOOK_URL`
- `VITE_API_BASE_URL`
- `BACKEND_CORS_ORIGINS`

Real values belong in GitHub, Vercel, Render, or local `.env` files. Do not commit real secrets.

## Deployment

GitHub Actions runs tests on pull requests and pushes. Pushes to `main` run the deployment workflow after backend tests, frontend build, and Playwright E2E tests pass.

- Frontend deploys to Vercel from `frontend/`.
- Backend deploy is triggered on Render using `RENDER_DEPLOY_HOOK_URL`.
- On Render, set `CORS_ORIGINS` to the same frontend URL stored in `BACKEND_CORS_ORIGINS`.
- SQLite is local/demo persistence. Use a Render persistent disk or hosted Postgres for durable production data.

More setup notes are in `docs/ci-cd.md`.

## Project Structure

```text
Mercedes_Vibathon26/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── routes.py
│   ├── tests/
│   │   ├── test_health.py
│   │   └── test_items.py
│   ├── .env.example
│   ├── pytest.ini
│   └── requirements.txt
├── docs/
│   └── ci-cd.md
├── e2e/
│   └── app.spec.js
├── frontend/
│   ├── public/
│   │   └── favicon.svg
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── index.css
│   │   └── main.jsx
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── vite.config.js
├── .gitignore
├── README.md
├── package-lock.json
├── package.json
└── playwright.config.js
```

## File And Folder Breakdown

- `.github/workflows/`: GitHub Actions automation for CI and deployment.
- `.github/workflows/ci.yml`: Runs tests and builds on pull requests and pushes.
- `.github/workflows/deploy.yml`: Deploys from `main` after checks pass.
- `backend/`: FastAPI application, SQLite setup, API routes, and backend tests.
- `backend/app/main.py`: Creates the FastAPI app, CORS middleware, startup database initialization, and `/health` endpoint.
- `backend/app/database.py`: Opens SQLite connections, creates tables, and seeds demo data.
- `backend/app/models.py`: Defines request and response data shapes.
- `backend/app/routes.py`: Defines the sample `/api/items` endpoints.
- `backend/tests/`: Backend tests for API behavior.
- `frontend/`: React + Tailwind application and frontend build config.
- `frontend/src/main.jsx`: Starts the React app.
- `frontend/src/App.jsx`: Starter UI that displays backend status and sample SQLite items.
- `frontend/src/api.js`: Central place for frontend API calls and `VITE_API_BASE_URL`.
- `frontend/src/index.css`: Tailwind imports and global styles.
- `e2e/`: Playwright browser tests that verify the full app flow.
- `docs/ci-cd.md`: Step-by-step CI/CD and GitHub Secrets setup notes.
- `package.json`: Root scripts for Playwright.
- `playwright.config.js`: Starts backend/frontend dev servers and configures browser tests.
- `.env.example`: Safe example environment variables for local setup.
- `.gitignore`: Prevents committing dependencies, caches, build output, local databases, and real env files.

## Common Issues

If the frontend says the API is offline:

- Make sure the backend is running on `http://localhost:8000`.
- Check `frontend/.env` and confirm `VITE_API_BASE_URL=http://localhost:8000`.

If `pytest` is not recognized:

- Activate the backend virtual environment.
- Run `pip install -r requirements.txt` again.

If `npm run e2e` fails because browsers are missing:

```bash
npm run install:browsers
```

If a teammate gets dependency issues:

- Delete `node_modules/` in the affected folder.
- Run `npm install` again.
- For Python, recreate `.venv` and rerun `pip install -r requirements.txt`.
