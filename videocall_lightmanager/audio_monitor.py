"""audio_monitor.py — Detect default audio output device changes via pactl.

Requires PulseAudio or PipeWire with pactl available in PATH.
No additional Python packages needed.
"""
from __future__ import annotations

import dataclasses
import logging
import subprocess

log = logging.getLogger(__name__)


@dataclasses.dataclass
class AudioOutputState:
    sink_name: str    # internal PipeWire/PulseAudio name, e.g. "bluez_output.xx_xx.1"
    description: str  # human-readable label, e.g. "My Bluetooth Headphones"


def _get_default_sink() -> str | None:
    """Return the current default sink name, or None if pactl is unavailable."""
    try:
        r = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            return r.stdout.strip() or None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _get_sink_description(sink_name: str) -> str:
    """Return the human-readable description for *sink_name*, falling back to the name."""
    try:
        r = subprocess.run(
            ["pactl", "list", "sinks"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0:
            current_name: str | None = None
            for line in r.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("Name: "):
                    current_name = stripped[6:]
                elif stripped.startswith("Description: ") and current_name == sink_name:
                    return stripped[13:]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return sink_name


def get_audio_output_state() -> AudioOutputState | None:
    """Return current default audio output, or None if pactl is unavailable."""
    sink_name = _get_default_sink()
    if not sink_name:
        return None
    return AudioOutputState(
        sink_name=sink_name,
        description=_get_sink_description(sink_name),
    )


class AudioOutputMonitor:
    """Stateful wrapper that emits events only on confirmed output-device changes.

    Uses the same debounce pattern as CameraMonitor.
    """

    def __init__(self, debounce_polls: int = 1) -> None:
        self._debounce_polls = max(1, debounce_polls)
        self._last_confirmed: str | None = None  # last emitted sink_name
        self._pending: str | None = None
        self._pending_count: int = 0

    def poll(self) -> tuple[bool | None, AudioOutputState | None]:
        """Poll once. Returns (state_changed, current_state).

        state_changed is None on the first successful poll (baseline).
        state_changed is True when a confirmed change occurred.
        state_changed is False otherwise.
        """
        state = get_audio_output_state()
        if state is None:
            log.debug("Audio output: pactl unavailable — skipping poll.")
            return False, None

        current = state.sink_name

        if self._last_confirmed is None:
            log.info(
                "Initial audio output: %s (%s)",
                state.description, state.sink_name,
            )
            self._last_confirmed = current
            self._pending = None
            self._pending_count = 0
            return None, state

        if current == self._last_confirmed:
            if self._pending is not None and self._pending != current:
                log.debug(
                    "Debounce: audio output reverted to %r before threshold (%d/%d) — suppressed",
                    current, self._pending_count, self._debounce_polls,
                )
            self._pending = None
            self._pending_count = 0
            return False, state

        if self._pending != current:
            self._pending = current
            self._pending_count = 1
        else:
            self._pending_count += 1

        log.debug(
            "Debounce: audio output candidate %r %d/%d",
            current, self._pending_count, self._debounce_polls,
        )

        if self._pending_count < self._debounce_polls:
            return False, state

        self._last_confirmed = current
        self._pending = None
        self._pending_count = 0
        log.info(
            "Audio output changed -> %s (%s)",
            state.description, state.sink_name,
        )
        return True, state
