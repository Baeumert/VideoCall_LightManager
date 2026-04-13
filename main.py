#!/usr/bin/env python3
"""main.py — VideoCall Light Manager daemon entry point."""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import signal
import sys
import time
from pathlib import Path
from typing import Optional

# Allow running directly from the project root
sys.path.insert(0, str(Path(__file__).parent))

from videocall_lightmanager.camera_monitor import CameraMonitor
from videocall_lightmanager.config_loader import AppConfig
from videocall_lightmanager.ha_client import HAClient
from videocall_lightmanager.mqtt_client import MQTTPublisher

log = logging.getLogger("videocall_lightmanager")

_running = True


def _handle_signal(signum, frame) -> None:
    global _running
    log.info("Received signal %d — shutting down.", signum)
    _running = False


def setup_logging(cfg_logging) -> None:
    level = getattr(logging, cfg_logging.level, logging.INFO)
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handlers: list[logging.Handler] = []

    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(level)
    stream.setFormatter(fmt)
    handlers.append(stream)

    if cfg_logging.file:
        fh = logging.handlers.RotatingFileHandler(
            cfg_logging.file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
        fh.setLevel(level)
        fh.setFormatter(fmt)
        handlers.append(fh)

    root = logging.getLogger()
    root.setLevel(level)
    for h in handlers:
        root.addHandler(h)


def main() -> None:
    parser = argparse.ArgumentParser(description="VideoCall Light Manager")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml (default: ./config.yaml)",
    )
    args = parser.parse_args()

    # Load and validate configuration
    try:
        cfg = AppConfig.from_yaml(args.config)
    except FileNotFoundError:
        print(f"ERROR: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    setup_logging(cfg.logging)
    log.info("VideoCall Light Manager starting. Config: %s", args.config)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Initialise components
    monitor = CameraMonitor(cfg.camera.devices, debounce_polls=cfg.camera.debounce_polls)

    mqtt_pub: Optional[MQTTPublisher] = None
    if cfg.mqtt.enabled:
        mqtt_pub = MQTTPublisher(cfg.mqtt)
        mqtt_pub.start()

    ha_client: Optional[HAClient] = None
    if cfg.ha.enabled:
        ha_client = HAClient(cfg.ha)

    log.info(
        "Poll interval: %.1fs | MQTT: %s | HA API: %s",
        cfg.camera.poll_interval,
        "enabled" if mqtt_pub else "disabled",
        "enabled" if ha_client else "disabled",
    )

    # Main polling loop
    try:
        while _running:
            changed, state = monitor.poll()

            # Only trigger on real ON/OFF transitions (not the first poll)
            if changed is True:
                primary_device = (
                    sorted(state.devices_in_use)[0] if state.devices_in_use else ""
                )
                if mqtt_pub:
                    mqtt_pub.publish_state(active=state.active, device=primary_device)
                if ha_client:
                    ha_client.trigger(active=state.active)

            time.sleep(cfg.camera.poll_interval)

    finally:
        log.info("Cleaning up...")
        if mqtt_pub:
            mqtt_pub.stop()
        if ha_client:
            ha_client.close()
        log.info("VideoCall Light Manager stopped.")


if __name__ == "__main__":
    main()
