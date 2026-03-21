"""
f1-cli — Rich Live display with toggleable columns.

Views: full / times / simple
Toggle keys: s=sectors  t=tyres+pit  c=race control  q=quit
"""

from __future__ import annotations

import signal
import sys
import threading
import time

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.style import Style
from rich.box import Box

SIMPLE_BOTTOM = Box(
    "    \n"
    "    \n"
    " ── \n"
    "    \n"
    "    \n"
    " ── \n"
    "    \n"
    " ── \n"
)

from .data_store import DataStore, DriverTiming

TYRE_STYLES = {
    "SOFT": ("S", "bold red"),
    "MEDIUM": ("M", "bold yellow"),
    "HARD": ("H", "bold white"),
    "INTERMEDIATE": ("I", "bold green"),
    "WET": ("W", "bold blue"),
}

def _sector(val, pb, ob):
    if not val: return Text("")
    if ob: return Text(val, style="bold magenta")
    if pb: return Text(val, style="bold green")
    return Text(val)

def _lap(val, pb, ob):
    if not val: return Text("")
    if ob: return Text(val, style="bold magenta")
    if pb: return Text(val, style="bold green")
    return Text(val)


class ViewState:
    def __init__(self, view: str = "full"):
        if view == "simple":
            self.show_times = False
            self.show_sectors = False
            self.show_tyres = False
        elif view == "times":
            self.show_times = True
            self.show_sectors = False
            self.show_tyres = False
        else:
            self.show_times = True
            self.show_sectors = True
            self.show_tyres = True
        self.show_rc = False


def build_header(store: DataStore) -> Text:
    s = store
    t = Text()
    if s.is_connected:
        t.append(" \u25cf ", style="bold green")
    else:
        t.append(" \u25cf ", style="bold red")
    t.append(s.gp_name or "F1", style="bold")
    if s.session_name:
        t.append(f"  {s.session_name}", style="dim bold")
    if s.total_laps > 0 and s.current_lap > 0:
        pct = s.current_lap / s.total_laps
        style = "bold red" if pct > 0.9 else "bold yellow" if pct > 0.7 else "bold"
        t.append(f"  {s.current_lap}/{s.total_laps}", style=style)
    elif s.clock_remaining:
        t.append(f"  {s.clock_remaining}", style="bold")
    if s.track_status != "1":
        t.append(f"  {s.track_status_message}", style="bold")
    w = []
    if s.air_temp: w.append(s.air_temp)
    if s.track_temp: w.append(f"T:{s.track_temp}")
    if s.rainfall: w.append("Rain")
    if w:
        t.append(f"  {' '.join(w)}", style="dim")
    return t


def _count_columns(vs: ViewState) -> int:
    n = 4  # P, dot, DRV, GAP
    if vs.show_times: n += 3
    if vs.show_sectors: n += 3
    if vs.show_tyres: n += 2
    return n


def _build_driver_row(drv: DriverTiming, vs: ViewState) -> list:
    row = []

    ps = f"{drv.position:>2}"
    row.append(Text(ps, style="bold" if drv.position <= 3 else "dim" if drv.position > 10 else ""))

    color = drv.team_color if drv.team_color else "#888"
    row.append(Text("\u25cf", style=Style(color=color)))

    if drv.in_pit:
        row.append(Text(drv.abbreviation or drv.number, style="bold yellow"))
    elif drv.pit_out:
        row.append(Text(drv.abbreviation or drv.number, style="bold cyan"))
    else:
        row.append(Text(drv.abbreviation or drv.number, style="bold"))

    if drv.in_pit:
        row.append(Text("PIT", style="bold yellow"))
    elif drv.stopped:
        row.append(Text("STOP", style="bold red"))
    else:
        row.append(Text(drv.gap_to_leader) if drv.gap_to_leader else Text(""))

    if vs.show_times:
        row.append(Text(drv.interval, style="dim") if drv.interval else Text(""))
        row.append(_lap(drv.last_lap, drv.last_lap_personal_best, drv.last_lap_overall_best))
        row.append(Text(drv.best_lap, style="dim") if drv.best_lap else Text(""))

    if vs.show_sectors:
        row.append(_sector(drv.sector_1, drv.sector_1_personal_best, drv.sector_1_overall_best))
        row.append(_sector(drv.sector_2, drv.sector_2_personal_best, drv.sector_2_overall_best))
        row.append(_sector(drv.sector_3, drv.sector_3_personal_best, drv.sector_3_overall_best))

    if vs.show_tyres:
        compound = drv.tyre_compound.upper() if drv.tyre_compound else ""
        tc, ts_style = TYRE_STYLES.get(compound, ("?", "dim"))
        row.append(Text(f"{tc}{drv.tyre_age:>2}", style=ts_style))
        row.append(Text(str(drv.num_pit_stops), style="dim") if drv.num_pit_stops > 0 else Text(""))

    return row


def _build_retired_row(drv: DriverTiming, vs: ViewState) -> list:
    color = drv.team_color if drv.team_color else "#888"
    row = [
        Text("--", style="dim strike"),
        Text("\u25cf", style=Style(color=color, dim=True)),
        Text(drv.abbreviation or drv.number, style="dim strike"),
        Text("DNF", style="bold red"),
    ]
    if vs.show_times: row.extend([Text("")] * 3)
    if vs.show_sectors: row.extend([Text("")] * 3)
    if vs.show_tyres: row.extend([Text("")] * 2)
    return row


