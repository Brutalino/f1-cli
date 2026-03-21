"""
Custom F1 Live Timing client.

Based on FastF1's SignalRClient but routes messages to our DataStore
for real-time processing, while optionally also saving to file.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable, Optional

import requests
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.messages.completion_message import CompletionMessage

import fastf1
from fastf1.internals.f1auth import get_auth_token

from .data_store import DataStore


class F1LiveClient:
    """
    A live timing client that feeds data into a DataStore in real-time.
    
    Unlike FastF1's built-in SignalRClient (which only writes to a file),
    this client processes each message as it arrives and updates a shared
    DataStore that the TUI reads from.
    """

    _connection_url = 'wss://livetiming.formula1.com/signalrcore'
    _negotiate_url = 'https://livetiming.formula1.com/signalrcore/negotiate'

    TOPICS = [
        "Heartbeat", "AudioStreams", "DriverList",
        "ExtrapolatedClock", "RaceControlMessages",
        "SessionInfo", "SessionStatus", "TeamRadio",
        "TimingAppData", "TimingStats", "TrackStatus",
        "WeatherData", "Position.z", "CarData.z",
        "ContentStreams", "SessionData", "TimingData",
        "TopThree", "RcmSeries", "LapCount",
    ]

    def __init__(
        self,
        store: DataStore,
        save_file: Optional[str] = None,
        no_auth: bool = False,
        timeout: int = 120,
        on_status_change: Optional[Callable[[str], None]] = None,
    ):
        self.store = store
        self.save_file = save_file
        self._no_auth = no_auth
        self.timeout = timeout
        self._on_status_change = on_status_change

        self.headers: dict = {}
        self._connection = None
        self._is_connected = False
        self._should_stop = False
        self._output_file = None
        self._t_last_message = time.time()
        self._thread: Optional[threading.Thread] = None

        self.logger = logging.getLogger("F1LiveClient")
        self.logger.setLevel(logging.WARNING)

    def _notify_status(self, status: str):
        """Notify the app of a connection status change."""
        if self._on_status_change:
            try:
                self._on_status_change(status)
            except Exception:
                pass

    def _on_message(self, msg: list | CompletionMessage):
        """Handle an incoming SignalR message."""
        self._t_last_message = time.time()

        try:
            if isinstance(msg, CompletionMessage):
                # Initial subscription response — contains full state dump
                if msg.result:
                    for topic, payload in msg.result.items():
                        self.store.process_message(topic, payload)
                        self._write_to_file(topic, payload)

            elif isinstance(msg, list):
                # Incremental update: [topic, data, timestamp]
                if len(msg) >= 2:
                    topic = msg[0]
                    data = msg[1]
                    timestamp = msg[2] if len(msg) > 2 else ""
                    self.store.process_message(topic, data, timestamp)
                    self._write_to_file(topic, data, timestamp)

        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def _write_to_file(self, topic: str, data, timestamp: str = ""):
        """Optionally save raw data to file for later replay."""
        if self._output_file:
            try:
                line = str([topic, json.dumps(data) if not isinstance(data, str) else data, timestamp])
                self._output_file.write(line + "\n")
                self._output_file.flush()
            except Exception:
                pass

    def _on_connect(self):
        self._is_connected = True
        self.store.is_connected = True
        self._notify_status("connected")
        self.logger.info("Connected to F1 live timing")

    def _on_close(self):
        self._is_connected = False
        self.store.is_connected = False
        self._notify_status("disconnected")
        self.logger.info("Disconnected from F1 live timing")

    def _run(self):
        """Set up and start the SignalR connection."""
        if self.save_file:
            self._output_file = open(self.save_file, "w")

        self._notify_status("connecting")

        try:
            # Pre-negotiate for AWSALBCORS cookie
            r = requests.options(self._negotiate_url, headers=self.headers)
            if "AWSALBCORS" in r.cookies:
                self.headers["Cookie"] = f"AWSALBCORS={r.cookies['AWSALBCORS']}"
        except Exception as e:
            self.logger.warning(f"Negotiate failed: {e}")

        # Build SignalR connection
        options = {
            "verify_ssl": True,
            "access_token_factory": None if self._no_auth else get_auth_token,
            "headers": self.headers,
        }

        self._connection = (
            HubConnectionBuilder()
            .with_url(self._connection_url, options=options)
            .configure_logging(logging.WARNING)
            .build()
        )

        self._connection.on_open(self._on_connect)
        self._connection.on_close(self._on_close)
        self._connection.on("feed", self._on_message)

        self._connection.start()

        # Wait for connection
        t_start = time.time()
        while not self._is_connected and not self._should_stop:
            if time.time() - t_start > 30:
                self._notify_status("timeout")
                return
            time.sleep(0.1)

        if self._is_connected:
            self._connection.send(
                "Subscribe", [self.TOPICS], on_invocation=self._on_message
            )

    def _supervise(self):
        """Monitor connection health."""
        while not self._should_stop:
            if (
                self.timeout > 0
                and self._is_connected
                and time.time() - self._t_last_message > self.timeout
            ):
                self._notify_status("timeout")
                break
            time.sleep(1)

    def start_background(self):
        """Start the client in a background thread."""
        self._should_stop = False

        def _worker():
            try:
                self._run()
                self._supervise()
            except Exception as e:
                self.logger.error(f"Client error: {e}")
                self._notify_status(f"error: {e}")
            finally:
                self.stop()

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the client gracefully."""
        self._should_stop = True
        if self._connection:
            try:
                self._connection.stop()
            except Exception:
                pass
        if self._output_file:
            try:
                self._output_file.close()
            except Exception:
                pass
        self.store.is_connected = False
