# Starter Web App CI/CD Boilerplate

This repo is a beginner-friendly monorepo for a React frontend, FastAPI backend, SQLite demo database, Playwright tests, and GitHub Actions deployment to Vercel and Render.

## Quick Start

Run the backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Run the frontend in a second terminal:

```bash
cd frontend
npm install #if you havent installed
npm run dev
```

Open `http://localhost:5173`.

## Tests

Backend:

```bash
cd backend
pytest
```

Frontend build:

```bash
cd frontend
npm run build
```

End-to-end tests:

```bash
npm install
npm run install:browsers
npm run e2e
```

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

## Project Structure

```text
Mercedes_Vibathon26/
  .github/
    workflows/
      ci.yml
      deploy.yml
  backend/
    app/
      __init__.py
      main.py
      database.py
      models.py
      routes.py
    tests/
      test_health.py
      test_items.py
    .env.example
    requirements.txt
    pytest.ini
  frontend/
    src/
      App.jsx
      main.jsx
      api.js
      index.css
    public/
      favicon.svg
    .env.example
    index.html
    package.json
    vite.config.js
    tailwind.config.js
    postcss.config.js
  e2e/
    app.spec.js
  docs/
    ci-cd.md
  package.json
  playwright.config.js
  README.md
  .gitignore
```

- `.github/workflows/`: GitHub Actions automation for CI and deployment.
- `backend/`: FastAPI application, SQLite setup, API routes, and backend tests.
- `backend/app/main.py`: Creates the FastAPI app, CORS middleware, startup database initialization, and `/health` endpoint.
- `backend/app/database.py`: Opens SQLite connections, creates tables, and seeds demo data.
- `backend/app/models.py`: Defines request and response data shapes.
- `backend/app/routes.py`: Defines the sample `/api/items` endpoints.
- `frontend/`: React + Tailwind application and frontend build config.
- `frontend/src/api.js`: Central place for frontend API calls and `VITE_API_BASE_URL`.
- `frontend/src/App.jsx`: Starter UI that displays backend status and sample SQLite items.
- `e2e/`: Playwright browser tests that verify the full app flow.
- `docs/ci-cd.md`: Step-by-step CI/CD and GitHub Secrets setup notes.
- `playwright.config.js`: Starts backend/frontend dev servers and configures browser tests.
- `.env.example`: Safe example environment variables for local setup.
- `.gitignore`: Prevents committing dependencies, caches, build output, local databases, and real env files.
