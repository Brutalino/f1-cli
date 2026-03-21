"""
Demo data generator.

Simulates realistic F1 timing data for development and testing,
so you don't need an active F1 session to work on the TUI.
"""

from __future__ import annotations

import random
import threading
import time

from .data_store import DataStore, DriverTiming, RaceControlMessage

# 2024-style grid with realistic team colors
DEMO_DRIVERS = [
    ("1",  "VER", "Max Verstappen",       "Red Bull Racing",     "#3671C6"),
    ("11", "PER", "Sergio Perez",          "Red Bull Racing",     "#3671C6"),
    ("44", "HAM", "Lewis Hamilton",        "Ferrari",             "#E8002D"),
    ("16", "LEC", "Charles Leclerc",       "Ferrari",             "#E8002D"),
    ("4",  "NOR", "Lando Norris",          "McLaren",             "#FF8000"),
    ("81", "PIA", "Oscar Piastri",         "McLaren",             "#FF8000"),
    ("63", "RUS", "George Russell",        "Mercedes",            "#27F4D2"),
    ("12", "ANT", "Kimi Antonelli",        "Mercedes",            "#27F4D2"),
    ("14", "ALO", "Fernando Alonso",       "Aston Martin",        "#229971"),
    ("18", "STR", "Lance Stroll",          "Aston Martin",        "#229971"),
    ("10", "GAS", "Pierre Gasly",          "Alpine",              "#FF87BC"),
    ("31", "OCO", "Esteban Ocon",          "Haas F1 Team",        "#B6BABD"),
    ("22", "TSU", "Yuki Tsunoda",          "RB",                  "#6692FF"),
    ("30", "LAW", "Liam Lawson",           "RB",                  "#6692FF"),
    ("23", "ALB", "Alexander Albon",       "Williams",            "#64C4FF"),
    ("55", "SAI", "Carlos Sainz",          "Williams",            "#64C4FF"),
    ("27", "HUL", "Nico Hulkenberg",       "Kick Sauber",         "#52E252"),
    ("5",  "BOR", "Gabriel Bortoleto",     "Kick Sauber",         "#52E252"),
    ("87", "BEA", "Oliver Bearman",        "Haas F1 Team",        "#B6BABD"),
    ("7",  "DOO", "Jack Doohan",           "Alpine",              "#FF87BC"),
]

TYRE_COMPOUNDS = ["SOFT", "MEDIUM", "HARD"]

RC_MESSAGES = [
    ("Flag", "GREEN", "GREEN LIGHT - PIT LANE OPEN"),
    ("Flag", "GREEN", "DRS ENABLED"),
    ("Flag", "YELLOW", "YELLOW FLAG IN TURN 4"),
    ("Other", "", "CAR 11 (PER) TRACK LIMITS TURN 9 LAP 12 - WARNING"),
    ("Other", "", "CAR 18 (STR) TRACK LIMITS TURN 4 LAP 15 - PENALTY - 5 SEC"),
    ("SafetyCar", "", "SAFETY CAR DEPLOYED"),
    ("SafetyCar", "", "SAFETY CAR IN THIS LAP"),
    ("Flag", "GREEN", "GREEN FLAG - SAFETY CAR IN"),
    ("Drs", "", "DRS ENABLED"),
    ("Flag", "BLUE", "BLUE FLAG FOR CAR 27 (HUL)"),
    ("Other", "", "FASTEST LAP: CAR 1 (VER) 1:18.432 ON LAP 34"),
]


