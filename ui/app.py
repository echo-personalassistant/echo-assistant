from __future__ import annotations

import threading
from datetime import datetime

from rich.style import Style
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

# ── ASCII logo ────────────────────────────────────────────────────────────────
# "$" is its own 4-row glyph, same height as the "echo" lettering, concatenated
# row-by-row so it reads as one continuous logo (no more lopsided "$" stuck on
# just the top row).
_DOLLAR = [
    " __  ",
    "(_   ",
    " _)  ",
    "|__| ",
]
_ECHO = [
    "  ___   __  _  _   ___ ",
    " / _ \\ / _|| || | / _ \\",
    "|  __/| |  | __ || (_) |",
    " \\___/ \\_| |_||_| \\___/",
]
ECHO_ASCII = "\n".join(d + e for d, e in zip(_DOLLAR, _ECHO))

SIDEBAR_WIDTH = 36
DIVIDER_WIDTH = 28


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


class MessageTextArea(TextArea):
    """A customized TextArea that handles Shift+Enter for newlines and Enter for submission."""

    class Submitted(Message):
        """Posted when Enter is pressed (without Shift)."""
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


class MessageRichLog(RichLog):
    """A customized RichLog that supports click-and-drag to copy text to the clipboard and highlight it."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._drag_start = None
        self._drag_current = None

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


# ── Sidebar ───────────────────────────────────────────────────────────────────

class Sidebar(Static):
    """Right-hand info/stats panel."""

    messages_sent: reactive[int] = reactive(0)
    discord_status: reactive[str] = reactive("Disabled")
    _start_time: datetime

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._start_time = datetime.now()

    def compose(self) -> ComposeResult:
        yield Static(id="sb-logo")
        yield Static(id="sb-divider-1")
        yield Static(id="sb-section-label-info")
        yield Static(id="sb-stats")
        yield Static(id="sb-divider-2")
        yield Static(id="sb-section-label-session")
        yield Static(id="sb-session")
        yield Static(id="sb-divider-3")
        yield Static(id="sb-section-label-keys")
        yield Static(id="sb-keys")

    def on_mount(self) -> None:
        self._render_chrome()
        self._render_stats()
        self._render_session()
        self._render_keys()
        self.set_interval(1, self._render_session)

    # ── renderers ─────────────────────────────────────────────────────────────
    # NOTE: everything below builds rich.text.Text objects directly instead of
    # markup strings like "[bold #8BFF7A]...[/]". That avoids any chance of a
    # closing tag leaking through as literal text.

    def _render_chrome(self) -> None:
        """Render the logo, dividers, and section labels (static elements)."""
        lines = ECHO_ASCII.splitlines()
        logo = Text()
        for i, line in enumerate(lines):
            style = "bold #8BFF7A" if i == 0 else "#61D65A"
            logo.append(line, style=style)
            if i < len(lines) - 1:
                logo.append("\n")
        self.query_one("#sb-logo", Static).update(logo)

        for sid in ("#sb-divider-1", "#sb-divider-2", "#sb-divider-3"):
            self.query_one(sid, Static).update(Text("─" * DIVIDER_WIDTH, style="#232323"))

        self.query_one("#sb-section-label-info", Static).update(
            Text("  PROFILE", style="dim #666666")
        )
        self.query_one("#sb-section-label-session", Static).update(
            Text("  SESSION", style="dim #666666")
        )
        self.query_one("#sb-section-label-keys", Static).update(
            Text("  SHORTCUTS", style="dim #666666")
        )

    def watch_discord_status(self, new_status: str) -> None:
        self._render_stats()

    def _kv_line(self, label: str, value: str, value_style: str = "#F3F3F3") -> Text:
        """Build one 'label   value' row as a Text object."""
        t = Text()
        t.append(f"  {label}", style="#666666")
        t.append(" " * max(1, 12 - len(label)))
        t.append(value, style=value_style)
        return t

    def _render_stats(self) -> None:
        from config import MODEL
        color = (
            "#8BFF7A" if self.discord_status == "Active"
            else "#FFAC47" if self.discord_status == "Connecting..."
            else "#666666"
        )
        block = Text()
        block.append_text(self._kv_line("User", "Josh"))
        block.append("\n")
        block.append_text(self._kv_line("Model", MODEL))
        block.append("\n")
        block.append_text(self._kv_line("Messages", str(self.messages_sent), "#8BFF7A"))
        block.append("\n")
        block.append_text(self._kv_line("Discord", self.discord_status, color))
        self.query_one("#sb-stats", Static).update(block)

    def _render_session(self) -> None:
        elapsed = datetime.now() - self._start_time
        h, rem = divmod(int(elapsed.total_seconds()), 3600)
        m, s = divmod(rem, 60)

        block = Text()
        block.append_text(self._kv_line("Uptime", f"{h:02d}:{m:02d}:{s:02d}"))
        block.append("\n")
        block.append_text(self._kv_line("Date", datetime.now().strftime("%d %b %Y")))
        block.append("\n")
        block.append_text(self._kv_line("Time", datetime.now().strftime("%H:%M")))
        self.query_one("#sb-session", Static).update(block)

    def _render_keys(self) -> None:
        block = Text()
        block.append_text(self._kv_line("Enter", "Send"))
        block.append("\n")
        block.append_text(self._kv_line("Ctrl+L", "Clear"))
        block.append("\n")
        block.append_text(self._kv_line("Ctrl+C", "Quit"))
        self.query_one("#sb-keys", Static).update(block)

    def increment_messages(self) -> None:
        self.messages_sent += 1
        self._render_stats()


# ── Thinking indicator ────────────────────────────────────────────────────────

class ThinkingBar(Static):
    """Braille spinner shown while the agent or warmup is working."""

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


# ── Main app ──────────────────────────────────────────────────────────────────

class AssistantApp(App):

    TITLE = "$echo"
    SUB_TITLE = "Personal Assistant"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_log", "Clear", show=True),
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

    #input-strip {{
        height: auto;
        min-height: 3;
        layout: horizontal;
        background: #111111;
        border-top: tall #232323;
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
        overflow-y: auto;
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

    #sb-section-label-info {{
        height: 1;
        margin-top: 0;
    }}

    #sb-section-label-session,
    #sb-section-label-keys {{
        height: 1;
        margin-top: 1;
    }}

    #sb-stats, #sb-session, #sb-keys {{
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

    # ── Setup ─────────────────────────────────────────────────────────────────

    def __init__(self) -> None:
        super().__init__()
        self.agent = Agent()
        self._warmup_done = False  # guard: _on_ready must only run once
        self._log:      MessageRichLog  | None = None
        self._thinking: ThinkingBar     | None = None
        self._sidebar:  Sidebar         | None = None
        self._input:    MessageTextArea | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="chat-pane"):
                yield MessageRichLog(id="log", wrap=True, highlight=False, markup=True)
                yield ThinkingBar(id="thinking")
                with Horizontal(id="input-strip"):
                    yield Label(">", id="prompt-glyph")
                    yield MessageTextArea(placeholder="Type a message...", id="user-input")
            yield Sidebar(id="sidebar")
        yield Footer()

    def on_mount(self) -> None:
        self._log      = self.query_one("#log",        MessageRichLog)
        self._thinking = self.query_one("#thinking",   ThinkingBar)
        self._sidebar  = self.query_one("#sidebar",    Sidebar)
        self._input    = self.query_one("#user-input", MessageTextArea)

        # Block input while the model warms up
        self._input.disabled = True
        self._log.write("  [dim #666666]Starting $echo...[/]\n")
        self._thinking.start("loading...")

        # Start warmup thread
        def _warmup() -> None:
            try:
                self.agent.warmup()
            except Exception:
                pass  # If warmup fails, carry on — first message will load the model
            self.call_from_thread(self._on_ready)

        threading.Thread(target=_warmup, daemon=True).start()

        # Start background Discord Bot thread if token is present
        from DCBot.botconfig import DISCORD_TOKEN
        if DISCORD_TOKEN:
            from DCBot.bot import start_discord_bot
            self._sidebar.discord_status = "Connecting..."
            threading.Thread(
                target=start_discord_bot,
                args=(self, DISCORD_TOKEN),
                daemon=True
            ).start()
        else:
            self._sidebar.discord_status = "Disabled"

    def _on_ready(self) -> None:
        if self._warmup_done:
            return  # already ran — ignore duplicate calls
        self._warmup_done = True

        assert self._log      is not None
        assert self._thinking is not None
        assert self._input    is not None

        self._thinking.stop()
        ts = datetime.now().strftime("%H:%M")
        self._log.write(
            f"  [#232323]{'─' * 44}[/]\n"
            f"  [bold #8BFF7A]$echo[/] [#666666]is ready.[/]  [dim #666666]{ts}[/]\n"
            f"  [#232323]{'─' * 44}[/]\n"
        )
        self._input.disabled = False
        self._input.focus()

    def _update_discord_status(self, status: str) -> None:
        if self._sidebar:
            self._sidebar.discord_status = status

    # ── Events ────────────────────────────────────────────────────────────────

    def on_message_text_area_submitted(self, event: MessageTextArea.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return

        event.text_area.text = ""
        event.text_area.disabled = True

        ts = datetime.now().strftime("%H:%M")
        
        msg_text = Text()
        msg_text.append(f"\n  Josh  ", style="bold #F3F3F3")
        msg_text.append(f"{ts}\n", style="dim #666666")
        
        indented_message = "\n".join("  " + line for line in message.splitlines())
        body_text = parse_markdown_to_text(indented_message, default_style="#A0A0A0")
        msg_text.append(body_text)
        
        self._log.write(msg_text)
        self._sidebar.increment_messages() # type: ignore[union-attr]
        self._thinking.start()             # type: ignore[union-attr]

        def _run() -> None:
            try:
                reply = self.agent.send(message)
            except Exception as exc:
                reply = f"Error: {exc}"
            self.call_from_thread(self._on_reply, reply)

        threading.Thread(target=_run, daemon=True).start()

    def _on_reply(self, reply: str) -> None:
        assert self._log      is not None
        assert self._thinking is not None
        assert self._input    is not None

        self._thinking.stop()
        ts = datetime.now().strftime("%H:%M")
        
        msg_text = Text()
        msg_text.append(f"\n  $echo  ", style="bold #8BFF7A")
        msg_text.append(f"{ts}\n", style="dim #666666")
        
        indented_reply = "\n".join("  " + line for line in reply.splitlines())
        body_text = parse_markdown_to_text(indented_reply, default_style="#F3F3F3")
        msg_text.append(body_text)
        msg_text.append("\n")
        
        self._log.write(msg_text)
        self._input.disabled = False
        self._input.focus()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_clear_log(self) -> None:
        if self._log:
            self._log.clear()
            ts = datetime.now().strftime("%H:%M")
            self._log.write(f"\n  [dim #666666]Log cleared  {ts}[/]\n")

    def action_quit(self) -> None:
        self.exit()