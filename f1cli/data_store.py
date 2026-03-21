"""
Central data store for F1 live timing state.

Receives parsed messages from the SignalR stream and maintains
an up-to-date view of the session. The TUI polls this store
to render the interface.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class DriverTiming:
    """Timing state for a single driver."""
    number: str = ""
    abbreviation: str = ""
    full_name: str = ""
    team: str = ""
    team_color: str = "#FFFFFF"
    position: int = 0
    gap_to_leader: str = ""
    interval: str = ""
    last_lap: str = ""
    best_lap: str = ""
    sector_1: str = ""
    sector_2: str = ""
    sector_3: str = ""
    sector_1_personal_best: bool = False
    sector_2_personal_best: bool = False
    sector_3_personal_best: bool = False
    sector_1_overall_best: bool = False
    sector_2_overall_best: bool = False
    sector_3_overall_best: bool = False
    in_pit: bool = False
    pit_out: bool = False
    retired: bool = False
    stopped: bool = False
    num_laps: int = 0
    num_pit_stops: int = 0
    tyre_compound: str = ""
    tyre_age: int = 0
    last_lap_personal_best: bool = False
    last_lap_overall_best: bool = False


@dataclass
class RaceControlMessage:
    """A single race control message."""
    timestamp: str = ""
    message: str = ""
    category: str = ""  # Flag, Drs, SafetyCar, etc.
    flag: str = ""  # GREEN, YELLOW, RED, etc.


@dataclass
class DataStore:
    """
    Thread-safe store for all live timing data.
    
    The SignalR client runs in a background thread and writes here.
    The Textual app reads from here on its update timer.
    """
    # Driver timing data keyed by driver number (str)
    drivers: dict[str, DriverTiming] = field(default_factory=dict)
    
    # Session info
    session_name: str = ""
    session_type: str = ""  # Race, Qualifying, Practice, Sprint
    gp_name: str = ""
    track_name: str = ""
    
    # Clock / Laps
    clock_remaining: str = ""
    clock_extrapolating: bool = False
    current_lap: int = 0
    total_laps: int = 0
    
    # Track status
    track_status: str = "1"  # 1=Clear, 2=Yellow, 4=SC, 6=VSC, 7=VSCEnding
    track_status_message: str = "All Clear"
    
    # Weather
    air_temp: str = ""
    track_temp: str = ""
    humidity: str = ""
    wind_speed: str = ""
    rainfall: bool = False
    
    # Race control messages (most recent first)
    race_control_messages: list[RaceControlMessage] = field(default_factory=list)
    
    # Connection state
    is_connected: bool = False
    last_message_time: float = 0.0
    
    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    # Dirty flag — set when data changes, cleared by UI after render
    _dirty: bool = False

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_clean(self):
        self._dirty = False

    def get_sorted_drivers(self) -> list[DriverTiming]:
        """Return drivers sorted by position."""
        with self._lock:
            drivers = list(self.drivers.values())
        drivers.sort(key=lambda d: d.position if d.position > 0 else 999)
        return drivers

    # ── Message handlers ──────────────────────────────────────────

    def process_message(self, topic: str, data: Any, timestamp: str = ""):
        """Route an incoming SignalR message to the correct handler."""
        import time
        self.last_message_time = time.time()
        self._dirty = True

        handler_map = {
            "TimingData": self._handle_timing_data,
            "DriverList": self._handle_driver_list,
            "TimingAppData": self._handle_timing_app_data,
            "TimingStats": self._handle_timing_stats,
            "ExtrapolatedClock": self._handle_clock,
            "LapCount": self._handle_lap_count,
            "TrackStatus": self._handle_track_status,
            "WeatherData": self._handle_weather,
            "RaceControlMessages": self._handle_race_control,
            "SessionInfo": self._handle_session_info,
            "SessionData": self._handle_session_data,
            "SessionStatus": self._handle_session_status,
            "TopThree": self._handle_top_three,
        }

        handler = handler_map.get(topic)
        if handler:
            with self._lock:
                try:
                    if isinstance(data, str):
                        data = json.loads(data)
                    handler(data, timestamp)
                except Exception as e:
                    pass  # Silently skip malformed messages

    def _ensure_driver(self, num: str) -> DriverTiming:
        """Get or create a DriverTiming for the given car number."""
        if num not in self.drivers:
            self.drivers[num] = DriverTiming(number=num)
        return self.drivers[num]

    def _handle_driver_list(self, data: dict, ts: str):
        """
        DriverList contains info like abbreviation, name, team, color.
        Format: {"1": {"RacingNumber": "1", "Tla": "VER", ...}, ...}
        """
        for num, info in data.items():
            if not isinstance(info, dict):
                continue
            drv = self._ensure_driver(num)
            if "Tla" in info:
                drv.abbreviation = info["Tla"]
            if "FullName" in info:
                drv.full_name = info["FullName"]
            if "TeamName" in info:
                drv.team = info["TeamName"]
            if "TeamColour" in info:
                color = info["TeamColour"]
                if color and not color.startswith("#"):
                    color = f"#{color}"
                drv.team_color = color
            if "RacingNumber" in info:
                drv.number = info["RacingNumber"]

    def _handle_timing_data(self, data: dict, ts: str):
        """
        TimingData is the main timing feed.
        Format: {"Lines": {"1": {"Position": "1", "GapToLeader": "+0.5", ...}}}
        """
        lines = data.get("Lines", data)
        if not isinstance(lines, dict):
            return

        for num, info in lines.items():
            if not isinstance(info, dict):
                continue
            drv = self._ensure_driver(num)

            if "Position" in info:
                try:
                    drv.position = int(info["Position"])
                except (ValueError, TypeError):
                    pass

            if "GapToLeader" in info:
                val = info["GapToLeader"]
                if isinstance(val, dict):
                    drv.gap_to_leader = val.get("Value", "")
                else:
                    drv.gap_to_leader = str(val)

            if "IntervalToPositionAhead" in info:
                val = info["IntervalToPositionAhead"]
                if isinstance(val, dict):
                    drv.interval = val.get("Value", "")
                else:
                    drv.interval = str(val)

            if "LastLapTime" in info:
                val = info["LastLapTime"]
                if isinstance(val, dict):
                    drv.last_lap = val.get("Value", "")
                    drv.last_lap_personal_best = val.get("PersonalFastest", False)
                    drv.last_lap_overall_best = val.get("OverallFastest", False)
                else:
                    drv.last_lap = str(val)

            if "BestLapTime" in info:
                val = info["BestLapTime"]
                if isinstance(val, dict):
                    drv.best_lap = val.get("Value", "")
                else:
                    drv.best_lap = str(val)

            # Sectors
            if "Sectors" in info:
                sectors = info["Sectors"]
                if isinstance(sectors, dict):
                    for sec_key, sec_data in sectors.items():
                        if not isinstance(sec_data, dict):
                            continue
                        sec_idx = int(sec_key) if sec_key.isdigit() else -1
                        val = sec_data.get("Value", "")
                        pb = sec_data.get("PersonalFastest", False)
                        ob = sec_data.get("OverallFastest", False)
                        if sec_idx == 0:
                            drv.sector_1 = val
                            drv.sector_1_personal_best = pb
                            drv.sector_1_overall_best = ob
                        elif sec_idx == 1:
                            drv.sector_2 = val
                            drv.sector_2_personal_best = pb
                            drv.sector_2_overall_best = ob
                        elif sec_idx == 2:
                            drv.sector_3 = val
                            drv.sector_3_personal_best = pb
                            drv.sector_3_overall_best = ob

            if "InPit" in info:
                drv.in_pit = info["InPit"] in (True, "true", "True")
            if "PitOut" in info:
                drv.pit_out = info["PitOut"] in (True, "true", "True")
            if "Retired" in info:
                drv.retired = info["Retired"] in (True, "true", "True")
            if "Stopped" in info:
                drv.stopped = info["Stopped"] in (True, "true", "True")
            if "NumberOfLaps" in info:
                try:
                    drv.num_laps = int(info["NumberOfLaps"])
                except (ValueError, TypeError):
                    pass
            if "NumberOfPitStops" in info:
                try:
                    drv.num_pit_stops = int(info["NumberOfPitStops"])
                except (ValueError, TypeError):
                    pass

    def _handle_timing_app_data(self, data: dict, ts: str):
        """TimingAppData contains tyre compound and stint info."""
        lines = data.get("Lines", data)
        if not isinstance(lines, dict):
            return

        for num, info in lines.items():
            if not isinstance(info, dict):
                continue
            drv = self._ensure_driver(num)
            
            stints = info.get("Stints", {})
            if isinstance(stints, dict) and stints:
                # Get the latest stint
                latest_key = max(stints.keys(), key=lambda k: int(k) if k.isdigit() else 0)
                stint = stints.get(latest_key, {})
                if isinstance(stint, dict):
                    if "Compound" in stint:
                        drv.tyre_compound = stint["Compound"]
                    if "TotalLaps" in stint:
                        try:
                            drv.tyre_age = int(stint["TotalLaps"])
                        except (ValueError, TypeError):
                            pass

    def _handle_timing_stats(self, data: dict, ts: str):
        """TimingStats contains personal best and overall best sector times."""
        lines = data.get("Lines", data)
        if not isinstance(lines, dict):
            return
        # Mainly used for stats, we already get PB/OB flags from TimingData

    def _handle_clock(self, data: dict, ts: str):
        """ExtrapolatedClock provides the session countdown timer."""
        if "Remaining" in data:
            self.clock_remaining = data["Remaining"]
        if "Extrapolating" in data:
            self.clock_extrapolating = data["Extrapolating"]

    def _handle_lap_count(self, data: dict, ts: str):
        """LapCount for race sessions."""
        if "CurrentLap" in data:
            try:
                self.current_lap = int(data["CurrentLap"])
            except (ValueError, TypeError):
                pass
        if "TotalLaps" in data:
            try:
                self.total_laps = int(data["TotalLaps"])
            except (ValueError, TypeError):
                pass

    def _handle_track_status(self, data: dict, ts: str):
        """
        TrackStatus: status code + message.
        Codes: 1=Clear, 2=Yellow, 3=??, 4=SC, 5=Red, 6=VSC, 7=VSCEnding
        """
        status_names = {
            "1": "🟢 All Clear",
            "2": "🟡 Yellow Flag",
            "3": "⚠️  Flag",
            "4": "🟠 Safety Car",
            "5": "🔴 Red Flag",
            "6": "🟡 Virtual Safety Car",
            "7": "🟢 VSC Ending",
        }
        if "Status" in data:
            self.track_status = str(data["Status"])
            self.track_status_message = status_names.get(
                self.track_status, f"Status {self.track_status}"
            )
        if "Message" in data:
            self.track_status_message = data["Message"]

    def _handle_weather(self, data: dict, ts: str):
        """WeatherData: temperatures, humidity, wind, rain."""
        if "AirTemp" in data:
            self.air_temp = f"{data['AirTemp']}°C"
        if "TrackTemp" in data:
            self.track_temp = f"{data['TrackTemp']}°C"
        if "Humidity" in data:
            self.humidity = f"{data['Humidity']}%"
        if "WindSpeed" in data:
            self.wind_speed = f"{data['WindSpeed']} km/h"
        if "Rainfall" in data:
            self.rainfall = data["Rainfall"] in (True, "1", 1, "true")

    def _handle_race_control(self, data: dict, ts: str):
        """RaceControlMessages: penalties, investigations, flags, DRS."""
        messages = data.get("Messages", data)
        if isinstance(messages, dict):
            for key, msg_data in messages.items():
                if not isinstance(msg_data, dict):
                    continue
                rcm = RaceControlMessage(
                    timestamp=msg_data.get("Utc", ts),
                    message=msg_data.get("Message", ""),
                    category=msg_data.get("Category", ""),
                    flag=msg_data.get("Flag", ""),
                )
                if rcm.message:
                    self.race_control_messages.insert(0, rcm)
        # Keep only last 50 messages
        self.race_control_messages = self.race_control_messages[:50]

    def _handle_session_info(self, data: dict, ts: str):
        """SessionInfo: GP name, session name, track."""
        meeting = data.get("Meeting", {})
        if isinstance(meeting, dict):
            if "Name" in meeting:
                self.gp_name = meeting["Name"]
            if "OfficialName" in meeting:
                self.gp_name = meeting["OfficialName"]
            circuit = meeting.get("Circuit", {})
            if isinstance(circuit, dict) and "ShortName" in circuit:
                self.track_name = circuit["ShortName"]
        if "Name" in data:
            self.session_name = data["Name"]
        if "Type" in data:
            self.session_type = data["Type"]

    def _handle_session_data(self, data: dict, ts: str):
        """SessionData: series status changes."""
        pass  # Not critical for MVP

    def _handle_session_status(self, data: dict, ts: str):
        """SessionStatus: Started, Finished, etc."""
        pass  # Not critical for MVP

    def _handle_top_three(self, data: dict, ts: str):
        """TopThree: quick reference to top 3 drivers."""
        pass  # We already have full timing data
