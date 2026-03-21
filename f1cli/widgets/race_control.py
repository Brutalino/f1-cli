"""
Race Control Messages — clean scrollable feed.
Hidden by default, toggled with 'c' key.
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static
from ..data_store import DataStore


FLAG_ICONS = {
    "YELLOW": "\U0001f7e1",
    "RED": "\U0001f534",
    "GREEN": "\U0001f7e2",
    "BLUE": "\U0001f535",
    "CHEQUERED": "\U0001f3c1",
}


class RaceControl(Static):

    DEFAULT_CSS = """
    RaceControl {
        width: 100%;
        height: 100%;
        overflow-y: auto;
    }
    """

    def __init__(self, store: DataStore, max_messages: int = 20, **kwargs):
        super().__init__(**kwargs)
        self.store = store
        self.max_messages = max_messages

    def render_messages(self) -> Text:
        output = Text()
        output.append("Race Control\n", style="dim bold")

        messages = self.store.race_control_messages[:self.max_messages]

        if not messages:
            output.append("  no messages\n", style="dim")
            return output

        for msg in messages:
            icon = FLAG_ICONS.get(msg.flag, "\u25b8")
            if msg.category == "SafetyCar":
                icon = "\U0001f7e0"
            elif msg.category == "Drs":
                icon = "\u25b8"

            style = "dim" if msg.flag == "GREEN" else "bright_white"
            if msg.flag == "RED":
                style = "bold red"
            elif msg.flag == "YELLOW":
                style = "yellow"

            output.append(f" {icon} ", style=style)
            output.append(f"{msg.message}\n", style=style)

        return output

    def refresh_data(self):
        self.update(self.render_messages())
