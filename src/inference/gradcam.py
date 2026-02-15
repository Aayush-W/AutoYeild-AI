import torch
import torch.nn.functional as F
import numpy as np
import cv2
from torchvision import transforms
from torchvision.models import efficientnet_b0
from PIL import Image
import os

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

MODEL_PATH = "models/baseline_model.pt"
IMAGE_SIZE = (224, 224)
OUTPUT_DIR = "outputs/heatmaps"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------
# Load model
# -------------------------
checkpoint = torch.load(MODEL_PATH, map_location=DEVICE)
class_names = checkpoint["class_names"]
num_classes = len(class_names)

model = efficientnet_b0(weights=None)
in_features = model.classifier[1].in_features
model.classifier[1] = torch.nn.Linear(in_features, num_classes)
model.load_state_dict(checkpoint["model_state_dict"])
model = model.to(DEVICE)
model.eval()

# Target layer for Grad-CAM
target_layer = model.features[-1]

# -------------------------
# Hooks
# -------------------------
gradients = None
activations = None

def backward_hook(module, grad_input, grad_output):
    global gradients
    gradients = grad_output[0]

def forward_hook(module, input, output):
    global activations
    activations = output

target_layer.register_forward_hook(forward_hook)
target_layer.register_backward_hook(backward_hook)

# -------------------------
# Grad-CAM Function
# -------------------------
# Match training preprocessing (ImageNet norm)
imagenet_norm = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
gradcam_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(IMAGE_SIZE),
    transforms.ToTensor(),
    imagenet_norm,
])


def generate_gradcam(image_path):
    image = Image.open(image_path).convert("RGB")
    input_tensor = gradcam_transform(image).unsqueeze(0).to(DEVICE)

    output = model(input_tensor)
    pred_class = output.argmax(dim=1).item()

    model.zero_grad()
    output[0, pred_class].backward()

    pooled_grads = torch.mean(gradients, dim=[0, 2, 3])

    for i in range(activations.shape[1]):
        activations[:, i, :, :] *= pooled_grads[i]

    heatmap = torch.mean(activations, dim=1).squeeze()
    heatmap = F.relu(heatmap)
    heatmap /= torch.max(heatmap)
    heatmap = heatmap.cpu().detach().numpy()

    heatmap = cv2.resize(heatmap, IMAGE_SIZE)
    heatmap = np.uint8(255 * heatmap)

    image_np = np.array(image.resize(IMAGE_SIZE))
    heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)

    overlay = cv2.addWeighted(image_np, 0.6, heatmap_color, 0.4, 0)

    output_path = os.path.join(
        OUTPUT_DIR, f"gradcam_{os.path.basename(image_path)}"
    )
    cv2.imwrite(output_path, overlay)

    return class_names[pred_class], output_path
