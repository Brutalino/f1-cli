"""
Timing Tower widget — the main race leaderboard.

Clean, minimal table. No heavy borders. Color speaks for itself.
"""

from __future__ import annotations

from rich.text import Text
from rich.table import Table
from rich.style import Style
from rich.box import SIMPLE

from textual.widgets import Static

from ..data_store import DataStore, DriverTiming


TYRE_STYLES = {
    "SOFT": ("S", "bold red"),
    "MEDIUM": ("M", "bold yellow"),
    "HARD": ("H", "bold white"),
    "INTERMEDIATE": ("I", "bold green"),
    "WET": ("W", "bold blue"),
}


def _sector_style(val: str, pb: bool, ob: bool) -> Text:
    if not val:
        return Text("")
    if ob:
        return Text(val, style="bold magenta")
    if pb:
        return Text(val, style="bold green")
    return Text(val, style="bright_white")


def _lap_style(val: str, pb: bool, ob: bool) -> Text:
    if not val:
        return Text("")
    if ob:
        return Text(val, style="bold magenta")
    if pb:
        return Text(val, style="bold green")
    return Text(val, style="bright_white")


class TimingTower(Static):
    """Rich-rendered timing tower leaderboard."""

    DEFAULT_CSS = """
    TimingTower {
        width: 100%;
        height: 100%;
        overflow-y: auto;
    }
    """

    def __init__(self, store: DataStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store

    def render_tower(self) -> Table:
        table = Table(
            box=SIMPLE,
            show_header=True,
            header_style="dim bold",
            expand=True,
            padding=(0, 1),
            show_edge=False,
            show_lines=False,
        )

        table.add_column("P", width=3, justify="right")
        table.add_column("", width=1)
        table.add_column("DRV", width=4)
        table.add_column("GAP", width=10, justify="right")
        table.add_column("INT", width=9, justify="right")
        table.add_column("LAST", width=10, justify="right")
        table.add_column("BEST", width=10, justify="right")
        table.add_column("S1", width=8, justify="right")
        table.add_column("S2", width=8, justify="right")
        table.add_column("S3", width=8, justify="right")
        table.add_column("T", width=4, justify="center")
        table.add_column("P#", width=2, justify="center")

        drivers = self.store.get_sorted_drivers()

        for drv in drivers:
            if drv.position == 0 or drv.position >= 99:
                if drv.retired:
                    self._add_retired_row(table, drv)
                continue

            # Position — just the number, clean
            pos_str = f"{drv.position:>2}"
            if drv.position <= 3:
                pos = Text(pos_str, style="bold bright_white")
            elif drv.position <= 10:
                pos = Text(pos_str, style="bright_white")
            else:
                pos = Text(pos_str, style="dim")

            # Team color bar
            color = drv.team_color if drv.team_color else "#888888"
            team_bar = Text("\u2588", style=Style(color=color))

            # Driver name
            if drv.in_pit:
                drv_text = Text(drv.abbreviation or drv.number, style="bold yellow")
            elif drv.pit_out:
                drv_text = Text(drv.abbreviation or drv.number, style="bold cyan")
            else:
                drv_text = Text(drv.abbreviation or drv.number, style="bold bright_white")

            # Gap / Interval
            if drv.in_pit:
                gap = Text("PIT", style="bold yellow")
            elif drv.stopped:
                gap = Text("STOP", style="bold red")
            else:
                gap = Text(drv.gap_to_leader, style="bright_white") if drv.gap_to_leader else Text("")

            interval = Text(drv.interval, style="dim bright_yellow") if drv.interval else Text("")

            # Laps
            last = _lap_style(drv.last_lap, drv.last_lap_personal_best, drv.last_lap_overall_best)
            best = Text(drv.best_lap, style="dim") if drv.best_lap else Text("")

            # Sectors
            s1 = _sector_style(drv.sector_1, drv.sector_1_personal_best, drv.sector_1_overall_best)
            s2 = _sector_style(drv.sector_2, drv.sector_2_personal_best, drv.sector_2_overall_best)
            s3 = _sector_style(drv.sector_3, drv.sector_3_personal_best, drv.sector_3_overall_best)

            # Tyre — compact
            compound = drv.tyre_compound.upper() if drv.tyre_compound else ""
            tyre_char, tyre_style = TYRE_STYLES.get(compound, ("?", "dim"))
            tyre = Text(f"{tyre_char}{drv.tyre_age:>2}", style=tyre_style)

            # Pits
            pits = Text(str(drv.num_pit_stops), style="dim") if drv.num_pit_stops > 0 else Text("")

            table.add_row(pos, team_bar, drv_text, gap, interval, last, best, s1, s2, s3, tyre, pits)

        return table

    def _add_retired_row(self, table: Table, drv: DriverTiming):
        dim = "dim strike"
        color = drv.team_color if drv.team_color else "#888888"
        table.add_row(
            Text("--", style=dim),
            Text("\u2588", style=Style(color=color, dim=True)),
            Text(drv.abbreviation or drv.number, style=dim),
            Text("DNF", style="bold red"),
            Text(""), Text(""), Text(""),
            Text(""), Text(""), Text(""),
            Text(""), Text(""),
        )

    def refresh_data(self):
        self.update(self.render_tower())
