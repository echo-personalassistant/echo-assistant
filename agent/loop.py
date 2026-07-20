import ollama
from agent.prompts import SYSTEM_PROMPT
from tools.files import read_file, write_file, list_dir, TOOL_SCHEMAS_FILES
from tools.shell import run_shell, TOOL_SCHEMAS_SHELL
from config import MODEL

TOOLS = TOOL_SCHEMAS_FILES + TOOL_SCHEMAS_SHELL

TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "run_shell": run_shell,
}

class Agent:
    def __init__(self):
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def warmup(self) -> None:
        """Load the model into memory before the first user message.
        Sends a minimal request using the system prompt only — does not
        affect conversation history."""
        ollama.chat(
            model=MODEL,
            messages=self.history + [{"role": "user", "content": "hi"}],
        )

    def send(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        while True:
            response = ollama.chat(
                model=MODEL,
                messages=self.history,
                tools=TOOLS,
            )
            msg = response["message"]
            self.history.append(msg)

            if not msg.get("tool_calls"):
                return msg["content"]

            for call in msg["tool_calls"]:
                fn_name = call["function"]["name"]
                fn_args = call["function"]["arguments"]
                fn = TOOL_FUNCTIONS.get(fn_name)
                result = fn(**fn_args) if fn else f"Unknown tool: {fn_name}"

                self.history.append({
                    "role": "tool",
                    "content": str(result),
                })