import os
import shutil
from pathlib import Path

workspace_root = Path(r"c:\Users\Aayush Walsangikar\OneDrive\Desktop\AutoYeildAI")

# Create server directory
server_dir = workspace_root / "server"
server_dir.mkdir(exist_ok=True)

# List of folders/files to move to server
server_items = [
    "api", "src", "config", "data", "models", "rag_data", "scripts", "tests", "ui", "outputs", "reports", "runlogs",
    "requirements.txt", "Dockerfile", ".dockerignore", ".env", ".env.example", "pyrightconfig.json", ".venv", "venv"
]

for item_name in server_items:
    src_path = workspace_root / item_name
    if src_path.exists():
        dest_path = server_dir / item_name
        print(f"Moving {src_path} -> {dest_path}")
        try:
            shutil.move(str(src_path), str(dest_path))
        except Exception as e:
            print(f"Error moving {item_name}: {e}")

# Rename web to client
web_dir = workspace_root / "web"
client_dir = workspace_root / "client"
if web_dir.exists():
    print(f"Renaming {web_dir} -> {client_dir}")
    try:
        shutil.move(str(web_dir), str(client_dir))
    except Exception as e:
        print(f"Error renaming web: {e}")

# Delete package-lock.json in root if it exists
pkg_lock = workspace_root / "package-lock.json"
if pkg_lock.exists():
    print("Deleting root package-lock.json")
    try:
        os.remove(pkg_lock)
    except Exception as e:
        print(f"Error deleting package-lock.json: {e}")

# Move APGS_PAPER_IEEE[1].docx to docs/
docx_file = workspace_root / "APGS_PAPER_IEEE[1].docx"
docs_dir = workspace_root / "docs"
if docx_file.exists():
    docs_dir.mkdir(exist_ok=True)
    print(f"Moving {docx_file} -> {docs_dir}")
    try:
        shutil.move(str(docx_file), str(docs_dir / docx_file.name))
    except Exception as e:
        print(f"Error moving docx file: {e}")

print("Restructuring script completed successfully!")
