# AutoYield-AI

AutoYield-AI is an autonomous wafer quality pipeline that combines computer vision inference, explainability, drift monitoring, and GenAI-assisted root-cause analysis. It is structured as a clean full-stack monorepo containing a FastAPI backend, a React/Vite operations dashboard, and a Streamlit demo UI.

**What it does**
- Runs defect classification on wafer images using an EfficientNet-B0 model.
- Generates Grad-CAM heatmaps for visual explainability.
- Produces root-cause summaries using deterministic rules or Gemini (optional).
- Tracks drift based on confidence and triggers synthetic data generation.
- Serves a React dashboard and a Streamlit demo app.

**Tech Stack**
- Backend: FastAPI, PyTorch, torchvision, OpenCV, NumPy, scikit-learn
- Frontend: React, Vite, React Router
- Optional GenAI: Google Gemini via `google-generativeai`

---

## Workspace Structure

```
AutoYeildAI/                    (Root Workspace)
├── client/                      (Frontend Application - React + Vite)
├── server/                      (Backend Application - FastAPI + ML Pipelines)
└── docs/                        (Overall system architecture and documentation)
```

---

## Quick Start

### 1) Backend API (FastAPI)

```bash
# Navigate to the server folder
cd server

# Install dependencies (use virtual environment if desired)
pip install -r requirements.txt
pip install torch torchvision opencv-python pillow

# Create server/.env from server/.env.example and set MONGO_URI
uvicorn api.app:app --reload --port 8000
```

The API exposes:
- `POST /api/analyze` for image analysis
- `GET /api/history` for recent inspections
- `GET /api/metrics` for dashboard summary

### 2) Web Dashboard (React + Vite)

```bash
# Navigate to the client folder
cd client

# Install dependencies
npm install

# Create client/.env from client/.env.example if needed
npm run dev
```

The UI expects the API at `http://localhost:8000`.

### 3) Streamlit Demo

```bash
# Navigate to the server folder
cd server

# Run the Streamlit dashboard
streamlit run ui/dashboard.py
```

---

## Environment Variables

### Backend (`server/.env`):

```bash
MONGO_URI=mongodb+srv://YOUR_DB_USER:YOUR_DB_PASSWORD@cluster0.0dwbwfe.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
MONGO_DB_NAME=autoyield
MONGO_SERVER_SELECTION_TIMEOUT_MS=5000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```
If your MongoDB password contains special characters (`@`, `:`, `/`, `?`, `#`, `%`), URL-encode it in `MONGO_URI`.

### Frontend (`client/.env`):

```bash
VITE_API_BASE_URL=http://localhost:8000
```

### Optional Gemini Root-Cause Analysis:

```bash
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
```

Without these, the system uses fallback rules.

---

## Project Structure Detail

```
client/                 React/Vite frontend dashboard
server/                 Backend workspace
├── api/                FastAPI service
├── src/                Core ML pipeline (inference, explainability, drift, reasoning)
├── scripts/            RAG ingestion/indexing scripts
├── config/             YAML configs and prompt templates
├── models/             Model checkpoints
├── data/               Raw and processed wafer datasets
├── ui/                 Streamlit demo
├── tests/              Unit and integration tests
├── outputs/            Local inference/run-time outputs (uploads, heatmaps, synthetics)
├── reports/            Generated PDF/HTML reports
└── runlogs/            Execution logs
docs/                   Overall system architecture and documentation
```

## Notes on Data and Models

This repository includes large datasets and model files under `server/data/`, `server/outputs/`, and `server/models/`. If you plan to push to GitHub, consider using Git LFS or moving large assets to external storage.
