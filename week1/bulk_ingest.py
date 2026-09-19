import os
import sys
import re
import random
import requests
FASTAPI_URL = "http://localhost:8000"
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls"}


def windows_to_wsl_path(path: str) -> str:
    """Convert a Windows path to a WSL-compatible path.
    
    Examples:
        C:\\Users\\JKA\\Docs  →  /mnt/c/Users/JKA/Docs
        D:\\Data             →  /mnt/d/Data
        /mnt/c/already/wsl  →  /mnt/c/already/wsl  (unchanged)
    """
    # Match Windows-style paths like C:\ or D:/
    match = re.match(r'^([A-Za-z]):[/\\](.*)$', path)
    if match:
        drive_letter = match.group(1).lower()
        rest = match.group(2).replace('\\', '/')
        return f"/mnt/{drive_letter}/{rest}"
    # Also handle backslashes in case of partial paths
    return path.replace('\\', '/')


def ingest_folder(folder_path: str):
    # Auto-convert Windows paths when running inside WSL
    folder_path = windows_to_wsl_path(folder_path)
    print(f"📁 Resolved path: {folder_path}")
    if not os.path.isdir(folder_path):
        print(f"❌ '{folder_path}' is not a valid directory.")
        return {"status": "error", "message": f"Invalid directory: {folder_path}"}
    total_files = 0
    total_chunks = 0
    errors = []
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            filepath = os.path.join(root, filename)
            # Source = the concatenate of three parent folder name + the filename
            # replace any underscore in the folder names with "-"
            source = os.path.basename(os.path.dirname(os.path.dirname(root))).replace("_", "-") + "-" + os.path.basename(os.path.dirname(root)).replace("_", "-") + "-" + os.path.basename(root).replace("_", "-")
            print("filename",filename)
            print("source",source)
            print("filepath",filepath)
            print("root",root)
            doc_id = str(random.randint(1, 9_999_999))
            print(f"📄 Ingesting: {filepath}")
            print(f"   Source: {source} | Doc ID: {doc_id}")
            try:
                with open(filepath, "rb") as f:
                    files_payload = {
                        "file": (filename, f, "application/octet-stream")
                    }
                    data_payload = {"doc_id": doc_id, "source": source}
                    response = requests.post(
                        f"{FASTAPI_URL}/api/v1/ingest-file",
                        files=files_payload,
                        data=data_payload,
                    )
                if response.status_code == 200:
                    result = response.json()
                    chunks = result["chunks_added"]
                    total_chunks += chunks
                    total_files += 1
                    print(f"   ✅ Success — {chunks} chunks added\n")
                else:
                    detail = response.json().get("detail", "Unknown error")
                    errors.append((filepath, detail))
                    print(f"   ❌ Failed — {detail}\n")
            except requests.exceptions.ConnectionError:
                print("   ❌ Cannot connect. Is FastAPI running on port 8000?\n")
                sys.exit(1)
            except Exception as e:
                errors.append((filepath, str(e)))
                print(f"   ❌ Error — {e}\n")
    # Summary
    print("=" * 50)
    print(f"✅ Done! Ingested {total_files} files ({total_chunks} total chunks)")
    if errors:
        print(f"⚠️  {len(errors)} file(s) failed:")
        for path, err in errors:
            print(f"   - {path}: {err}")