import subprocess

CONFIRM_REQUIRED = True  # keep this True until you fully trust the setup

def run_shell(command: str, confirmed: bool = False) -> str:
    if CONFIRM_REQUIRED and not confirmed:
        return (
            f"CONFIRMATION_REQUIRED: about to run `{command}`. "
            "Ask the user to confirm before calling this tool again with confirmed=true."
        )
    result = subprocess.run(
        command, shell=True, capture_output=True, encoding="utf-8", errors="replace", timeout=30
    )
    return result.stdout + result.stderr

TOOL_SCHEMAS_SHELL = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command on the user's machine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["command"],
            },
        },
    },
]