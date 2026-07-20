import tkinter as tk
from config import ENABLE_READ_CLIPBOARD

def read_clipboard() -> str:
    """
    Read the current text contents from the user's system clipboard.
    Useful for reviewing copied code snippets or error stack traces.
    """
    if not ENABLE_READ_CLIPBOARD:
        return "Error: Clipboard reading is disabled in config.py"
    try:
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        if not text:
            return "Clipboard is empty or does not contain text."
        return f"Clipboard Content:\n{text}"
    except Exception as e:
        return f"Error reading clipboard: {e}"

TOOL_SCHEMAS_CLIPBOARD = [
    {
        "type": "function",
        "function": {
            "name": "read_clipboard",
            "description": "Read the text contents from the user's system clipboard.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]
