import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Literal, Tuple

import streamlit as st
from PIL import Image

# Ensure project root is on sys.path when running via `streamlit run ui/dashboard.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.inference.run_inference import predict
from src.inference.gradcam import generate_gradcam
from src.reasoning.root_cause_agent import analyze_defect
from src.autonomy.drift_monitor import DriftMonitor
from src.autonomy.triage_agent import triage
from src.self_improvement.auto_retrainer import retrain_with_synthetic
from src.self_improvement.synthetic_generator import generate_synthetic_images


APP_TITLE = "AutoYield-AI | Autonomous Wafer QA"
UPLOAD_DIR = "outputs/uploads"
SYNTH_DIR = "outputs/synthetic_images"


def _setup_page() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🧪",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600;700&family=Space+Grotesk:wght@400;600;700&display=swap');

        :root {
            --bg-1: #0b1020;
            --bg-2: #121a2f;
            --card: rgba(255, 255, 255, 0.06);
            --card-border: rgba(255, 255, 255, 0.10);
            --accent: #8bf4c8;
            --accent-2: #ffd36a;
            --accent-3: #7fb4ff;
            --text: #eef2ff;
            --muted: #b6c0d4;
        }

        html, body, [class*="css"] {
            font-family: "IBM Plex Sans", sans-serif;
            background: radial-gradient(1200px 500px at 10% 0%, #162043 0%, var(--bg-1) 50%, #090f1d 100%);
            color: var(--text);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .hero {
            background: linear-gradient(120deg, rgba(139, 244, 200, 0.15), rgba(127, 180, 255, 0.10));
            border: 1px solid var(--card-border);
            border-radius: 18px;
            padding: 18px 22px;
            margin-bottom: 20px;
        }

        .hero h1 {
            font-family: "Space Grotesk", sans-serif;
            font-size: 2.2rem;
            margin-bottom: 0.2rem;
        }

        .hero p {
            color: var(--muted);
            margin: 0;
        }

        .card {
            background: var(--card);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 16px;
            box-shadow: 0 14px 28px rgba(0, 0, 0, 0.24);
            margin-bottom: 16px;
        }

        .pill {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 999px;
            background: rgba(139, 244, 200, 0.18);
            color: var(--accent);
            font-weight: 600;
            font-size: 0.85rem;
            margin-right: 8px;
        }

        .pill-warn {
            background: rgba(255, 211, 106, 0.15);
            color: var(--accent-2);
        }

        .pill-info {
            background: rgba(127, 180, 255, 0.18);
            color: var(--accent-3);
        }

        .stButton button {
            background: linear-gradient(120deg, #8bf4c8, #7fb4ff);
            color: #0b1020;
            border: none;
            border-radius: 10px;
            padding: 0.6rem 1rem;
            font-weight: 700;
        }

        .stProgress > div > div {
            background: linear-gradient(120deg, #8bf4c8, #ffd36a);
        }

        .section-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.2rem;
            margin-bottom: 0.6rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _save_upload(uploaded_file) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def _get_session_drift_monitor(
    confidence_threshold: float,
    max_low_confidence: int,
    synth_trigger_mode: Literal["below", "above"],
) -> DriftMonitor:
    """
    Return a DriftMonitor stored in Streamlit session state so the
    low-confidence counter persists across button clicks within a session.
    """
    if "drift_monitor" not in st.session_state:
        st.session_state["drift_monitor"] = DriftMonitor(
            confidence_threshold=confidence_threshold,
            max_low_confidence=max_low_confidence,
            trigger_mode=synth_trigger_mode,
        )
    # Always update monitor config so sidebar changes take effect immediately.
    dm = st.session_state["drift_monitor"]
    dm.configure(
        confidence_threshold=confidence_threshold,
        max_low_confidence=max_low_confidence,
        trigger_mode=synth_trigger_mode,
    )
    return dm


def _run_autonomous_pipeline(
    image_path: str,
    confidence_threshold: float,
    max_low_confidence: int,
    synth_trigger_mode: Literal["below", "above"],
    synth_count: int,
    synth_image_size: Tuple[int, int],
    auto_retrain: bool,
    retrain_epochs: int,
) -> Dict[str, Any]:
    defect_class, confidence = predict(image_path)
    cam_class, cam_path = generate_gradcam(image_path)
    reasoning = analyze_defect(defect_class, confidence)

    # Session-persistent drift monitor (accumulates across button clicks)
    drift_mon = _get_session_drift_monitor(
        confidence_threshold, max_low_confidence, synth_trigger_mode
    )
    drift_detected = drift_mon.update(confidence)

    # Active-learning triage
    triage_result = triage(
        image_path=image_path,
        predicted_class=defect_class,
        confidence=confidence,
    )

    synth_paths = []
    if drift_detected:
        synth_paths = generate_synthetic_images(
            output_dir=SYNTH_DIR,
            num_images=synth_count,
            image_size=synth_image_size,
            defect_class=defect_class,
        )

    retrain_result = None
    if synth_paths and auto_retrain:
        retrain_result = retrain_with_synthetic(
            synthetic_paths=synth_paths,
            target_class=defect_class,
            epochs=max(1, retrain_epochs),
            min_accuracy_delta=0.0,
        )

    return {
        "defect_class": defect_class,
        "confidence": confidence,
        "cam_class": cam_class,
        "cam_path": cam_path,
        "reasoning": reasoning,
        "drift_detected": drift_detected,
        "synth_trigger_mode": synth_trigger_mode,
        "triage": triage_result,
        "synth_paths": synth_paths,
        "retrain_result": retrain_result,
    }


def _render_summary(result: Dict[str, Any]) -> None:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Autonomy Decision</div>', unsafe_allow_html=True)

    if result["drift_detected"]:
        st.markdown(
            '<span class="pill pill-warn">Drift detected</span>'
            '<span class="pill pill-info">Synthetic data triggered</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<span class="pill">Healthy confidence</span>', unsafe_allow_html=True)

    triage_info = result.get("triage", {})
    if triage_info.get("queued"):
        reason_label = (
            "Low confidence"
            if triage_info["reason"] == "low_confidence"
            else "Ambiguous prediction"
        )
        st.markdown(
            f'<span class="pill pill-warn">🔬 Queued for human review ({reason_label})</span>',
            unsafe_allow_html=True,
        )

    st.write(
        f"**Prediction:** {result['defect_class']}  \n"
        f"**Confidence:** {result['confidence']:.3f}"
    )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_reasoning(reasoning: Dict[str, Any]) -> None:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">GenAI Root-Cause Analysis</div>', unsafe_allow_html=True)
    for key, value in reasoning.items():
        st.write(f"**{key}**: {value}")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_images(input_path: str, cam_path: str) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Uploaded Wafer</div>', unsafe_allow_html=True)
        st.image(Image.open(input_path), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Grad-CAM Heatmap</div>', unsafe_allow_html=True)
        st.image(Image.open(cam_path), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    _setup_page()

    st.markdown(
        """
        <div class="hero">
          <h1>Autonomous Wafer QA</h1>
          <p>Upload a wafer image and let AutoYield-AI run inference, Grad-CAM, GenAI reasoning, and drift-driven actions.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### Pipeline Controls")
        confidence_threshold = st.slider("Confidence Threshold", 0.1, 0.9, 0.45, 0.01)
        synth_trigger_mode = st.selectbox(
            "Synthetic Trigger Mode",
            options=["above", "below"],
            index=0,
            help=(
                "'above': generate when confidence is above threshold. "
                "'below': generate when confidence is below threshold."
            ),
        )
        max_low_confidence = st.slider("Consecutive Trigger Count", 1, 5, 1, 1)
        synth_count = st.slider("Synthetic Images", 2, 24, 10, 2)
        auto_retrain = st.checkbox("Auto Retrain on Synthetic Batch", value=False)
        retrain_epochs = st.slider("Retrain Epochs", 1, 5, 1, 1)
        synth_image_size = st.selectbox(
            "Synthetic Image Size",
            options=[(64, 64), (96, 96), (128, 128)],
            index=0,
        )
        st.markdown("---")
        st.markdown("Upload a wafer image and press **Run Analysis**.")

    uploaded = st.file_uploader(
        "Upload Wafer Image",
        type=["png", "jpg", "jpeg"],
    )

    run_clicked = st.button("Run Analysis")

    if uploaded and run_clicked:
        image_path = _save_upload(uploaded)

        with st.status("Running autonomous pipeline...", expanded=True) as status:
            st.write("Loading image and running inference...")
            time.sleep(0.2)
            st.write("Generating Grad-CAM heatmap...")
            time.sleep(0.2)
            st.write("Running GenAI root-cause analysis...")
            time.sleep(0.2)
            st.write("Checking drift and synthesizing data if needed...")

            result = _run_autonomous_pipeline(
                image_path=image_path,
                confidence_threshold=confidence_threshold,
                max_low_confidence=max_low_confidence,
                synth_trigger_mode=synth_trigger_mode,
                synth_count=synth_count,
                synth_image_size=synth_image_size,
                auto_retrain=auto_retrain,
                retrain_epochs=retrain_epochs,
            )
            status.update(label="Pipeline complete", state="complete", expanded=False)

        _render_images(image_path, result["cam_path"])
        _render_summary(result)
        _render_reasoning(result["reasoning"])

        if result["synth_paths"]:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Synthetic Samples</div>', unsafe_allow_html=True)
            st.image(
                [Image.open(p) for p in result["synth_paths"][:8]],
                use_container_width=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

        if result.get("retrain_result"):
            rr = result["retrain_result"]
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Retrain Outcome</div>', unsafe_allow_html=True)
            st.write(rr)
            st.markdown("</div>", unsafe_allow_html=True)

    elif run_clicked and not uploaded:
        st.warning("Please upload a wafer image to run the analysis.")


if __name__ == "__main__":
    main()
