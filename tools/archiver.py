import os
import zipfile
import tarfile
from pathlib import Path

def archive_files(action: str, archive_path: str, source_path: str) -> str:
    """
    Compress or extract ZIP or TAR archives.

    Args:
        action: 'zip', 'unzip', 'tar', or 'untar'.
        archive_path: Path to the target/source archive file.
        source_path: Path to directory or files to compress or destination directory to extract to.
    """
    archive_path = str(Path(archive_path).expanduser().resolve())
    source_path = str(Path(source_path).expanduser().resolve())

    try:
        if action == "zip":
            if not os.path.exists(source_path):
                return f"Error: Source path '{source_path}' does not exist."
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                if os.path.isdir(source_path):
                    for root, _, files in os.walk(source_path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, source_path)
                            zipf.write(full_path, rel_path)
                else:
                    zipf.write(source_path, os.path.basename(source_path))
            return f"Successfully created ZIP archive: {archive_path}"

        elif action == "unzip":
            if not os.path.exists(archive_path):
                return f"Error: Archive '{archive_path}' does not exist."
            os.makedirs(source_path, exist_ok=True)
            with zipfile.ZipFile(archive_path, "r") as zipf:
                zipf.extractall(source_path)
            return f"Successfully extracted ZIP archive to: {source_path}"

        elif action == "tar":
            if not os.path.exists(source_path):
                return f"Error: Source path '{source_path}' does not exist."
            with tarfile.open(archive_path, "w:gz") as tarf:
                if os.path.isdir(source_path):
                    tarf.add(source_path, arcname=os.path.basename(source_path))
                else:
                    tarf.add(source_path, arcname=os.path.basename(source_path))
            return f"Successfully created TAR archive: {archive_path}"

        elif action == "untar":
            if not os.path.exists(archive_path):
                return f"Error: Archive '{archive_path}' does not exist."
            os.makedirs(source_path, exist_ok=True)
            with tarfile.open(archive_path, "r:gz") as tarf:
                tarf.extractall(source_path)
            return f"Successfully extracted TAR archive to: {source_path}"

        else:
            return f"Unknown archive action: {action}"
    except Exception as e:
        return f"Archive operation failed: {e}"

TOOL_SCHEMAS_ARCHIVER = [
    {
        "type": "function",
        "function": {
            "name": "archive_files",
            "description": "Compress or extract files using ZIP or Gzipped TAR archives.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["zip", "unzip", "tar", "untar"],
                        "description": "The action to perform: zip, unzip, tar, untar"
                    },
                    "archive_path": {
                        "type": "string",
                        "description": "Path to the archive file (e.g. workspace/archive.zip)."
                    },
                    "source_path": {
                        "type": "string",
                        "description": "Path to compress (folder/file) or directory to extract into."
                    }
                },
                "required": ["action", "archive_path", "source_path"]
            }
        }
    }
]
