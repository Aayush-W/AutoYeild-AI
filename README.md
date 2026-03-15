# AutoYield-AI

AutoYield-AI is an autonomous wafer quality pipeline that combines computer vision inference, explainability, drift monitoring, and GenAI-assisted root-cause analysis. It includes a FastAPI backend, a React/Vite operations dashboard, and a Streamlit demo UI.

**What it does**
- Runs defect classification on wafer images using an EfficientNet-B0 model.
- Generates Grad-CAM heatmaps for visual explainability.
- Produces root-cause summaries using deterministic rules or Gemini (optional).
- Tracks drift based on confidence and triggers synthetic data generation.
- Serves a React dashboard and a Streamlit demo app.

**Tech stack**
- Backend: FastAPI, PyTorch, torchvision, OpenCV, NumPy, scikit-learn
- Frontend: React, Vite, React Router
- Optional GenAI: Google Gemini via `google-generativeai`

## Quick Start

**1) Backend API (FastAPI)**

```bash
pip install -r requirements.txt
pip install torch torchvision opencv-python pillow

# create .env from .env.example and set MONGO_URI first
uvicorn api.app:app --reload --port 8000
```

The API exposes:
- `POST /api/analyze` for image analysis
- `GET /api/history` for recent inspections
- `GET /api/metrics` for dashboard summary

**2) Web dashboard (React + Vite)**

```bash
cd web
npm install
# create web/.env from web/.env.example if needed
npm run dev
```

The UI expects the API at `http://localhost:8000`.

**3) Streamlit demo**

```bash
pip install streamlit
streamlit run ui/dashboard.py
```

## Environment Variables

Backend (`.env` at project root):

```bash
MONGO_URI=mongodb+srv://YOUR_DB_USER:YOUR_DB_PASSWORD@cluster0.0dwbwfe.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
MONGO_DB_NAME=autoyield
MONGO_SERVER_SELECTION_TIMEOUT_MS=5000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```
If your MongoDB password contains special characters (`@`, `:`, `/`, `?`, `#`, `%`), URL-encode it in `MONGO_URI`.

Frontend (`web/.env`):

```bash
VITE_API_BASE_URL=http://localhost:8000
```

Optional Gemini root-cause analysis:

```bash
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
```

Without these, the system uses deterministic fallback rules.

## Project Structure

```
api/                    FastAPI service
src/                    Core ML pipeline (inference, explainability, drift, reasoning)
scripts/rag/            RAG ingestion/indexing scripts (extract, chunk, embed, search)
tests/manual/           One-off manual verification scripts
ui/                     Streamlit demo
web/                    React/Vite dashboard
models/                 Model checkpoints (baseline and updated)
data/                   Raw and processed wafer image datasets
outputs/                Heatmaps, synthetic images, metrics, uploads
outputs/debug/          Local debug/log output from manual runs
config/                 YAML configs and prompt templates
```

## Notes on Data and Models

This repository includes large datasets and model files under `data/`, `outputs/`, and `models/`. If you plan to push to GitHub, consider using Git LFS or moving large assets to external storage.
