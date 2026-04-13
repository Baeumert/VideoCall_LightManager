"""ha_client.py — HomeAssistant REST API and Webhook client."""
from __future__ import annotations

import logging

import requests

from .config_loader import HAConfig

log = logging.getLogger(__name__)

_TIMEOUT = 5  # seconds per request


class HAClient:
    def __init__(self, config: HAConfig) -> None:
        self._cfg = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {config.token}",
                "Content-Type": "application/json",
            }
        )

    def trigger(self, active: bool) -> None:
        """Trigger all enabled HA integration methods for the given state."""
        if not self._cfg.enabled:
            return
        if self._cfg.webhook.enabled:
            self._trigger_webhook(active)
        if self._cfg.input_boolean.enabled:
            self._set_input_boolean(active)

    def _base_url(self) -> str:
        return self._cfg.url.rstrip("/")

    def _trigger_webhook(self, active: bool) -> None:
        webhook_id = (
            self._cfg.webhook.webhook_id_on if active else self._cfg.webhook.webhook_id_off
        )
        if not webhook_id:
            log.warning("Webhook ID not configured for state %s", "ON" if active else "OFF")
            return

        url = f"{self._base_url()}/api/webhook/{webhook_id}"
        log.debug("HA webhook POST %s", url)
        try:
            resp = self._session.post(
                url,
                json={"state": "ON" if active else "OFF"},
                timeout=_TIMEOUT,
            )
            if resp.status_code in (200, 201, 204):
                log.info(
                    "HA webhook triggered: %s (state=%s)",
                    webhook_id,
                    "ON" if active else "OFF",
                )
            else:
                log.error(
                    "HA webhook failed: HTTP %d — %s",
                    resp.status_code,
                    resp.text[:200],
                )
        except requests.RequestException as exc:
            log.error("HA webhook request error: %s", exc)

    def _set_input_boolean(self, active: bool) -> None:
        service = "turn_on" if active else "turn_off"
        url = f"{self._base_url()}/api/services/input_boolean/{service}"
        payload = {"entity_id": self._cfg.input_boolean.entity_id}

        log.debug("HA input_boolean POST %s payload=%s", url, payload)
        try:
            resp = self._session.post(url, json=payload, timeout=_TIMEOUT)
            if resp.status_code in (200, 201):
                log.info(
                    "HA input_boolean.%s called for %s",
                    service,
                    self._cfg.input_boolean.entity_id,
                )
            else:
                log.error(
                    "HA input_boolean failed: HTTP %d — %s",
                    resp.status_code,
                    resp.text[:200],
                )
        except requests.RequestException as exc:
            log.error("HA input_boolean request error: %s", exc)

    def close(self) -> None:
        self._session.close()
