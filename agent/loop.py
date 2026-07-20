import os
import json
import uuid
import ollama
from pathlib import Path
from agent.prompts import SYSTEM_PROMPT
from tools.files import read_file, write_file, list_dir, TOOL_SCHEMAS_FILES
from tools.shell import run_shell, TOOL_SCHEMAS_SHELL
from tools.tasks import (
    add_task, complete_task, remove_task, list_tasks, log_completed_action,
    TOOL_SCHEMAS_TASKS,
)
from tools.archiver import archive_files, TOOL_SCHEMAS_ARCHIVER
from tools.search import search_file_content, TOOL_SCHEMAS_SEARCH
from config import (
    MODEL,
    ENABLE_WEB_SEARCH,
    ENABLE_GMAIL_DRAFT,
    ENABLE_RAG,
    ENABLE_READ_CLIPBOARD,
    GITHUB_TOKEN,
)

# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS = TOOL_SCHEMAS_FILES + TOOL_SCHEMAS_SHELL + TOOL_SCHEMAS_TASKS + TOOL_SCHEMAS_ARCHIVER + TOOL_SCHEMAS_SEARCH

TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "run_shell": run_shell,
    "add_task": add_task,
    "complete_task": complete_task,
    "remove_task": remove_task,
    "list_tasks": list_tasks,
    "archive_files": archive_files,
    "search_file_content": search_file_content,
}

if ENABLE_WEB_SEARCH:
    from tools.web_search import ddg_search, fetch_page_text, TOOL_SCHEMAS_WEB_SEARCH
    TOOLS += TOOL_SCHEMAS_WEB_SEARCH
    TOOL_FUNCTIONS["ddg_search"] = ddg_search
    TOOL_FUNCTIONS["fetch_page_text"] = fetch_page_text

if ENABLE_GMAIL_DRAFT:
    from tools.gmail import draft_email, TOOL_SCHEMAS_GMAIL
    TOOLS += TOOL_SCHEMAS_GMAIL
    TOOL_FUNCTIONS["draft_email"] = draft_email

if GITHUB_TOKEN:
    from tools.github_tool import gh_list_prs, gh_create_issue, gh_list_repos, TOOL_SCHEMAS_GITHUB
    TOOLS += TOOL_SCHEMAS_GITHUB
    TOOL_FUNCTIONS["gh_list_prs"] = gh_list_prs
    TOOL_FUNCTIONS["gh_create_issue"] = gh_create_issue
    TOOL_FUNCTIONS["gh_list_repos"] = gh_list_repos

if ENABLE_READ_BOARD := ENABLE_READ_CLIPBOARD:
    from tools.clipboard import read_clipboard, TOOL_SCHEMAS_CLIPBOARD
    TOOLS += TOOL_SCHEMAS_CLIPBOARD
    TOOL_FUNCTIONS["read_clipboard"] = read_clipboard


def _log_tool_as_completed_task(name: str, args: dict) -> None:
    """Helper to log successful tool execution to tasks.json as a completed task."""
    try:
        desc = ""
        if name == "draft_email":
            to = args.get("to", "")
            subject = args.get("subject", "")
            desc = f"Drafted email to {to}" + (f" regarding '{subject}'" if subject else "")
        elif name == "ddg_search":
            query = args.get("query", "")
            desc = f"Searched web for '{query}'"
        elif name == "fetch_page_text":
            url = args.get("url", "")
            desc = f"Fetched webpage content from {url}"
        elif name == "gh_list_prs":
            repo = args.get("repo", "")
            desc = f"Listed GitHub pull requests in {repo}"
        elif name == "gh_create_issue":
            repo = args.get("repo", "")
            title = args.get("title", "")
            desc = f"Created GitHub issue in {repo}: '{title}'"
        elif name == "gh_list_repos":
            org = args.get("org", "")
            desc = f"Listed GitHub repos" + (f" for org {org}" if org else "")
        elif name == "run_shell":
            command = args.get("command", "")
            desc = f"Executed shell command: {command}"
        elif name == "write_file":
            path = args.get("path", "")
            desc = f"Wrote file {path}"
        elif name == "read_file":
            path = args.get("path", "")
            desc = f"Read file {path}"
        elif name == "list_dir":
            path = args.get("path", ".")
            desc = f"Listed contents of directory: {path}"
        elif name == "read_clipboard":
            desc = "Read text from system clipboard"
        elif name == "archive_files":
            action = args.get("action", "")
            archive_path = args.get("archive_path", "")
            desc = f"Performed {action} archive on: {os.path.basename(archive_path)}"
        elif name == "search_file_content":
            query = args.get("query", "")
            desc = f"Searched file contents for: '{query}'"
        
        if desc:
            log_completed_action(desc)
    except Exception:
        pass


