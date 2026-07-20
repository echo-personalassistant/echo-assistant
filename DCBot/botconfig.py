import os
from pathlib import Path

# Helper to safely parse channel and role IDs, even if configured incorrectly
def _get_env_id(key: str, default_val: str = "0") -> int:
    # If the key itself is a raw digit (user pasted the ID directly in the getenv call)
    if key.isdigit():
        return int(key)
    
    val = os.getenv(key, default_val)
    # If getenv returned None or isn't a digit, fallback to default_val
    if not val or not str(val).isdigit():
        val = default_val
        
    return int(val)

# ── Discord Bot Configuration ──
# Token can be set via environment variable or in a file: credentials/discord_token.txt
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
token_file = Path(__file__).parent.parent / "credentials" / "discord_token.txt"
if not DISCORD_TOKEN and token_file.exists():
    try:
        DISCORD_TOKEN = token_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass

# Discord Server (Guild) Feature IDs
# Replace these with your actual Channel/Role IDs in your Discord Server
DISCORD_VERIFY_CHANNEL_ID = _get_env_id("1526302526616506368")
DISCORD_MEMBER_ROLE_ID = _get_env_id("1526302928649060383")
DISCORD_WELCOME_CHANNEL_ID = _get_env_id("1526302902610690180")
DISCORD_SUGGESTIONS_CHANNEL_ID = _get_env_id("1526307382156857495")
DISCORD_GUILD_ID = _get_env_id("1526297619553583165")
