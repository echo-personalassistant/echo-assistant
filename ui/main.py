from rich import print, box, text
from rich.panel import Panel
from rich.text import Text
from rich.console import Console
from rich.prompt import Prompt
import readline
import functools

console = Console()

# Persistent command history
readline.read_history_file("history.txt")
readline.set_history_length(1000)

# Help system
def show_help():
    help_text = """
    [bold]Available commands:[/bold]
    - [cyan]help[/cyan]: Show this help menu
    - [cyan]exit[/cyan]: Quit the application
    - [cyan]secure[/cyan]: Toggle secure mode
    
    [bold]Keybindings:[/bold]
    - [cyan]SHIFT+Enter[/cyan]: New line in input
    - [cyan]CTRL+D[/cyan]: Exit
    
    [bold]System info:[/bold]
    Python: 3.11.5
    rich: 15.0.0
    """
    console.print(Panel(help_text, title="[bold]Terminal UI[/bold]", border_style="blue", box=box.ROUNDED))

# Smart completion
def complete(text):
    # Add tab completion logic here
    return text

# Performance optimized command execution
@functools.lru_cache(maxsize=128)
def execute_command(cmd):
    # Your command execution logic here
    return f"Executed: {cmd}"

# Secure mode flag
def secure_mode():
    return os.getenv("ECHO_SECURE") == "1"

# Main UI loop
def render_ui():
    while True:
        console.clear()
        console.print(Panel("[bold]Terminal UI[/bold]", border_style="blue", box=box.ROUNDED))
        user_input = Prompt.ask("[bold]Enter your message[/bold] (SHIFT+Enter for new line)", default="")
        if user_input == "help":
            show_help()
        elif user_input == "exit":
            break
        elif user_input == "secure":
            os.environ["ECHO_SECURE"] = "1" if "ECHO_SECURE" not in os.environ else "0"
        else:
            if not secure_mode():
                result = execute_command(user_input)
                console.print(f"[green]{result}[/green]")
            else:
                console.print("[red]Secure mode enabled. Command execution disabled.[/red]")

if __name__ == "__main__":
    render_ui()