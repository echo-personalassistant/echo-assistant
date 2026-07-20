import os
import re
import subprocess
from pathlib import Path

def git_check_conflicts(directory: str = ".") -> str:
    """
    Scan files in the workspace directory for active Git merge conflict markers (<<<<<<<, =======, >>>>>>>).
    Returns a detailed list of files and lines where conflicts are present.
    """
    root_path = Path(directory).expanduser().resolve()
    if not root_path.exists():
        return f"Error: Directory '{directory}' does not exist."

    conflict_files = []
    
    # Try running git diff command to check status first
    try:
        res = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=root_path, capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            unmerged = [f.strip() for f in res.stdout.splitlines() if f.strip()]
            for rel_file in unmerged:
                full_path = root_path / rel_file
                if full_path.exists():
                    conflict_files.append(full_path)
    except Exception:
        pass

    # If git command failed or not in git repo, fall back to checking text files manually
    if not conflict_files:
        ignored_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build"}
        try:
            for root, dirs, files in os.walk(root_path):
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
                for file in files:
                    full_path = Path(root) / file
                    if full_path.suffix in (".py", ".txt", ".md", ".json", ".js", ".ts", ".yml", ".yaml"):
                        conflict_files.append(full_path)
        except Exception:
            pass

    report = []
    conflict_marker_re = re.compile(r"^(<<<<<<<|=======|>>>>>>>)")

    for path in conflict_files:
        try:
            if path.stat().st_size > 500 * 1024:  # Skip files > 500KB
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                markers = []
                for line_num, line in enumerate(f, 1):
                    if conflict_marker_re.match(line):
                        markers.append(f"Line {line_num}: {line.strip()}")
                
                if markers:
                    rel_path = os.path.relpath(path, root_path)
                    report.append(f"File: {rel_path}\n" + "\n".join(f"  {m}" for m in markers))
        except Exception:
            pass

    if not report:
        return "No Git merge conflict markers detected in the workspace."

    return "Git Conflict Report:\n\n" + "\n\n".join(report)

def git_resolve_conflict_marker(file_path: str, resolution: str) -> str:
    """
    Resolve active merge conflicts in a file by selecting either 'ours', 'theirs', or 'both'.

    Args:
        file_path: Path to the conflict file.
        resolution: 'ours' (keep current changes), 'theirs' (keep incoming changes), or 'both' (keep both).
    """
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        return f"Error: File '{file_path}' does not exist."

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file: {e}"

    new_lines = []
    in_conflict = False
    ours_buf = []
    theirs_buf = []
    mode = None  # 'ours' or 'theirs'

    for line in lines:
        if line.startswith("<<<<<<<"):
            in_conflict = True
            ours_buf = []
            theirs_buf = []
            mode = "ours"
        elif line.startswith("======="):
            mode = "theirs"
        elif line.startswith(">>>>>>>"):
            in_conflict = False
            # Resolve conflict block
            if resolution == "ours":
                new_lines.extend(ours_buf)
            elif resolution == "theirs":
                new_lines.extend(theirs_buf)
            elif resolution == "both":
                new_lines.extend(ours_buf)
                new_lines.extend(theirs_buf)
            else:
                return f"Error: Invalid resolution value '{resolution}'. Use 'ours', 'theirs', or 'both'."
            mode = None
        else:
            if in_conflict:
                if mode == "ours":
                    ours_buf.append(line)
                elif mode == "theirs":
                    theirs_buf.append(line)
            else:
                new_lines.append(line)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return f"Successfully resolved conflicts in '{file_path}' selecting '{resolution}'."
    except Exception as e:
        return f"Error writing resolved file: {e}"

TOOL_SCHEMAS_GIT_HELPER = [
    {
        "type": "function",
        "function": {
            "name": "git_check_conflicts",
            "description": "Scan the workspace directory for active Git merge conflict markers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Starting directory path. Defaults to workspace root."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_resolve_conflict_marker",
            "description": "Resolve conflict blocks in a file using a strategy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the conflict file."},
                    "resolution": {
                        "type": "string",
                        "enum": ["ours", "theirs", "both"],
                        "description": "Resolution strategy: 'ours' (keep HEAD changes), 'theirs' (keep incoming), or 'both'."
                    }
                },
                "required": ["file_path", "resolution"]
            }
        }
    }
]
