from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.strip import Strip
from textual.widgets import Footer, Header, Label, RichLog, Static, TextArea

from agent.loop import Agent
from config import ENABLE_SYNTAX_HIGHLIGHT

# ── Large ASCII Logo ──────────────────────────────────────────────────────────
ECHO_ASCII = """
███████  ██████  ██   ██  ██████  
██      ██      ██   ██ ██    ██ 
█████   ██      ███████ ██    ██ 
██      ██      ██   ██ ██    ██ 
███████  ██████ ██   ██  ██████  
"""

# Note: The logo above uses forward slashes (/) which do not need escaping. 
# However, Textual Static widgets process brackets like '[/]' as markup tags.
# To prevent Textual from parsing '/_' and '/]' sequences as BBCode tags,
# we turn off markup parsing for the logo widget or escape it.


SIDEBAR_WIDTH = 36
DIVIDER_WIDTH = 28
_TASKS_FILE = Path(__file__).parent.parent / "tasks.json"


# ── Markdown Parser & Custom Widgets ──────────────────────────────────────────

def parse_markdown_to_text(s: str, default_style: str = "") -> Text:
    result = Text()
    i = 0
    n = len(s)
    bold = False
    italic = False
    while i < n:
        if s[i] == '`':
            j = s.find('`', i + 1)
            if j != -1:
                code_text = s[i+1:j]
                result.append(code_text, style="bold #FFAC47")
                i = j + 1
                continue
        if i + 1 < n and s[i:i+2] in ('**', '__'):
            bold = not bold
            i += 2
            continue
        if s[i] in ('*', '_'):
            italic = not italic
            i += 1
            continue
        styles = []
        if bold:
            styles.append("bold")
        if italic:
            styles.append("italic")
        if default_style:
            styles.append(default_style)
        style_str = " ".join(styles) if styles else None
        result.append(s[i], style=style_str)
        i += 1
    return result


def render_reply_to_log(reply: str, log: MessageRichLog) -> None:
    parts = reply.split("```")
    for idx, part in enumerate(parts):
        if idx % 2 == 0:
            if not part:
                continue
            log.write(parse_markdown_to_text(part, default_style="#F3F3F3"))
        else:
            lines = part.split("\n", 1)
            lang = lines[0].strip() if lines else ""
            code = lines[1] if len(lines) > 1 else ""

            if ENABLE_SYNTAX_HIGHLIGHT and code.strip():
                lang_map = {
                    "py": "python", "js": "javascript", "ts": "typescript",
                    "sh": "bash", "shell": "bash", "zsh": "bash",
                    "yml": "yaml", "dockerfile": "docker",
                }
                resolved = lang_map.get(lang.lower(), lang.lower()) if lang else "text"
                syntax = Syntax(
                    code.rstrip(),
                    resolved or "text",
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                    padding=(0, 2),
                )
                log.write(syntax)
            else:
                log.write(Text(part, style="bold #FFAC47"))


class MessageTextArea(TextArea):
    """A customized TextArea that handles Shift+Enter for newlines and Enter for submission."""

    class Submitted(Message):
        def __init__(self, text_area: MessageTextArea) -> None:
            super().__init__()
            self.text_area = text_area
            self.value = text_area.text

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("compact", True)
        kwargs.setdefault("show_line_numbers", False)
        kwargs.setdefault("highlight_cursor_line", False)
        kwargs.setdefault("soft_wrap", True)
        super().__init__(*args, **kwargs)
        self.show_horizontal_scrollbar = False

    def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self))
        elif event.key in ("shift+enter", "ctrl+enter", "ctrl+j"):
            event.prevent_default()
            event.stop()
            self.insert("\n")
        else:
            super()._on_key(event)

    def _on_mouse_up(self, event: events.MouseEvent) -> None:
        super()._on_mouse_up(event)
        selected = self.selected_text
        if selected:
            self.app.copy_to_clipboard(selected)
            self.app.notify("Copied to clipboard", timeout=2.0)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        num_lines = self.document.line_count
        self.styles.height = min(10, max(1, num_lines))
        # Fire autocomplete check event to the main app
        self.app.post_message(AutocompleteCheck(self.text))


