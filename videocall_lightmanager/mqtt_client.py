"""mqtt_client.py — MQTT publisher with automatic reconnect logic.

Uses paho-mqtt 2.x API (CallbackAPIVersion.VERSION2).
"""
from __future__ import annotations

import json
import logging
import threading

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from .config_loader import MQTTConfig

log = logging.getLogger(__name__)


class MQTTPublisher:
    def __init__(self, config: MQTTConfig) -> None:
        self._cfg = config
        self._connected = False
        self._lock = threading.Lock()

        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=config.client_id,
        )

        if config.username:
            self._client.username_pw_set(config.username, config.password or None)

        if config.ca_certs:
            self._client.tls_set(ca_certs=config.ca_certs)

        # Last Will Testament: broker publishes "OFF" if we disconnect ungracefully
        self._client.will_set(
            topic=config.topic_state,
            payload="OFF",
            qos=1,
            retain=True,
        )

        # Exponential backoff reconnect: 1s min → 60s max
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    # --- paho 2.x callback signatures ---

    def _publish_discovery(self) -> None:
        """Publish HA MQTT Auto-Discovery payloads for all entities."""
        prefix = self._cfg.discovery_prefix
        device = {
            "identifiers": [self._cfg.client_id],
            "name": "VideoCall LightManager",
            "model": "VideoCall LightManager",
            "manufacturer": "Custom",
        }

        # Binary sensor: ON/OFF Kamerastatus
        state_config = {
            "name": "Video Call Active",
            "unique_id": f"{self._cfg.client_id}_state",
            "state_topic": self._cfg.topic_state,
            "payload_on": "ON",
            "payload_off": "OFF",
            "device_class": "running",
            "retain": True,
            "device": device,
        }
        self._client.publish(
            topic=f"{prefix}/binary_sensor/{self._cfg.client_id}/config",
            payload=json.dumps(state_config),
            qos=1,
            retain=True,
        )
        log.info("MQTT discovery published: binary_sensor")

        # Sensor: aktives Kameragerät (/dev/videoN)
        camera_config = {
            "name": "Video Call Camera Device",
            "unique_id": f"{self._cfg.client_id}_camera",
            "state_topic": self._cfg.topic_camera,
            "icon": "mdi:webcam",
            "device": device,
        }
        self._client.publish(
            topic=f"{prefix}/sensor/{self._cfg.client_id}_camera/config",
            payload=json.dumps(camera_config),
            qos=1,
            retain=True,
        )
        log.info("MQTT discovery published: sensor (camera)")

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            log.error("MQTT connection failed: %s", reason_code)
        else:
            log.info("MQTT connected to %s:%d", self._cfg.broker, self._cfg.port)
            with self._lock:
                self._connected = True
            if self._cfg.discovery_enabled:
                self._publish_discovery()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        with self._lock:
            self._connected = False
        if reason_code != 0:
            log.warning(
                "MQTT disconnected unexpectedly (rc=%s). Auto-reconnect active.",
                reason_code,
            )
        else:
            log.info("MQTT disconnected cleanly.")

    # --- Public API ---

    def start(self) -> None:
        """Initiate async connection and start background network loop."""
        log.info("Connecting to MQTT broker %s:%d ...", self._cfg.broker, self._cfg.port)
        try:
            self._client.connect_async(
                host=self._cfg.broker,
                port=self._cfg.port,
                keepalive=self._cfg.keepalive,
            )
            self._client.loop_start()
        except Exception as exc:
            log.error("MQTT initial connect error: %s", exc)

    def stop(self) -> None:
        """Publish final OFF state, then disconnect cleanly."""
        self.publish_state(active=False, device="")
        self._client.loop_stop()
        self._client.disconnect()
        log.info("MQTT stopped.")

    def publish_state(self, active: bool, device: str) -> None:
        """Publish camera ON/OFF state. device is the /dev/videoN path."""
        payload = "ON" if active else "OFF"

        with self._lock:
            is_connected = self._connected

        if not is_connected:
            log.warning("MQTT not connected — message queued by paho for retry.")

        # paho queues internally even when disconnected
        result = self._client.publish(
            topic=self._cfg.topic_state,
            payload=payload,
            qos=1,
            retain=True,
        )
        log.debug(
            "MQTT publish %s -> %s (mid=%s)", self._cfg.topic_state, payload, result.mid
        )

        if device and active:
            self._client.publish(
                topic=self._cfg.topic_camera,
                payload=device,
                qos=0,
                retain=False,
            )
