# CI/CD Setup

This project uses GitHub Actions to test every pull request and deploy from `main`.

## GitHub Secrets

Create these secrets in GitHub under **Settings > Secrets and variables > Actions > New repository secret**.

| Secret | Used by | Purpose |
| --- | --- | --- |
| `VERCEL_TOKEN` | GitHub Actions | Authenticates the Vercel CLI. |
| `VERCEL_ORG_ID` | GitHub Actions | Selects the Vercel team or personal account. |
| `VERCEL_PROJECT_ID` | GitHub Actions | Selects the frontend Vercel project. |
| `RENDER_DEPLOY_HOOK_URL` | GitHub Actions | Triggers a Render backend deploy after tests pass. |
| `VITE_API_BASE_URL` | GitHub Actions, Vercel build | Points the frontend at the deployed backend URL. |
| `BACKEND_CORS_ORIGINS` | GitHub Actions, Render setup reference | Lists frontend origins allowed to call the backend. |

Never commit real secret values to the repo. Keep only `.env.example` files in source control.

## Local Development

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

E2E tests:

```bash
npm install
npm run install:browsers
npm run e2e
```

## Deployment Notes

- Vercel should point to the `frontend` project.
- Render should point to the `backend` project.
- Render build command: `pip install -r requirements.txt`
- Render start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Set Render env var `CORS_ORIGINS` to the same value as the GitHub secret `BACKEND_CORS_ORIGINS`.
- SQLite is fine for local/demo data. For durable Render data, add a persistent disk or move to hosted Postgres later.