# ── Custom Messages ───────────────────────────────────────────────────────────

class AutocompleteCheck(Message):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


# ── Suggestion Panel ──────────────────────────────────────────────────────────

class SuggestionPanel(Static):
    """A small suggestions block showing available commands when user starts typing '/'."""

    def on_mount(self) -> None:
        self.display = False

    def update_suggestions(self, text: str) -> None:
        if text.startswith("/") and " " not in text:
            commands = [
                "/clear - Clear the log window",
                "/quit - Exit echo assistant",
                "/toggle-sidebar - Collapse/expand the sidebar panel (Ctrl+B)",
                "/history - Clear the conversation session history log"
            ]
            typed = text.lower()
            filtered = [c for c in commands if c.startswith(typed)]
            if filtered:
                block = Text("Available commands:\n", style="bold #8BFF7A")
                for c in filtered:
                    block.append(f"  {c}\n", style="#F3F3F3")
                self.update(block)
                self.display = True
                return
        self.display = False


# ── Toast Notifications Panel ──────────────────────────────────────────────────

class ToastContainer(Static):
    """Temporary notification panel displaying action notifications that fade out."""

    def on_mount(self) -> None:
        self.display = False

    def trigger_toast(self, text: str) -> None:
        self.update(Text(f" \u2713 {text} ", style="bold #0D0D0D bgcolor=#8BFF7A"))
        self.display = True
        self.set_timer(3.0, self.hide_toast)

    def hide_toast(self) -> None:
        self.display = False


# ── Task Panel ────────────────────────────────────────────────────────────────

