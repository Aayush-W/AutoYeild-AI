import torch
import torch.nn as nn
from torchvision.models import convnext_small, ConvNeXt_Small_Weights

class ConvNeXtDefectClassifier(nn.Module):
    def __init__(self, num_classes: int, pretrained: bool = True, dropout: float = 0.3):
        super().__init__()
        weights = ConvNeXt_Small_Weights.DEFAULT if pretrained else None
        self.model = convnext_small(weights=weights)
        
        # Replace classifier head
        # convnext_small.classifier[2] is the Linear layer
        in_features = self.model.classifier[2].in_features
        
        # Adding Dropout for regularization as requested
        self.model.classifier = nn.Sequential(
            self.model.classifier[0], # LayerNorm
            self.model.classifier[1], # Flatten
            nn.Dropout(p=dropout),
            nn.Linear(in_features, num_classes)
        )
        
    def forward(self, x):
        return self.model(x)

    @property
    def target_layer(self):
        """Used for Grad-CAM"""
        return self.model.features[-1]

def load_convnext_model(num_classes: int, pretrained: bool = True, device: str = "cpu", dropout: float = 0.3):
    model = ConvNeXtDefectClassifier(num_classes, pretrained=pretrained, dropout=dropout)
    model.to(device)
    model.eval()
    return model
