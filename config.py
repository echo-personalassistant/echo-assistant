import os
from pathlib import Path

MODEL = "qwen3:8b"
OLLAMA_HOST = "http://localhost:11434"
CONFIRM_SHELL_COMMANDS = True


# ── Feature flags ─────────────────────────────────────────────────────────────
# Set to True to enable the corresponding feature.

# DuckDuckGo HTML scraping — lets the agent search the web and read page text.
ENABLE_WEB_SEARCH = False

# Rich Syntax-highlighted code blocks in the conversation log.
ENABLE_SYNTAX_HIGHLIGHT = True

# Draft emails via Gmail compose URL (opens in default browser, no API key needed).
ENABLE_GMAIL_DRAFT = True

# Conversation memory / RAG — embeds past exchanges using ChromaDB
ENABLE_RAG = True
EMBEDDING_MODEL = "nomic-embed-text"

# Clipboard tool configuration — lets the agent read clipboard contents
ENABLE_READ_CLIPBOARD = True

# GitHub REST API Token — leave empty to disable GitHub tools
GITHUB_TOKEN = ""