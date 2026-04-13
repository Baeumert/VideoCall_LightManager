# VideoCall Light Manager

Erkennt automatisch, ob die Webcam aktiv genutzt wird, und benachrichtigt Home Assistant — per MQTT (mit Auto-Discovery) und/oder Webhook.

**Anwendungsfall:** Smarte Beleuchtungssteuerung die automatisch reagiert, sobald ein Videoanruf startet oder endet.

## Funktionsweise

Der Daemon liest periodisch `/proc/[pid]/fd/` aus und prüft, ob ein Prozess ein Video-Device (`/dev/video*`) geöffnet hat. Bei einem Zustandswechsel (Kamera an/aus) werden konfigurierbare Aktionen ausgelöst.

```
Webcam-Zugriff erkannt
        │
        ▼
  CameraMonitor
  (Debounce-Filter)
        │
   ┌────┴────┐
   ▼         ▼
 MQTT      HA Webhook
 (ON/OFF)  (Automatisierung)
```

## Features

- **Kein Root** erforderlich — liest nur `/proc` des eigenen Users
- **MQTT Auto-Discovery** — Gerät erscheint automatisch in Home Assistant
- **Debounce-Filter** — verhindert Flackern bei kurzen Kamerazugriffen (z.B. Browser-Prüfung)
- **Last Will Testament** — MQTT-Broker publiziert `OFF` bei unerwartetem Absturz
- **Systemd User-Service** — startet mit der User-Session, kein Root-Daemon nötig
- **HA Webhook** — löst HA-Automatisierungen direkt aus
- **Auto-Reconnect** — MQTT-Verbindung wird automatisch wiederhergestellt

## Installation

### Voraussetzungen

- Python 3.10+
- Home Assistant mit MQTT-Integration (Mosquitto o.ä.)
- Linux (getestet auf Ubuntu/Debian)

### Schritt 1: Repository klonen

```bash
git clone https://github.com/YOUR_USERNAME/VideoCall_LightManager.git
cd VideoCall_LightManager
```

### Schritt 2: Konfiguration anlegen

```bash
cp config.yaml.example config.yaml
```

Dann `config.yaml` anpassen:

| Parameter | Beschreibung |
|---|---|
| `mqtt.broker` | IP/Hostname des MQTT-Brokers |
| `mqtt.username` / `mqtt.password` | MQTT-Zugangsdaten |
| `homeassistant.url` | URL der HA-Instanz |
| `homeassistant.token` | Long-Lived Access Token (HA → Profil → Tokens) |
| `camera.debounce_polls` | Anzahl stabiler Polls vor Zustandswechsel (Standard: 2) |

### Schritt 3: Installieren

```bash
chmod +x install.sh
./install.sh
```

Das Skript erstellt die virtuelle Umgebung, installiert Abhängigkeiten und richtet den systemd User-Service ein.

### Service-Verwaltung

```bash
systemctl --user status videocall-lightmanager
systemctl --user restart videocall-lightmanager
journalctl --user -u videocall-lightmanager -f
```

### Autostart ohne Login (optional)

```bash
loginctl enable-linger $USER
```

## Home Assistant — MQTT Auto-Discovery

Nach dem Start publiziert der Daemon automatisch Discovery-Payloads. In HA erscheint unter **Einstellungen → Geräte & Dienste → MQTT** das Gerät **VideoCall LightManager** mit zwei Entitäten:

| Entität | Typ | Topic |
|---|---|---|
| Video Call Active | `binary_sensor` (device_class: running) | `home/office/videocall/state` |
| Video Call Camera Device | `sensor` | `home/office/videocall/camera` |

## Home Assistant — Webhook-Automatisierung

In HA eine Automatisierung mit Webhook-Auslöser anlegen:

- **Auslöser:** Webhook → ID: `videocall_started` (bzw. `videocall_ended`)
- **Aktion:** z.B. Licht einschalten / Szene aktivieren

## Konfigurationsreferenz

```yaml
camera:
  devices: "/dev/video*"     # Glob-Pattern für Kamerageräte
  poll_interval: 2.0         # Sekunden zwischen Abfragen
  debounce_polls: 2          # Stabile Polls vor Zustandswechsel

mqtt:
  enabled: true
  broker: "192.168.1.100"
  port: 1883
  username: ""
  password: ""
  ca_certs: ""               # Pfad zu CA-Zertifikat für TLS
  discovery_enabled: true
  discovery_prefix: "homeassistant"
  topic_state: "home/office/videocall/state"
  topic_camera: "home/office/videocall/camera"

homeassistant:
  enabled: true
  url: "http://homeassistant.local:8123"
  token: "..."
  webhook:
    enabled: true
    webhook_id_on: "videocall_started"
    webhook_id_off: "videocall_ended"
  input_boolean:
    enabled: false
    entity_id: "input_boolean.video_call_active"

logging:
  level: "INFO"              # DEBUG, INFO, WARNING, ERROR
  file: ""                   # Leer = nur journald
```

## Lizenz

MIT
