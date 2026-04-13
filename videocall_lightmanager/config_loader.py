"""config_loader.py — Load and validate config.yaml"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml


@dataclasses.dataclass
class CameraConfig:
    devices: str        # glob pattern e.g. "/dev/video*"
    poll_interval: float
    debounce_polls: int  # how many consecutive polls a new state must hold before emitting


@dataclasses.dataclass
class MQTTConfig:
    enabled: bool
    broker: str
    port: int
    keepalive: int
    client_id: str
    username: str
    password: str
    ca_certs: str       # empty string = no TLS
    topic_state: str
    topic_camera: str
    discovery_enabled: bool
    discovery_prefix: str   # default: "homeassistant"


@dataclasses.dataclass
class HAWebhookConfig:
    enabled: bool
    webhook_id_on: str
    webhook_id_off: str


@dataclasses.dataclass
class HAInputBooleanConfig:
    enabled: bool
    entity_id: str


@dataclasses.dataclass
class HAConfig:
    enabled: bool
    url: str
    token: str
    webhook: HAWebhookConfig
    input_boolean: HAInputBooleanConfig


@dataclasses.dataclass
class LoggingConfig:
    level: str
    file: str           # empty = stdout only


@dataclasses.dataclass
class AppConfig:
    camera: CameraConfig
    mqtt: MQTTConfig
    ha: HAConfig
    logging: LoggingConfig

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        with open(path, "r") as f:
            raw = yaml.safe_load(f)

        cam_raw = raw.get("camera", {})
        camera = CameraConfig(
            devices=cam_raw.get("devices", "/dev/video*"),
            poll_interval=float(cam_raw.get("poll_interval", 2.0)),
            debounce_polls=int(cam_raw.get("debounce_polls", 2)),
        )

        mq_raw = raw.get("mqtt", {})
        mqtt = MQTTConfig(
            enabled=bool(mq_raw.get("enabled", False)),
            broker=mq_raw.get("broker", ""),
            port=int(mq_raw.get("port", 1883)),
            keepalive=int(mq_raw.get("keepalive", 60)),
            client_id=mq_raw.get("client_id", "videocall-lightmanager"),
            username=mq_raw.get("username", ""),
            password=mq_raw.get("password", ""),
            ca_certs=mq_raw.get("ca_certs", ""),
            topic_state=mq_raw.get("topic_state", "home/office/videocall/state"),
            topic_camera=mq_raw.get("topic_camera", "home/office/videocall/camera"),
            discovery_enabled=bool(mq_raw.get("discovery_enabled", True)),
            discovery_prefix=mq_raw.get("discovery_prefix", "homeassistant"),
        )

        ha_raw = raw.get("homeassistant", {})
        wh_raw = ha_raw.get("webhook", {})
        ib_raw = ha_raw.get("input_boolean", {})
        ha = HAConfig(
            enabled=bool(ha_raw.get("enabled", False)),
            url=ha_raw.get("url", ""),
            token=ha_raw.get("token", ""),
            webhook=HAWebhookConfig(
                enabled=bool(wh_raw.get("enabled", False)),
                webhook_id_on=wh_raw.get("webhook_id_on", ""),
                webhook_id_off=wh_raw.get("webhook_id_off", ""),
            ),
            input_boolean=HAInputBooleanConfig(
                enabled=bool(ib_raw.get("enabled", False)),
                entity_id=ib_raw.get("entity_id", ""),
            ),
        )

        log_raw = raw.get("logging", {})
        logging_cfg = LoggingConfig(
            level=log_raw.get("level", "INFO").upper(),
            file=log_raw.get("file", ""),
        )

        cfg = cls(camera=camera, mqtt=mqtt, ha=ha, logging=logging_cfg)
        cfg._validate()
        return cfg

    def _validate(self) -> None:
        errors = []
        if self.mqtt.enabled and not self.mqtt.broker:
            errors.append("mqtt.broker must be set when mqtt.enabled is true")
        if self.ha.enabled and not self.ha.url:
            errors.append("homeassistant.url must be set when homeassistant.enabled is true")
        if self.ha.enabled and not self.ha.token:
            errors.append("homeassistant.token must be set when homeassistant.enabled is true")
        if not self.mqtt.enabled and not self.ha.enabled:
            errors.append("At least one of mqtt or homeassistant must be enabled")
        if errors:
            raise ValueError(
                "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            )
