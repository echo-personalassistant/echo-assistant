# $echo

$echo is a terminal-first personal AI assistant built for developer productivity, local automation, and command-line workflows. It integrates a local large language model (LLM) with a Textual-based terminal user interface (TUI) and a Discord bot for remote server management.

## Core Capabilities

| Capability | Description | Components |
| --- | --- | --- |
| Local AI Engine | Qwen-based intelligence executing commands and answer inquiries entirely on-device. | Ollama, agent/loop.py |
| Terminal Dashboard | High-performance interactive UI showing session logs, system uptime, and runtime controls. | Textual, ui/app.py |
| Workspace Automation | Safe, validated tools to read/write files and check directories. | tools/files.py |
| Command Execution | Execute local bash/powershell scripts with built-in confirmation safety gates. | tools/shell.py |
| Discord Integration | Remote sync bot mapping Discord commands and verification states to the local assistant. | DCBot/bot.py |

<details>
<summary>Installation and Setup</summary>

### Prerequisites

Before starting, ensure you have the following installed:
* Python 3.11 or higher
* Ollama local LLM runner
* Git

### Step-by-Step Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/echo-personalassistant/echo-assistant
   cd echo-assistant
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```

3. Activate the virtual environment:
   * Windows:
     ```powershell
     .venv\Scripts\activate
     ```
   * Linux/macOS:
     ```bash
     source .venv/bin/activate
     ```

4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Install and pull the default model in Ollama:
   ```bash
   ollama pull qwen3:8b
   ```
</details>

<details>
<summary>Configuration</summary>

### System Configuration
Modify config.py to adjust assistant properties:
* `MODEL`: The local LLM name (defaults to qwen3:8b).
* `OLLAMA_HOST`: The connection URI for the local Ollama instance.
* `CONFIRM_SHELL_COMMANDS`: Set to True to ensure the agent asks for authorization before executing command line actions.

### Discord Bot Configuration
To use the optional Discord bot integration:
1. Create a bot application on the Discord Developer Portal.
2. Retrieve the Bot Token and save it inside `credentials/discord_token.txt` or export it as an environment variable named `DISCORD_TOKEN`.
3. Configure the specific server Guild ID, Welcome Channel ID, Suggestions Channel ID, and Role IDs inside `DCBot/botconfig.py`.
</details>

<details>
<summary>Running the Assistant</summary>

### Start Terminal TUI Dashboard
To run the full dark-mode graphical terminal interface:
```bash
python main.py
```

### Start Simple Terminal Loop
To run a lightweight interactive command line loop without the full graphical dashboard:
```bash
python ui/main.py
```
</details>

## Discord Bot Command Reference

The background Discord bot handles remote integrations. Admins and users can run these slash commands:

| Command | Description | Target Users |
| --- | --- | --- |
| `/uptime` | Displays the current uptime duration of the active assistant session. | All Users |
| `/info` | Displays detailed statistics, system stack info, and project repository targets. | All Users |
| `/owner` | Shows information about Josh, the creator, and the design philosophy of the project. | All Users |
| `/docs` | Link to user guides, tutorials, and wiki pages. | All Users |
| `/features` | Lists active assistant modules and the upcoming development roadmap. | All Users |
| `/invite` | Generates a secure authorization URL to invite the bot to external servers. | All Users |
| `/verify` | Sends a message with a button allowing joining members to verify and gain roles. | Administrators |
| `/suggestions` | Opens a UI modal to submit feedback that logs directly to the local TUI screen. | Direct Messages Only |

## Safety and Privacy

All operations executed by $echo run locally on your hardware. Files are not uploaded, and prompt parsing stays offline. To prevent unauthorized actions, the safety gate enforces explicit user confirmation before writing files, running system modification scripts, or making external calls.
