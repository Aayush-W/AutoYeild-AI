# AutoYield AI Deployment Guide

This repo is best deployed as two services:

- **Backend**: FastAPI ML API in a Docker web service.
- **Frontend**: Vite static site from `client/`.

The backend is not a good pure serverless target because it loads PyTorch, OpenCV, model files, and writes temporary output artifacts. Use Render, Railway, Fly.io, Cloud Run, or another container host for the API.

---

## 1. Prepare Secrets

Create production values for:

```bash
MONGO_URI=mongodb+srv://...
MONGO_DB_NAME=autoyield
MONGO_SERVER_SELECTION_TIMEOUT_MS=5000
CORS_ORIGINS=https://your-frontend-domain.netlify.app,https://your-custom-domain.com
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash
AUTOYIELD_TOOL_NAME=Litho-04
AUTOYIELD_PROCESS_STAGE=wafer-inspection
AUTOYIELD_TARGET_LAYER=M2_Cu
```

Do not commit `.env` files.

---

## 2. MongoDB Atlas

1. Create or open your Atlas cluster.
2. Create a database user for the app.
3. Add your backend host to Atlas Network Access.
4. During initial setup, `0.0.0.0/0` is convenient but less restrictive.
5. Copy the app connection string into `MONGO_URI`.

If your password contains special characters such as `@`, `:`, `/`, `?`, `#`, or `%`, URL-encode the password in `MONGO_URI`.

---

## 3. Backend On Render

1. Push this repo to GitHub.
2. In Render, create a new Web Service.
3. Connect the GitHub repo.
4. Set the service language/runtime to **Docker**.
5. Set the **Docker Build Context** to `server`.
6. Set the **Dockerfile Path** to `Dockerfile` (relative to the context `server/`).
7. Add environment variables from section 1.
8. Set the health check path to `/api/health`.
9. Deploy.

After deployment, verify:

```bash
curl https://your-backend.onrender.com/api/health
curl https://your-backend.onrender.com/api/metrics
```

If `/api/metrics` fails but `/api/health` works, check MongoDB Atlas network access and the `MONGO_URI` value.

---

## 4. Frontend On Netlify

1. Create a new Netlify site from the same GitHub repo.
2. Set the **base directory** to `client`.
3. Set the **build command** to `npm run build`.
4. Set the **publish directory** to `dist` (relative to the base directory `client/`).
5. Add:
   ```bash
   VITE_API_BASE_URL=https://your-backend.onrender.com
   ```
6. Deploy.

The `client/netlify.toml` file handles React Router fallback routes.

---

## 5. Frontend On Vercel

Use this instead of Netlify if you prefer Vercel:

1. Import the GitHub repo in Vercel.
2. Set the project **root directory** to `client`.
3. Framework preset should be Vite.
4. Build command: `npm run build`.
5. Output directory: `dist`.
6. Add:
   ```bash
   VITE_API_BASE_URL=https://your-backend.onrender.com
   ```
7. Deploy.

The `client/vercel.json` file handles React Router fallback routes.

---

## 6. Update CORS

After the frontend deploys, copy its production URL and update the backend environment variable:

```bash
CORS_ORIGINS=https://your-site.netlify.app,https://your-custom-domain.com
```

Redeploy or restart the backend after changing this value.

---

## 7. Production Smoke Test

1. Open the frontend production URL.
2. Open browser DevTools and check for CORS or network errors.
3. Confirm dashboard metrics load.
4. Upload a small wafer image and confirm `/api/analyze` returns a result.
5. Generate a report and confirm the PDF download works.
6. Test a direct route refresh, such as `/defect-detection`.

---

## 8. Repo Cleanup Before Serious Production

Before connecting automated deploys, remove generated and local-only files from git tracking:

```bash
git rm -r --cached --ignore-unmatch server/.venv server/venv client/node_modules client/dist
git rm -r --cached --ignore-unmatch server/data server/outputs server/reports
git rm -r --cached --ignore-unmatch server/__pycache__ server/api/__pycache__ server/config/__pycache__
git rm -r --cached --ignore-unmatch "server/src/**/__pycache__"
```

Keep only the runtime model files you truly need under `server/models/`, or move them to object storage and download them during container startup.

---

## 9. Common Issues

- **Build runs at repo root**: set Netlify/Vercel base/root directory to `client`.
- **Frontend calls localhost**: set `VITE_API_BASE_URL` to the deployed backend URL.
- **Browser shows CORS errors**: update backend `CORS_ORIGINS`.
- **Backend deploy fails during startup**: verify `MONGO_URI` and Atlas Network Access.
- **Docker image is too large or slow**: move model artifacts to object storage and remove training/data folders from the deployment context.
