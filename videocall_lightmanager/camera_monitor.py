"""camera_monitor.py — Detect webcam usage via /proc/[pid]/fd/ symlinks.

No root required. Works for any process running as the same user (e.g. browser).
"""
from __future__ import annotations

import dataclasses
import glob
import logging
import os
from typing import Dict, Set

log = logging.getLogger(__name__)


@dataclasses.dataclass
class CameraState:
    active: bool                          # True if any camera is in use
    devices_in_use: Set[str]              # e.g. {'/dev/video0'}
    pids_by_device: Dict[str, Set[int]]   # e.g. {'/dev/video0': {1234}}


def _resolve_video_devices(pattern: str) -> Set[str]:
    """Resolve a glob pattern to a set of device paths (raw + realpath)."""
    devices: Set[str] = set()
    for path in glob.glob(pattern):
        devices.add(path)
        try:
            devices.add(os.path.realpath(path))
        except OSError:
            pass
    return devices


def scan_camera_usage(device_glob: str) -> CameraState:
    """Scan /proc filesystem for processes that have a video device open.

    PermissionError on other-user processes is silently skipped (expected).
    FileNotFoundError is silently skipped (process exited during scan).
    """
    video_devices = _resolve_video_devices(device_glob)

    if not video_devices:
        log.debug("No video devices found matching: %s", device_glob)
        return CameraState(active=False, devices_in_use=set(), pids_by_device={})

    log.debug("Scanning for usage of: %s", video_devices)

    pids_by_device: Dict[str, Set[int]] = {}
    devices_in_use: Set[str] = set()

    for proc_fd_path in glob.iglob("/proc/[0-9]*/fd"):
        pid_str = proc_fd_path.split("/")[2]

        try:
            fd_entries = os.listdir(proc_fd_path)
        except PermissionError:
            continue
        except FileNotFoundError:
            continue

        for fd_name in fd_entries:
            fd_full = os.path.join(proc_fd_path, fd_name)
            try:
                target = os.readlink(fd_full)
            except OSError:
                continue

            # Match raw target first, then resolved realpath
            if target in video_devices:
                matched = target
            else:
                try:
                    real = os.path.realpath(target)
                except OSError:
                    continue
                if real in video_devices:
                    matched = real
                else:
                    continue

            pid = int(pid_str)
            pids_by_device.setdefault(matched, set()).add(pid)
            devices_in_use.add(matched)

    active = bool(devices_in_use)
    if active:
        log.debug(
            "Camera(s) in use: %s",
            {dev: sorted(pids) for dev, pids in pids_by_device.items()},
        )

    return CameraState(
        active=active,
        devices_in_use=devices_in_use,
        pids_by_device=pids_by_device,
    )


class CameraMonitor:
    """Stateful wrapper that emits events only on confirmed ON <-> OFF transitions.

    A transition is only emitted after the new state has been observed for
    `debounce_polls` consecutive polls. This prevents brief camera flickers
    (e.g. a process opening the device for 1-2 seconds) from triggering
    spurious webhooks / MQTT messages.
    """

    def __init__(self, device_glob: str, debounce_polls: int = 2) -> None:
        self._device_glob = device_glob
        self._debounce_polls = max(1, debounce_polls)
        self._last_confirmed: bool | None = None  # last emitted state
        self._pending: bool | None = None          # candidate new state
        self._pending_count: int = 0               # how many polls it has held

    def poll(self) -> tuple[bool | None, CameraState]:
        """Poll once. Returns (state_changed, current_raw_state).

        state_changed is None on the very first poll.
        state_changed is True when a confirmed transition occurred.
        state_changed is False otherwise (including debounce accumulation).
        """
        state = scan_camera_usage(self._device_glob)
        current = state.active

        # First ever poll — establish baseline, no event emitted
        if self._last_confirmed is None:
            log.info(
                "Initial camera state: %s",
                "IN USE" if current else "idle",
            )
            self._last_confirmed = current
            self._pending = None
            self._pending_count = 0
            return None, state

        # Same as confirmed state → cancel any pending transition
        if current == self._last_confirmed:
            if self._pending is not None and self._pending != current:
                log.debug(
                    "Debounce: state reverted to %s before threshold (%d/%d) — suppressed",
                    "ON" if current else "OFF",
                    self._pending_count,
                    self._debounce_polls,
                )
            self._pending = None
            self._pending_count = 0
            return False, state

        # Potential new state — accumulate
        if self._pending != current:
            self._pending = current
            self._pending_count = 1
        else:
            self._pending_count += 1

        log.debug(
            "Debounce: %s candidate %d/%d",
            "ON" if current else "OFF",
            self._pending_count,
            self._debounce_polls,
        )

        if self._pending_count < self._debounce_polls:
            return False, state

        # Threshold reached → confirm transition
        self._last_confirmed = current
        self._pending = None
        self._pending_count = 0
        log.info(
            "Camera state -> %s  (devices: %s)",
            "ON" if state.active else "OFF",
            sorted(state.devices_in_use) if state.active else [],
        )
        return True, state
