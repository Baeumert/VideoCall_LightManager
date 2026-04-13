#!/usr/bin/env bash
# install.sh — VideoCall Light Manager Installations-Skript
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="videocall-lightmanager"
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "=== VideoCall Light Manager — Installation ==="
echo "Projektverzeichnis: $SCRIPT_DIR"

# 1. Virtuelle Umgebung erstellen
echo ""
echo "[1/5] Erstelle Python-Virtual-Environment..."
python3 -m venv "$SCRIPT_DIR/venv"

# 2. Abhängigkeiten installieren
echo "[2/5] Installiere Abhängigkeiten..."
"$SCRIPT_DIR/venv/bin/pip" install --quiet --upgrade pip
"$SCRIPT_DIR/venv/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "      Installiert:"
"$SCRIPT_DIR/venv/bin/pip" list | grep -E "paho|PyYAML|requests"

# 3. Kameraerkennung testen
echo ""
echo "[3/5] Teste Kameraerkennung..."
"$SCRIPT_DIR/venv/bin/python" -c "
import glob, sys
sys.path.insert(0, '$SCRIPT_DIR')
from videocall_lightmanager.camera_monitor import scan_camera_usage

devices = glob.glob('/dev/video*')
print(f'      Gefundene Geräte: {devices}')
state = scan_camera_usage('/dev/video*')
print(f'      Kamera aktiv:     {state.active}')
if state.active:
    print(f'      In Benutzung:     {list(state.devices_in_use)}')
"

# 4. Config validieren
echo ""
echo "[4/5] Validiere config.yaml..."
"$SCRIPT_DIR/venv/bin/python" -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from videocall_lightmanager.config_loader import AppConfig
try:
    cfg = AppConfig.from_yaml('$SCRIPT_DIR/config.yaml')
    print(f'      Config OK — Poll: {cfg.camera.poll_interval}s | MQTT: {cfg.mqtt.enabled} | HA: {cfg.ha.enabled}')
except ValueError as e:
    print(f'      Config-Fehler: {e}', file=sys.stderr)
    print('      Bitte config.yaml anpassen und erneut installieren.', file=sys.stderr)
    sys.exit(1)
"

# 5. systemd User-Service installieren
echo ""
echo "[5/5] Installiere systemd User-Service..."
mkdir -p "$USER_SYSTEMD_DIR"

# Ersetze Pfade im Service-File falls nötig
sed "s|/home/it-viking/VideoCall_LightManger|$SCRIPT_DIR|g" \
    "$SCRIPT_DIR/${SERVICE_NAME}.service" \
    > "$USER_SYSTEMD_DIR/${SERVICE_NAME}.service"

echo "      Installiert: $USER_SYSTEMD_DIR/${SERVICE_NAME}.service"

systemctl --user daemon-reload
systemctl --user enable "${SERVICE_NAME}.service"
systemctl --user start "${SERVICE_NAME}.service"

echo ""
echo "=== Installation abgeschlossen ==="
echo ""
echo "Verwaltungsbefehle:"
echo "  Status:    systemctl --user status ${SERVICE_NAME}"
echo "  Logs:      journalctl --user -u ${SERVICE_NAME} -f"
echo "  Neustart:  systemctl --user restart ${SERVICE_NAME}"
echo "  Stoppen:   systemctl --user stop ${SERVICE_NAME}"
echo "  Entfernen: systemctl --user disable --now ${SERVICE_NAME}"
echo ""
echo "Tipp: Damit der Service auch ohne Login startet (z.B. für Remote-Arbeit):"
echo "  loginctl enable-linger \$USER"