def _random_lap_time(base_seconds: float = 78.5, variance: float = 1.5) -> str:
    """Generate a realistic lap time string like '1:18.523'."""
    t = base_seconds + random.gauss(0, variance)
    mins = int(t // 60)
    secs = t % 60
    return f"{mins}:{secs:06.3f}"


def _random_sector(base: float, variance: float = 0.3) -> str:
    """Generate a sector time string like '23.456'."""
    t = base + random.gauss(0, variance)
    return f"{t:.3f}"


def _gap_string(gap: float) -> str:
    if gap <= 0:
        return ""
    if gap < 60:
        return f"+{gap:.3f}"
    laps = int(gap // 60)
    return f"+{laps} LAP{'S' if laps > 1 else ''}"


class DemoRunner:
    """
    Feeds realistic simulated data into a DataStore.
    Runs in a background thread, simulating a race lap by lap.
    """

    def __init__(self, store: DataStore, speed: float = 1.0):
        self.store = store
        self.speed = speed  # 1.0 = real-time, 2.0 = double speed, etc.
        self._should_stop = False
        self._thread: threading.Thread | None = None

    def start_background(self):
        self._should_stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._should_stop = True

    def _run(self):
        store = self.store
        store.is_connected = True

        # Set up session info
        store.gp_name = "FORMULA 1 GRAN PREMIO D'ITALIA 2025"
        store.track_name = "Monza"
        store.session_name = "Race"
        store.session_type = "Race"
        store.total_laps = 53
        store.air_temp = "28°C"
        store.track_temp = "42°C"
        store.humidity = "45%"
        store.wind_speed = "12 km/h"
        store.rainfall = False
        store.track_status = "1"
        store.track_status_message = "🟢 All Clear"

        # Initialize drivers in starting grid order (shuffled a bit)
        order = list(range(len(DEMO_DRIVERS)))
        random.shuffle(order)

        gaps = [0.0]  # Leader has 0 gap
        for i in range(1, len(DEMO_DRIVERS)):
            gaps.append(gaps[-1] + random.uniform(0.3, 2.5))

        drivers_state: list[dict] = []
        for pos_idx, drv_idx in enumerate(order):
            num, tla, name, team, color = DEMO_DRIVERS[drv_idx]
            drv = DriverTiming(
                number=num,
                abbreviation=tla,
                full_name=name,
                team=team,
                team_color=color,
                position=pos_idx + 1,
                gap_to_leader=_gap_string(gaps[pos_idx]),
                interval=_gap_string(gaps[pos_idx] - gaps[pos_idx - 1]) if pos_idx > 0 else "",
                tyre_compound=random.choice(TYRE_COMPOUNDS),
                tyre_age=random.randint(0, 3),
                num_pit_stops=0,
            )
            store.drivers[num] = drv
            drivers_state.append({
                "idx": drv_idx,
                "num": num,
                "base_pace": 78.0 + random.gauss(0, 0.4),  # Inherent pace
                "gap": gaps[pos_idx],
                "pit_lap": random.choice([15, 16, 17, 28, 29, 30, 35, 36]),
                "pitted": False,
                "retired": False,
            })

        store._dirty = True
        time.sleep(1.0 / self.speed)

        # Add formation lap RC message
        store.race_control_messages.insert(0, RaceControlMessage(
            timestamp="", message="LIGHTS OUT AND AWAY WE GO!", category="Other"
        ))

        # ── Simulate race lap by lap ──
        rc_idx = 0
        overall_best_lap = 999.0

        for lap in range(1, store.total_laps + 1):
            if self._should_stop:
                break

            store.current_lap = lap
            store.clock_remaining = f"LAP {lap}/{store.total_laps}"

            # Occasionally inject race control messages
            if random.random() < 0.15 and rc_idx < len(RC_MESSAGES):
                cat, flag, msg = RC_MESSAGES[rc_idx]
                store.race_control_messages.insert(0, RaceControlMessage(
                    timestamp="", message=msg, category=cat, flag=flag,
                ))
                rc_idx += 1

                # Briefly show yellow/SC if applicable
                if "SAFETY CAR DEPLOYED" in msg:
                    store.track_status = "4"
                    store.track_status_message = "🟠 Safety Car"
                elif "YELLOW" in msg:
                    store.track_status = "2"
                    store.track_status_message = "🟡 Yellow Flag"
                elif "GREEN" in flag:
                    store.track_status = "1"
                    store.track_status_message = "🟢 All Clear"

            # Update each driver
            for ds in drivers_state:
                if ds["retired"]:
                    continue

                num = ds["num"]
                drv = store.drivers[num]

                # Pit stop logic
                if lap == ds["pit_lap"] and not ds["pitted"]:
                    drv.in_pit = True
                    drv.pit_out = False
                    ds["pitted"] = True
                    drv.num_pit_stops += 1
                    drv.tyre_compound = random.choice(TYRE_COMPOUNDS)
                    drv.tyre_age = 0
                    ds["gap"] += random.uniform(18, 24)  # Pit stop time loss
                elif drv.in_pit:
                    drv.in_pit = False
                    drv.pit_out = True
                else:
                    drv.pit_out = False

                # Retirement chance (very small)
                if random.random() < 0.003 and lap > 5:
                    ds["retired"] = True
                    drv.retired = True
                    drv.last_lap = ""
                    continue

                drv.tyre_age += 1
                drv.num_laps = lap

                # Lap time with some variance
                tyre_deg = drv.tyre_age * 0.015
                lap_time_sec = ds["base_pace"] + random.gauss(0, 0.5) + tyre_deg
                if drv.in_pit:
                    lap_time_sec += random.uniform(18, 24)

                drv.last_lap = _random_lap_time(lap_time_sec, 0.2)
                
                # Personal/overall best flags
                is_pb = random.random() < 0.08
                is_ob = random.random() < 0.015
                drv.last_lap_personal_best = is_pb or is_ob
                drv.last_lap_overall_best = is_ob
                
                if is_ob and lap_time_sec < overall_best_lap:
                    overall_best_lap = lap_time_sec

                if not drv.best_lap or is_pb or is_ob:
                    drv.best_lap = drv.last_lap

                # Sector times
                s1_base = ds["base_pace"] * 0.30
                s2_base = ds["base_pace"] * 0.38
                s3_base = ds["base_pace"] * 0.32

                drv.sector_1 = _random_sector(s1_base)
                drv.sector_2 = _random_sector(s2_base)
                drv.sector_3 = _random_sector(s3_base)
                drv.sector_1_personal_best = random.random() < 0.1
                drv.sector_2_personal_best = random.random() < 0.1
                drv.sector_3_personal_best = random.random() < 0.1
                drv.sector_1_overall_best = random.random() < 0.02
                drv.sector_2_overall_best = random.random() < 0.02
                drv.sector_3_overall_best = random.random() < 0.02

                # Evolve gaps slightly
                ds["gap"] += random.gauss(0, 0.15)
                if ds["gap"] < 0:
                    ds["gap"] = 0

            # Re-sort by gap and assign positions
            active = [ds for ds in drivers_state if not ds["retired"]]
            active.sort(key=lambda x: x["gap"])
            for pos_idx, ds in enumerate(active):
                drv = store.drivers[ds["num"]]
                drv.position = pos_idx + 1
                if pos_idx == 0:
                    drv.gap_to_leader = ""
                    drv.interval = ""
                else:
                    drv.gap_to_leader = _gap_string(ds["gap"])
                    prev_gap = active[pos_idx - 1]["gap"]
                    drv.interval = _gap_string(ds["gap"] - prev_gap)

            # Retired drivers get high position numbers
            for ds in drivers_state:
                if ds["retired"]:
                    store.drivers[ds["num"]].position = 99

            store._dirty = True

            # Simulate time between laps (compressed)
            time.sleep(max(0.8, 3.0 / self.speed))

        # Race finished
        store.race_control_messages.insert(0, RaceControlMessage(
            timestamp="", message="CHEQUERED FLAG", category="Flag", flag="CHEQUERED"
        ))
        store._dirty = True
        store.is_connected = False
