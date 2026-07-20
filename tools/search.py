import os
import re
from pathlib import Path

def search_file_content(query: str, root_dir: str = ".", file_pattern: str = "") -> str:
    """
    Search for a text query or regex pattern within text files in the workspace (ignoring binary/hidden directories).

    Args:
        query: Literal text string or regex pattern to search for.
        root_dir: Directory path to begin search (defaults to current directory).
        file_pattern: Optional file extension filter, e.g. '.py' or '.md'.
    """
    root_path = Path(root_dir).expanduser().resolve()
    if not root_path.exists():
        return f"Error: Root directory '{root_dir}' does not exist."

    ignored_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build"}
    matches = []
    max_matches = 100

    try:
        matcher = re.compile(query, re.IGNORECASE)
    except re.error as e:
        # Fall back to literal text search if regex syntax is invalid
        matcher = re.compile(re.escape(query), re.IGNORECASE)

    try:
        for root, dirs, files in os.walk(root_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]

            for file in files:
                if file.startswith("."):
                    continue
                if file_pattern and not file.endswith(file_pattern):
                    continue

                full_path = Path(root) / file
                
                # Basic check to avoid reading large binary files
                if full_path.stat().st_size > 1024 * 1024:  # > 1MB
                    continue

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if matcher.search(line):
                                rel_path = os.path.relpath(full_path, root_path)
                                matches.append(f"{rel_path}:{line_num}: {line.strip()}")
                                if len(matches) >= max_matches:
                                    break
                except Exception:
                    pass

                if len(matches) >= max_matches:
                    break
            if len(matches) >= max_matches:
                break
    except Exception as e:
        return f"Search execution failed: {e}"

    if not matches:
        return f"No occurrences of '{query}' found."
    
    count = len(matches)
    truncated = "\n[Truncated: displaying top 100 results]" if count >= max_matches else ""
    return f"Search matches ({count} total):\n" + "\n".join(matches) + truncated

TOOL_SCHEMAS_SEARCH = [
    {
        "type": "function",
        "function": {
            "name": "search_file_content",
            "description": "Search for query matches within files inside the workspace (ignores binary, node_modules, and git dirs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Literal text query or regex pattern."
                    },
                    "root_dir": {
                        "type": "string",
                        "description": "Starting directory. Defaults to current workspace directory."
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Filter by extension (e.g. '.py' or '.md')."
                    }
                },
                "required": ["query"]
            }
        }
    }
]