def build_tower(store: DataStore, vs: ViewState, body_height: int = 0) -> Table:
    table = Table(
        box=SIMPLE_BOTTOM,
        show_header=True,
        header_style="dim",
        expand=True,
        padding=(0, 1),
        show_edge=True,
        show_lines=False,
    )

    table.add_column("P", width=3, justify="right")
    table.add_column("", width=1)
    table.add_column("DRV", width=4)
    table.add_column("GAP", width=10, justify="right")

    if vs.show_times:
        table.add_column("INT", width=9, justify="right")
        table.add_column("LAST", width=10, justify="right")
        table.add_column("BEST", width=10, justify="right")

    if vs.show_sectors:
        table.add_column("S1", width=8, justify="right")
        table.add_column("S2", width=8, justify="right")
        table.add_column("S3", width=8, justify="right")

    if vs.show_tyres:
        table.add_column("T", width=4, justify="center")
        table.add_column("P#", width=2, justify="center")

    ncols = _count_columns(vs)
    drivers = store.get_sorted_drivers()

    active = [d for d in drivers if 0 < d.position < 99]
    retired = [d for d in drivers if d.retired]

    n = len(active)

    # Calculate spacer distribution
    overhead = 4  # top edge + header + separator + bottom edge
    n_retired = len(retired)
    total_rows = n + n_retired
    extra = max(0, body_height - overhead - total_rows) if body_height > 0 else 0

    spacer_positions = set()
    if extra > 0 and n > 1:
        step = n / extra
        for i in range(extra):
            pos = int(i * step)
            spacer_positions.add(pos)

    empty_row = [Text("") for _ in range(ncols)]

    for i, drv in enumerate(active):
        table.add_row(*_build_driver_row(drv, vs))
        if i in spacer_positions:
            table.add_row(*empty_row)

    for drv in retired:
        table.add_row(*_build_retired_row(drv, vs))

    return table


def build_rc(store: DataStore) -> Text:
    t = Text()
    msgs = store.race_control_messages[:3]
    if not msgs: return t
    t.append("  RC  ", style="bold reverse")
    t.append(" ")
    for i, msg in enumerate(msgs):
        if i > 0:
            t.append(" \u2502 ", style="dim")
        style = "bold red" if msg.flag == "RED" else "yellow" if msg.flag == "YELLOW" else "dim"
        t.append(msg.message, style=style)
    return t


def build_legend(vs: ViewState) -> Text:
    t = Text()
    t.append("  \u25cf", style="bold green")
    t.append(" PB ", style="dim")
    t.append("\u25cf", style="bold magenta")
    t.append(" Best ", style="dim")
    t.append("\u25cf", style="bold yellow")
    t.append(" Pit ", style="dim")
    t.append("\u25cf", style="bold cyan")
    t.append(" Out", style="dim")

    if vs.show_tyres:
        t.append("  \u2502 ", style="dim")
        t.append("S", style="bold red")
        t.append(" M", style="bold yellow")
        t.append(" H", style="bold white")
        t.append(" I", style="bold green")
        t.append(" W", style="bold blue")

    t.append("  \u2502 ", style="dim")

    def _key(k, label, active):
        t.append(k, style="bold" if active else "dim")
        t.append(f":{label} ", style="dim")

    _key("s", "sectors", vs.show_sectors)
    _key("t", "tyres", vs.show_tyres)
    _key("c", "RC", vs.show_rc)
    t.append("q", style="bold")
    t.append(":quit", style="dim")
    return t


def run_app(store: DataStore, view: str = "full"):
    console = Console()
    vs = ViewState(view)
    running = [True]

    def on_sigint(sig, frame):
        running[0] = False
    signal.signal(signal.SIGINT, on_sigint)

    def key_listener():
        import tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while running[0]:
                ch = sys.stdin.read(1)
                if ch == 'q':
                    running[0] = False
                    break
                elif ch == 's':
                    vs.show_sectors = not vs.show_sectors
                elif ch == 't':
                    vs.show_tyres = not vs.show_tyres
                elif ch == 'c':
                    vs.show_rc = not vs.show_rc
        except Exception:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    key_thread = threading.Thread(target=key_listener, daemon=True)
    key_thread.start()

    rc_size = 2

    def make_display():
        layout = Layout()

        footer_size = 1
        header_size = 1
        body_h = console.height - header_size - footer_size
        if vs.show_rc:
            body_h -= rc_size

        layout.split_column(
            Layout(name="header", size=header_size),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=footer_size),
        )

        layout["header"].update(build_header(store))

        if vs.show_rc:
            rc = build_rc(store)
            if rc:
                body_layout = Layout()
                body_layout.split_column(
                    Layout(name="table", ratio=1),
                    Layout(name="rc", size=rc_size),
                )
                body_layout["table"].update(build_tower(store, vs, body_h))
                body_layout["rc"].update(rc)
                layout["body"].update(body_layout)
            else:
                layout["body"].update(build_tower(store, vs, body_h))
        else:
            layout["body"].update(build_tower(store, vs, body_h))

        layout["footer"].update(build_legend(vs))
        return layout

    with Live(make_display(), console=console, refresh_per_second=2, screen=True) as live:
        while running[0]:
            live.update(make_display())
            time.sleep(0.5)
