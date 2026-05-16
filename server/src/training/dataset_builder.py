import os
import random
from PIL import Image
from tqdm import tqdm

RAW_DATA_DIR = "data/raw"
PROCESSED_DATA_DIR = "data/processed"
IMAGE_SIZE = (224, 224)
TRAIN_SPLIT = 0.8
VALID_EXTENSIONS = (".png", ".jpg", ".jpeg")

def create_dir(path):
    os.makedirs(path, exist_ok=True)

def is_image_file(filename):
    return filename.lower().endswith(VALID_EXTENSIONS)

def resize_and_save(src_path, dst_path):
    try:
        with Image.open(src_path) as img:
            img = img.convert("RGB")
            img = img.resize(IMAGE_SIZE)
            img.save(dst_path)
    except Exception as e:
        print(f"⚠️ Skipping {src_path}: {e}")

def process_dataset():
    print("🔹 Starting dataset processing...")

    if not os.path.exists(RAW_DATA_DIR):
        raise FileNotFoundError(f"RAW_DATA_DIR not found: {RAW_DATA_DIR}")

    classes = [
        d for d in os.listdir(RAW_DATA_DIR)
        if os.path.isdir(os.path.join(RAW_DATA_DIR, d))
    ]

    print(f"Detected classes: {classes}")

    for split in ["train", "val"]:
        for cls in classes:
            create_dir(os.path.join(PROCESSED_DATA_DIR, split, cls))

    for cls in classes:
        class_dir = os.path.join(RAW_DATA_DIR, cls)
        images = [
            f for f in os.listdir(class_dir)
            if is_image_file(f)
        ]

        if len(images) == 0:
            print(f"⚠️ No images found in class: {cls}")
            continue

        random.shuffle(images)
        split_idx = int(len(images) * TRAIN_SPLIT)

        train_images = images[:split_idx]
        val_images = images[split_idx:]

        print(f"\nClass: {cls}")
        print(f"  Total: {len(images)} | Train: {len(train_images)} | Val: {len(val_images)}")

        for img_name in tqdm(train_images, desc=f"{cls} (train)"):
            resize_and_save(
                os.path.join(class_dir, img_name),
                os.path.join(PROCESSED_DATA_DIR, "train", cls, img_name)
            )

        for img_name in tqdm(val_images, desc=f"{cls} (val)"):
            resize_and_save(
                os.path.join(class_dir, img_name),
                os.path.join(PROCESSED_DATA_DIR, "val", cls, img_name)
            )

    print("\n✅ Dataset processing complete.")

if __name__ == "__main__":
    process_dataset()