class TaskPanel(Static):
    """Sidebar panel that displays the logged tasks/actions executed by the AI."""

    def on_mount(self) -> None:
        self.refresh_tasks()

    def refresh_tasks(self) -> None:
        if _TASKS_FILE.exists():
            try:
                tasks: list[dict] = json.loads(_TASKS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                tasks = []
        else:
            tasks = []

        completed_tasks = [t for t in tasks if t.get("done", False)]

        if not completed_tasks:
            t = Text("  no actions logged yet", style="dim #444444")
            self.update(t)
            return

        block = Text()
        # Limit display to top 8 completed actions to avoid scrollbars
        for task in completed_tasks[-8:]:
            text = task.get("text", "")
            block.append("  \u2713 ", style="#8BFF7A")
            block.append(text + "\n", style="#D0D0D0")

        self.update(block)


# ── Sidebar ───────────────────────────────────────────────────────────────────

class Sidebar(Static):
    """Right-hand info/stats panel."""

    messages_sent: reactive[int] = reactive(0)
    _start_time: datetime

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._start_time = datetime.now()

    def compose(self) -> ComposeResult:
        yield Static(id="sb-logo")
        yield Static(id="sb-divider-1")
        yield Static(id="sb-section-label-stats")
        yield Static(id="sb-stats")
        yield Static(id="sb-divider-2")
        yield Static(id="sb-section-label-keys")
        yield Static(id="sb-keys")
        yield Static(id="sb-divider-3")
        yield Static(id="sb-section-label-tasks")
        yield TaskPanel(id="sb-tasks")

    def on_mount(self) -> None:
        self._render_chrome()
        self._render_stats()
        self._render_keys()
        self.set_interval(1, self._render_stats)

    # ── renderers ─────────────────────────────────────────────────────────────

    def _render_chrome(self) -> None:
        lines = ECHO_ASCII.splitlines()
        logo = Text()
        for i, line in enumerate(lines):
            # Alternating shades of green for visual depth
            style = "bold #8BFF7A" if i % 2 == 0 else "bold #61D65A"
            logo.append(line, style=style)
            if i < len(lines) - 1:
                logo.append("\n")
        self.query_one("#sb-logo", Static).update(logo)

        for sid in ("#sb-divider-1", "#sb-divider-2", "#sb-divider-3"):
            self.query_one(sid, Static).update(Text("─" * DIVIDER_WIDTH, style="#232323"))

        self.query_one("#sb-section-label-stats", Static).update(
            Text("  STATS", style="dim #666666")
        )
        self.query_one("#sb-section-label-keys", Static).update(
            Text("  SHORTCUTS", style="dim #666666")
        )
        self.query_one("#sb-section-label-tasks", Static).update(
            Text("  COMPLETED TASKS", style="dim #666666")
        )

    def _kv_line(self, label: str, value: str, value_style: str = "#F3F3F3") -> Text:
        t = Text()
        t.append(f"  {label}", style="#666666")
        t.append(" " * max(1, 12 - len(label)))
        t.append(value, style=value_style)
        return t

    def _render_stats(self) -> None:
        from config import MODEL
        
        elapsed = datetime.now() - self._start_time
        h, rem = divmod(int(elapsed.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        uptime_str = f"{h:02d}:{m:02d}:{s:02d}"

        block = Text()
        block.append_text(self._kv_line("Model", MODEL))
        block.append("\n")
        block.append_text(self._kv_line("Messages", str(self.messages_sent), "#8BFF7A"))
        block.append("\n")
        block.append_text(self._kv_line("Uptime", uptime_str))
        
        self.query_one("#sb-stats", Static).update(block)

    def _render_keys(self) -> None:
        block = Text()
        block.append_text(self._kv_line("Enter", "Send"))
        block.append("\n")
        block.append_text(self._kv_line("Ctrl+B", "Sidebar"))
        block.append("\n")
        block.append_text(self._kv_line("Ctrl+L", "Clear"))
        block.append("\n")
        block.append_text(self._kv_line("Ctrl+C", "Quit"))
        self.query_one("#sb-keys", Static).update(block)

    def increment_messages(self) -> None:
        self.messages_sent += 1
        self._render_stats()

    def refresh_tasks(self) -> None:
        self.query_one("#sb-tasks", TaskPanel).refresh_tasks()


# ── Thinking indicator ────────────────────────────────────────────────────────

class ThinkingBar(Static):
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    _idx: int = 0
    _timer = None
    _label: str = "thinking..."

    def on_mount(self) -> None:
        self.display = False

    def start(self, label: str = "thinking...") -> None:
        self._label = label
        self._idx = 0
        self.display = True
        self._timer = self.set_interval(0.08, self._tick)

    def stop(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
        self.display = False
        self.update("")

    def _tick(self) -> None:
        f = self.FRAMES[self._idx % len(self.FRAMES)]
        self._idx += 1
        t = Text()
        t.append(f"  {f}  ", style="#8BFF7A")
        t.append(self._label, style="dim #666666")
        self.update(t)


# ── MessageRichLog Wrapper ────────────────────────────────────────────────────

class MessageRichLog(RichLog):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._drag_start = None
        self._drag_current = None
        self.show_horizontal_scrollbar = False

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:
            region = self.content_region
            content_x = int(event.screen_x - region.x) if event.screen_x is not None else int(event.x)
            content_y = int(event.screen_y - region.y) if event.screen_y is not None else int(event.y)

            line_index = int(content_y + self.scroll_y)
            if not self.lines:
                self._drag_start = None
                self._drag_current = None
                return

            line_index = max(0, min(len(self.lines) - 1, line_index))
            char_offset = max(0, min(len(self.lines[line_index].text), content_x))
            self._drag_start = (line_index, char_offset)
            self._drag_current = (line_index, char_offset)
            self.refresh()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if event.button == 1 and self._drag_start is not None:
            region = self.content_region
            content_x = int(event.screen_x - region.x) if event.screen_x is not None else int(event.x)
            content_y = int(event.screen_y - region.y) if event.screen_y is not None else int(event.y)

            line_index = int(content_y + self.scroll_y)
            if self.lines:
                line_index = max(0, min(len(self.lines) - 1, line_index))
                char_offset = max(0, min(len(self.lines[line_index].text), content_x))
                self._drag_current = (line_index, char_offset)
                self.refresh()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if event.button == 1 and self._drag_start is not None:
            region = self.content_region
            content_x = int(event.screen_x - region.x) if event.screen_x is not None else int(event.x)
            content_y = int(event.screen_y - region.y) if event.screen_y is not None else int(event.y)

            line_index = int(content_y + self.scroll_y)
            if self.lines:
                end_line = max(0, min(len(self.lines) - 1, line_index))
                end_char = max(0, min(len(self.lines[end_line].text), content_x))

                start_line, start_char = self._drag_start

                selected_text = self._get_text_range(start_line, start_char, end_line, end_char)
                if selected_text:
                    self.app.copy_to_clipboard(selected_text)
                    self.app.notify("Copied to clipboard", timeout=2.0)

            self._drag_start = None
            self._drag_current = None
            self.refresh()

    def render_line(self, y: int) -> Strip:
        strip = super().render_line(y)

        if self._drag_start is not None and self._drag_current is not None:
            scroll_x, scroll_y = self.scroll_offset
            abs_line = int(scroll_y + y)

            start_line, start_char = self._drag_start
            end_line, end_char = self._drag_current

            if (start_line, start_char) > (end_line, end_char):
                start_line, start_char, end_line, end_char = end_line, end_char, start_line, start_char

            if start_line <= abs_line <= end_line:
                if start_line == end_line:
                    highlight_start = start_char
                    highlight_end = end_char
                elif abs_line == start_line:
                    highlight_start = start_char
                    highlight_end = strip.cell_length
                elif abs_line == end_line:
                    highlight_start = 0
                    highlight_end = end_char
                else:
                    highlight_start = 0
                    highlight_end = strip.cell_length

                if highlight_start < highlight_end:
                    highlight_start = max(0, min(strip.cell_length, highlight_start))
                    highlight_end = max(0, min(strip.cell_length, highlight_end))

                    if highlight_start < highlight_end:
                        highlight_style = Style(bgcolor="#1E40AF", color="#FFFFFF")
                        p0 = strip.crop(0, highlight_start)
                        p1 = strip.crop(highlight_start, highlight_end)
                        p2 = strip.crop(highlight_end, strip.cell_length)
                        p1 = p1.apply_style(highlight_style)
                        strip = Strip.join([p0, p1, p2])

        return strip

    def _get_text_range(self, start_line: int, start_char: int, end_line: int, end_char: int) -> str:
        if (start_line, start_char) > (end_line, end_char):
            start_line, start_char, end_line, end_char = end_line, end_char, start_line, start_char

        if start_line == end_line:
            return self.lines[start_line].text[start_char:end_char]

        selected_lines = []
        selected_lines.append(self.lines[start_line].text[start_char:])
        for l in range(start_line + 1, end_line):
            selected_lines.append(self.lines[l].text)
        selected_lines.append(self.lines[end_line].text[:end_char])

        return "\n".join(selected_lines)


# ── Main app ──────────────────────────────────────────────────────────────────

class AssistantApp(App):
    TITLE = "echo assistant"
    SUB_TITLE = "Personal Assistant"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_log", "Clear", show=True),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=True),
    ]

    CSS = f"""
    Screen {{
        layout: horizontal;
        background: #0D0D0D;
    }}

    /* ── Chat pane ── */
    #chat-pane {{
        width: 1fr;
        layout: vertical;
    }}

    #log {{
        width: 100%;
        height: 1fr;
        padding: 1 3;
        scrollbar-color: #232323 #0D0D0D;
        scrollbar-size: 1 1;
    }}

    #thinking {{
        height: 1;
        padding: 0 0;
        background: #0D0D0D;
    }}

    #input-container {{
        layout: vertical;
        height: auto;
        background: #111111;
        border-top: tall #232323;
    }}

    #suggestions {{
        height: auto;
        padding: 0 2;
        background: #161616;
        color: #F3F3F3;
        border-bottom: tall #232323;
    }}

    #toasts {{
        height: auto;
        padding: 0 2;
        background: #8BFF7A;
        color: #0D0D0D;
    }}

    #input-strip {{
        height: auto;
        min-height: 3;
        layout: horizontal;
        padding: 1 2;
    }}

    #prompt-glyph {{
        width: 4;
        height: 1;
        content-align: center middle;
        color: #8BFF7A;
    }}

    #user-input, #user-input:focus {{
        width: 1fr;
        height: 1;
        border: none !important;
        background: transparent !important;
        color: #F3F3F3;
    }}

    /* ── Sidebar ── */
    #sidebar {{
        width: {SIDEBAR_WIDTH};
        layout: vertical;
        background: #111111;
        border-left: tall #232323;
        padding: 1 1;
    }}

    #sb-inner {{
        width: 100%;
        height: auto;
        background: transparent;
        padding: 0 !important;
    }}

    #sb-logo {{
        padding: 1 0 0 1;
        height: auto;
        width: 100%;
    }}

    #sb-divider-1 {{
        height: 1;
        width: 100%;
        margin-top: 0;
    }}

    #sb-divider-2, #sb-divider-3 {{
        height: 1;
        width: 100%;
    }}

    #sb-section-label-stats {{
        height: 1;
        margin-top: 0;
    }}

    #sb-section-label-keys,
    #sb-section-label-tasks {{
        height: 1;
        margin-top: 1;
    }}

    #sb-stats, #sb-keys, #sb-tasks {{
        height: auto;
        padding: 1 0 0 0;
        width: 100%;
    }}

    /* ── Header / Footer ── */
    Header {{
        background: #111111;
        color: #8BFF7A;
        border-bottom: tall #232323;
    }}

    Footer {{
        background: #111111;
        color: #666666;
        border-top: tall #232323;
    }}
    """

    def __init__(self) -> None:
        super().__init__()
        self.agent = Agent()
        self._warmup_done = False
        self._log:      MessageRichLog  | None = None
        self._thinking: ThinkingBar     | None = None
        self._sidebar:  Sidebar         | None = None
        self._input:    MessageTextArea | None = None
        self._suggestions: SuggestionPanel | None = None
        self._toasts:   ToastContainer  | None = None

        # Check if we recovered past session context
        self.restored_context = len(self.agent.history) > 1

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="chat-pane"):
                yield MessageRichLog(id="log", wrap=True, highlight=False, markup=True)
                yield ThinkingBar(id="thinking")
                with Vertical(id="input-container"):
                    yield ToastContainer(id="toasts")
                    yield SuggestionPanel(id="suggestions")
                    with Horizontal(id="input-strip"):
                        yield Label(">", id="prompt-glyph")
                        yield MessageTextArea(placeholder="Type a message...", id="user-input")
            with Vertical(id="sidebar"):
                yield Sidebar(id="sb-inner")
        yield Footer()

    def on_mount(self) -> None:
        import sys
        sys.stdout.write("\x1b]2;echo assistant\x07")
        sys.stdout.flush()

        self._log         = self.query_one("#log",           MessageRichLog)
        self._thinking    = self.query_one("#thinking",      ThinkingBar)
        self._sidebar     = self.query_one("#sb-inner",      Sidebar)
        self._input       = self.query_one("#user-input",    MessageTextArea)
        self._suggestions = self.query_one("#suggestions",   SuggestionPanel)
        self._toasts      = self.query_one("#toasts",        ToastContainer)

        self._input.disabled = True
        self._log.write("  [dim #666666]Starting echo...[/]\n")
        self._thinking.start("loading...")

        def _warmup() -> None:
            try:
                self.agent.warmup()
            except Exception:
                pass
            self.call_from_thread(self._on_ready)

        threading.Thread(target=_warmup, daemon=True).start()

    def _on_ready(self) -> None:
        if self._warmup_done:
            return
        self._warmup_done = True

        assert self._log      is not None
        assert self._thinking is not None
        assert self._input    is not None

        self._thinking.stop()
        ts = datetime.now().strftime("%H:%M")
        
        # Load active session history log if we restored past conversations
        if self.restored_context:
            self._log.write(
                f"  [#232323]{'─' * 44}[/]\n"
                f"  [bold #8BFF7A]echo[/] [#666666]resumed session history.[/]  [dim #666666]{ts}[/]\n"
                f"  [#232323]{'─' * 44}[/]\n"
            )
            # Re-render past message threads in history
            for turn in self.agent.history:
                role = turn.get("role")
                content = turn.get("content")
                if role == "user":
                    self._log.write(Text(f"\nJosh: {content}", style="bold #F3F3F3"))
                elif role == "assistant":
                    self._log.write(Text(f"\necho: ", style="bold #8BFF7A"))
                    render_reply_to_log(content, self._log)
                    self._log.write(Text("\n"))
        else:
            self._log.write(
                f"  [#232323]{'─' * 44}[/]\n"
                f"  [bold #8BFF7A]echo[/] [#666666]is ready.[/]  [dim #666666]{ts}[/]\n"
                f"  [#232323]{'─' * 44}[/]\n"
            )

        self._input.disabled = False
        self._input.focus()

    # ── Autocomplete Autopopup ─────────────────────────────────────────────────

    def on_autocomplete_check(self, event: AutocompleteCheck) -> None:
        if self._suggestions:
            self._suggestions.update_suggestions(event.text)

    # ── Events ────────────────────────────────────────────────────────────────

    def on_message_text_area_submitted(self, event: MessageTextArea.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return

        event.text_area.text = ""
        event.text_area.disabled = True

        # Intercept slash commands
        if message.startswith("/"):
            self._handle_slash_command(message)
            event.text_area.disabled = False
            event.text_area.focus()
            return

        ts = datetime.now().strftime("%H:%M")

        # Write user message inline
        msg_text = Text()
        msg_text.append(f"\nJosh ({ts}): ", style="bold #F3F3F3")
        body_text = parse_markdown_to_text(message, default_style="#A0A0A0")
        msg_text.append(body_text)

        self._log.write(msg_text)
        self._sidebar.increment_messages() # type: ignore[union-attr]
        self._thinking.start()             # type: ignore[union-attr]

        def _run() -> None:
            try:
                # Track number of tasks before running
                task_count_before = self._get_task_count()
                
                reply = self.agent.send(message)
                
                # Check if tasks file was modified and trigger toast notification
                task_count_after = self._get_task_count()
                if task_count_after > task_count_before:
                    self.call_from_thread(self._trigger_new_task_notification)
            except Exception as exc:
                reply = f"Error: {exc}"
            self.call_from_thread(self._on_reply, reply)

        threading.Thread(target=_run, daemon=True).start()

    def _get_task_count(self) -> int:
        if _TASKS_FILE.exists():
            try:
                return len(json.loads(_TASKS_FILE.read_text(encoding="utf-8")))
            except Exception:
                pass
        return 0

    def _trigger_new_task_notification(self) -> None:
        if self._toasts:
            self._toasts.trigger_toast("Action executed & logged in Tasks")

    def _on_reply(self, reply: str) -> None:
        assert self._log      is not None
        assert self._thinking is not None
        assert self._input    is not None

        self._thinking.stop()
        ts = datetime.now().strftime("%H:%M")

        # Write assistant prefix inline
        header = Text()
        header.append(f"\necho ({ts}): ", style="bold #8BFF7A")
        self._log.write(header)

        render_reply_to_log(reply, self._log)

        self._log.write(Text("\n"))
        self._input.disabled = False
        self._input.focus()

        if self._sidebar:
            self._sidebar.refresh_tasks()

    def _handle_slash_command(self, cmd_text: str) -> None:
        cmd = cmd_text.split(" ")[0].lower()
        if cmd == "/clear":
            self.action_clear_log()
        elif cmd == "/quit":
            self.action_quit()
        elif cmd == "/toggle-sidebar":
            self.action_toggle_sidebar()
        elif cmd == "/history":
            self.agent.clear_session_history()
            if self._log:
                self._log.clear()
                self._log.write("\n[dim #666666]Session history log cleared.[/]\n")
        else:
            if self._log:
                self._log.write(f"\n[red]Unknown slash command: {cmd}[/]\n")

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_clear_log(self) -> None:
        if self._log:
            self._log.clear()
            ts = datetime.now().strftime("%H:%M")
            self._log.write(f"\n[dim #666666]Log cleared  {ts}[/]\n")

    def action_toggle_sidebar(self) -> None:
        sb = self.query_one("#sidebar", Vertical)
        if sb.styles.display == "none":
            sb.styles.display = "block"
            if self._toasts:
                self._toasts.trigger_toast("Sidebar visible")
        else:
            sb.styles.display = "none"
            if self._toasts:
                self._toasts.trigger_toast("Sidebar hidden")

    def action_quit(self) -> None:
        self.exit()