
# AutoYield-AI

AutoYield-AI is an autonomous wafer quality pipeline that combines computer vision inference, explainability, drift monitoring, and GenAI-assisted root-cause analysis. It includes a FastAPI backend, a React/Vite operations dashboard, and a Streamlit demo UI.

**What it does**
- Runs defect classification on wafer images using an EfficientNet-B0 model.
- Generates Grad-CAM heatmaps for visual explainability.
- Produces root-cause summaries using deterministic rules or **Retrieval-Augmented Generation (RAG) + Gemini AI**.
- Tracks drift based on confidence and triggers synthetic data generation and retraining pipelines.
- Serves a React dashboard and a Streamlit demo app.

**Tech stack**
- Backend: FastAPI, PyTorch, torchvision, OpenCV, NumPy, scikit-learn
- Frontend: React, Vite, React Router
- GenAI & RAG: Google Gemini via `google-generativeai`, FAISS, Sentence-Transformers

## Quick Start

**1) Backend API (FastAPI)**

```bash
pip install -r requirements.txt
pip install torch torchvision opencv-python pillow

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
npm run dev
```

The UI expects the API at `http://localhost:8000`.

**3) Streamlit demo**

```bash
pip install streamlit
streamlit run ui/dashboard.py
```

## Environment Variables

The AI Insight Engine leverages a RAG (Retrieval-Augmented Generation) pipeline backed by Google Gemini. If you want the system to ground its reasoning in semiconductor knowledge bases, you must configure a Gemini API Key.

Create a `.env` file in the root directory:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Without a valid key, the system seamlessly falls back to using deterministic logical rules for explainability.

## Project Structure

```
api/                    FastAPI service
src/                    Core ML pipeline (inference, explainability, drift, reasoning)
ui/                     Streamlit demo
web/                    React/Vite dashboard
models/                 Model checkpoints (baseline and updated)
data/                   Raw and processed wafer image datasets
outputs/                Heatmaps, synthetic images, metrics, uploads
config/                 YAML configs and prompt templates
```

## Notes on Data and Models

This repository includes large datasets and model files under `data/`, `outputs/`, and `models/`. If you plan to push to GitHub, consider using Git LFS or moving large assets to external storage.


