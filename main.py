import sys
from pathlib import Path

# Automatically inject the virtual environment's site-packages so that running
# with global Python ('py main.py') resolves installed dependencies (like discord.py) successfully.
venv_site_packages = Path(__file__).parent / ".venv" / "Lib" / "site-packages"
if venv_site_packages.exists() and str(venv_site_packages) not in sys.path:
    sys.path.insert(0, str(venv_site_packages))

from ui.app import AssistantApp

if __name__ == "__main__":
    AssistantApp().run()