# ── Agent ─────────────────────────────────────────────────────────────────────

class Agent:
    def __init__(self):
        self.history_file = Path(__file__).parent.parent / "sessions" / "history.json"
        self.history_file.parent.mkdir(exist_ok=True, parents=True)
        self.history = self._load_session_history()
        
        self.memory = None
        if ENABLE_RAG:
            try:
                from memory.store import ConversationMemory
                self.memory = ConversationMemory()
            except Exception:
                pass

    def _load_session_history(self) -> list[dict]:
        """Loads previous conversation history if file exists, else uses default system prompt."""
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return [{"role": "system", "content": SYSTEM_PROMPT}]

    def _save_session_history(self) -> None:
        """Saves current conversation history to disk."""
        try:
            self.history_file.write_text(json.dumps(self.history, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def clear_session_history(self) -> None:
        """Clears session log file and resets agent state."""
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._save_session_history()

    def warmup(self) -> None:
        """Load the model into memory before the first user message."""
        ollama.chat(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + [{"role": "user", "content": "hi"}],
        )

    def send(self, user_message: str) -> str:
        # If RAG is enabled, retrieve context and insert as a temporary system message context
        temp_history = list(self.history)
        if ENABLE_RAG and self.memory:
            past_memories = self.memory.retrieve(user_message)
            if past_memories:
                temp_history.insert(1, {"role": "system", "content": past_memories})

        self.history.append({"role": "user", "content": user_message})
        temp_history.append({"role": "user", "content": user_message})
        self._save_session_history()

        shell_retry_count = 0
        max_shell_retries = 2

        while True:
            response = ollama.chat(
                model=MODEL,
                messages=temp_history,
                tools=TOOLS,
            )
            msg = response["message"]
            self.history.append(msg)
            temp_history.append(msg)
            self._save_session_history()

            if not msg.get("tool_calls"):
                reply_content = msg["content"]
                # Save conversation to RAG memory after completion
                if ENABLE_RAG and self.memory:
                    try:
                        self.memory.store(user_message, reply_content, str(uuid.uuid4()))
                    except Exception:
                        pass
                return reply_content

            for call in msg["tool_calls"]:
                fn_name = call["function"]["name"]
                fn_args = call["function"]["arguments"]
                fn = TOOL_FUNCTIONS.get(fn_name)
                
                # Execute tool
                try:
                    result = fn(**fn_args) if fn else f"Unknown tool: {fn_name}"
                except Exception as e:
                    result = f"Error executing tool {fn_name}: {e}"

                # Automatic Diagnostic / Self-Correction for run_shell errors
                if fn_name == "run_shell" and shell_retry_count < max_shell_retries:
                    # Capture common shell failure signals
                    result_str = str(result)
                    is_error = any(sig in result_str for sig in [
                        "Error:", "command not found", "is not recognized",
                        "cannot find the path", "failed with exit code",
                        "Permission denied", "Access is denied"
                    ]) or ("stderr" in result_str and len(result_str.strip()) < 50)
                    
                    if is_error:
                        shell_retry_count += 1
                        # Force prompt injection advising the model of the command error, prompting diagnostic correction.
                        result = (
                            f"{result}\n\n[SYSTEM NOTICE] The command failed. "
                            "Please analyze the stdout/stderr, correct your command arguments or approach, "
                            "and try running it again automatically."
                        )

                # If successful execution (didn't raise exception or require confirmation), log completed task
                if "CONFIRMATION_REQUIRED" not in str(result) and "[SYSTEM NOTICE]" not in str(result):
                    _log_tool_as_completed_task(fn_name, fn_args)

                self.history.append({
                    "role": "tool",
                    "content": str(result),
                })
                temp_history.append({
                    "role": "tool",
                    "content": str(result),
                })
                self._save_session_history()