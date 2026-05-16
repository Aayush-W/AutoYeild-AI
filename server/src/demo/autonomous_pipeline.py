from src.inference.run_inference import predict
from src.inference.gradcam import generate_gradcam
from src.reasoning.root_cause_agent import analyze_defect
from src.autonomy.drift_monitor import DriftMonitor
from src.self_improvement.synthetic_generator import generate_synthetic_images


def run_autonomous_analysis(image_path):
    print("\n=== AUTOYIELD-AI AUTONOMOUS ANALYSIS ===\n")

    # 1) Inference
    defect_class, confidence = predict(image_path)
    print(f"Prediction       : {defect_class}")
    print(f"Confidence       : {confidence:.3f}")

    # 2) Explainability
    cam_class, cam_path = generate_gradcam(image_path)
    print(f"Grad-CAM saved   : {cam_path}")

    # 3) GenAI Reasoning
    reasoning = analyze_defect(defect_class, confidence)
    print("\n--- GenAI Root-Cause Analysis ---")
    for k, v in reasoning.items():
        print(f"{k}: {v}")

    # 4) Drift Detection
    drift_monitor = DriftMonitor()
    drift_detected = drift_monitor.update(confidence)

    print("\n--- Autonomy Decision ---")
    if drift_detected:
        print("Drift detected!")
        print("Triggering synthetic data generation & auto-retraining pipeline...")
        synth_paths = generate_synthetic_images()
        print(f"Generated {len(synth_paths)} synthetic images.")
    else:
        print("Model confidence within acceptable range.")
        print("No retraining required.")

    print("\n=== ANALYSIS COMPLETE ===\n")


if __name__ == "__main__":
    # CHANGE THIS to any test image
    test_image = "data/processed/val/clean/757328.jpg"
    run_autonomous_analysis(test_image)
