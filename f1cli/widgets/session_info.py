"""
Session Info widget — minimal top bar.
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static
from ..data_store import DataStore


class SessionInfo(Static):

    DEFAULT_CSS = """
    SessionInfo {
        width: 100%;
        height: 2;
    }
    """

    def __init__(self, store: DataStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store

    def render_info(self) -> Text:
        s = self.store
        parts = Text()

        # Connection dot
        if s.is_connected:
            parts.append(" \u25cf ", style="bold green")
        else:
            parts.append(" \u25cf ", style="bold red")

        # GP Name — brief
        gp = s.gp_name or "F1"
        parts.append(gp, style="bold")

        # Session
        if s.session_name:
            parts.append(f"  {s.session_name}", style="dim bold")

        # Laps or clock
        if s.total_laps > 0 and s.current_lap > 0:
            pct = s.current_lap / s.total_laps
            style = "bold red" if pct > 0.9 else "bold yellow" if pct > 0.7 else "bold"
            parts.append(f"  {s.current_lap}/{s.total_laps}", style=style)
        elif s.clock_remaining:
            parts.append(f"  {s.clock_remaining}", style="bold")

        # Track status (only if not clear)
        if s.track_status != "1":
            parts.append(f"  {s.track_status_message}", style="bold bright_white")

        # Weather — very compact
        weather = []
        if s.air_temp:
            weather.append(s.air_temp)
        if s.track_temp:
            weather.append(f"T:{s.track_temp}")
        if s.rainfall:
            weather.append("\U0001f327")
        if weather:
            parts.append(f"  {' '.join(weather)}", style="dim")

        return parts

    def refresh_data(self):
        self.update(self.render_info())
