# VideoCall Light Manager

Automatically detects webcam usage and notifies Home Assistant — via MQTT (with Auto-Discovery) and/or Webhook.

**Use case:** Smart lighting that automatically reacts when a video call starts or ends.

*[Deutsche Version](README.de.md)*

## How it works

The daemon periodically scans `/proc/[pid]/fd/` to check whether any process has a video device (`/dev/video*`) open. On a state change (camera on/off), configurable actions are triggered.

```
Webcam access detected
        │
        ▼
  CameraMonitor
  (Debounce filter)
        │
   ┌────┴────┐
   ▼         ▼
 MQTT      HA Webhook
 (ON/OFF)  (Automation)
```

## Features

- **No root required** — only reads `/proc` of the current user
- **MQTT Auto-Discovery** — device appears automatically in Home Assistant
- **Debounce filter** — prevents flickering from brief camera accesses (e.g. browser permission checks)
- **Last Will Testament** — broker publishes `OFF` on unexpected crash
- **Systemd user service** — starts with the user session, no root daemon needed
- **HA Webhook** — directly triggers HA automations
- **Auto-reconnect** — MQTT connection is automatically re-established

## Installation

### Requirements

- Python 3.10+
- Home Assistant with MQTT integration (Mosquitto or similar)
- Linux (tested on Ubuntu/Debian)

### Step 1: Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/VideoCall_LightManager.git
cd VideoCall_LightManager
```

### Step 2: Create your configuration

```bash
cp config.yaml.example config.yaml
```

Then edit `config.yaml`:

| Parameter | Description |
|---|---|
| `mqtt.broker` | IP/hostname of the MQTT broker |
| `mqtt.username` / `mqtt.password` | MQTT credentials |
| `homeassistant.url` | URL of your HA instance |
| `homeassistant.token` | Long-Lived Access Token (HA → Profile → Tokens) |
| `camera.debounce_polls` | Stable polls required before state change (default: 2) |

### Step 3: Install

```bash
chmod +x install.sh
./install.sh
```

The script creates the virtual environment, installs dependencies, and sets up the systemd user service.

### Service management

```bash
systemctl --user status videocall-lightmanager
systemctl --user restart videocall-lightmanager
journalctl --user -u videocall-lightmanager -f
```

### Autostart without login (optional)

```bash
loginctl enable-linger $USER
```

## Home Assistant — MQTT Auto-Discovery

On startup, the daemon automatically publishes discovery payloads. In HA, the device **VideoCall LightManager** appears under **Settings → Devices & Services → MQTT** with two entities:

| Entity | Type | Topic |
|---|---|---|
| Video Call Active | `binary_sensor` (device_class: running) | `home/office/videocall/state` |
| Video Call Camera Device | `sensor` | `home/office/videocall/camera` |

## Home Assistant — Webhook Automation

Create an automation in HA with a Webhook trigger:

- **Trigger:** Webhook → ID: `videocall_started` (or `videocall_ended`)
- **Action:** e.g. turn on lights / activate a scene

## Configuration reference

```yaml
camera:
  devices: "/dev/video*"     # Glob pattern for camera devices
  poll_interval: 2.0         # Seconds between polls
  debounce_polls: 2          # Stable polls required before state change

mqtt:
  enabled: true
  broker: "192.168.1.100"
  port: 1883
  username: ""
  password: ""
  ca_certs: ""               # Path to CA certificate for TLS
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
  file: ""                   # Empty = journald only
```

## License

MIT
