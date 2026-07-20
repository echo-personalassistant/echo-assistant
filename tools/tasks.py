"""
Task/TODO tracker tool.

Persists tasks to tasks.json in the project root so they survive restarts.
The agent can manage tasks via these tool calls; the TUI sidebar reads the
same file and refreshes after each agent reply.
"""

from __future__ import annotations

import json
from pathlib import Path

_TASKS_FILE = Path(__file__).parent.parent / "tasks.json"


def _load() -> list[dict]:
    if _TASKS_FILE.exists():
        try:
            return json.loads(_TASKS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save(tasks: list[dict]) -> None:
    _TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")


def _next_id(tasks: list[dict]) -> int:
    return max((t["id"] for t in tasks), default=0) + 1


# ── Public functions ──────────────────────────────────────────────────────────

def add_task(text: str) -> str:
    """
    Add a new task to the TODO list.

    Args:
        text: Task description.

    Returns:
        Confirmation with the new task ID.
    """
    tasks = _load()
    new_id = _next_id(tasks)
    tasks.append({"id": new_id, "text": text.strip(), "done": False})
    _save(tasks)
    return f"Task #{new_id} added: {text.strip()}"


def log_completed_action(text: str) -> None:
    """
    Directly log a completed action to tasks.json.
    """
    tasks = _load()
    new_id = _next_id(tasks)
    tasks.append({"id": new_id, "text": text.strip(), "done": True})
    _save(tasks)



def complete_task(task_id: int) -> str:
    """
    Mark a task as completed.

    Args:
        task_id: The numeric ID of the task to mark done.

    Returns:
        Confirmation message.
    """
    tasks = _load()
    for t in tasks:
        if t["id"] == int(task_id):
            t["done"] = True
            _save(tasks)
            return f"Task #{task_id} marked as done."
    return f"Task #{task_id} not found."


def remove_task(task_id: int) -> str:
    """
    Remove a task from the list.

    Args:
        task_id: The numeric ID of the task to delete.

    Returns:
        Confirmation message.
    """
    tasks = _load()
    original_len = len(tasks)
    tasks = [t for t in tasks if t["id"] != int(task_id)]
    if len(tasks) == original_len:
        return f"Task #{task_id} not found."
    _save(tasks)
    return f"Task #{task_id} removed."


def list_tasks() -> str:
    """
    List all current tasks.

    Returns:
        A formatted text list of tasks with their IDs and status.
    """
    tasks = _load()
    if not tasks:
        return "No tasks."
    lines = []
    for t in tasks:
        status = "[x]" if t["done"] else "[ ]"
        lines.append(f"{status} #{t['id']} {t['text']}")
    return "\n".join(lines)


# ── Tool schemas ──────────────────────────────────────────────────────────────

TOOL_SCHEMAS_TASKS = [
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a new task or TODO item to the task list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Task description."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as completed by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "Task ID to mark done."},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_task",
            "description": "Delete a task from the list by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "Task ID to remove."},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Return the current task list with IDs and completion status.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]
