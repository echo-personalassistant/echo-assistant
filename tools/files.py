from pathlib import Path

def read_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"Error: {path} does not exist."
    return p.read_text(encoding="utf-8", errors="replace")

def write_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {path}."

def list_dir(path: str = ".") -> str:
    p = Path(path).expanduser()
    entries = [e.name for e in p.iterdir()]
    return "\n".join(entries) if entries else "(empty)"

TOOL_SCHEMAS_FILES = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a text file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file, overwriting it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        },
    },
]