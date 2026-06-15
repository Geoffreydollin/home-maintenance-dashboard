#!/usr/bin/env bash
#
# setup.sh -- one-shot installer for the Home Maintenance Dashboard on a
# fresh-ish Raspberry Pi OS (Bookworm or later, 64-bit recommended).
#
# What it does:
#   1. Installs system packages (Chromium, cage kiosk compositor, Python venv)
#   2. Creates a Python virtualenv and installs Flask
#   3. Installs and enables two systemd services:
#        - home-dashboard.service        (the Flask backend)
#        - home-dashboard-kiosk.service  (cage + Chromium full-screen)
#
# Re-running it is safe (idempotent): it just re-templates and re-enables.
#
# Usage:   cd into the repo, then:  ./setup.sh
#
set -euo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="${SUDO_USER:-$USER}"

echo "==> App directory : $APPDIR"
echo "==> Kiosk user    : $RUN_USER"

# --------------------------------------------------------------------------- #
# 1. System packages
# --------------------------------------------------------------------------- #
echo "==> Installing system packages (needs sudo)..."
sudo apt-get update
# chromium / chromium-browser naming varies by image; install whichever exists.
CHROMIUM_PKG="chromium-browser"
if ! apt-cache show chromium-browser >/dev/null 2>&1; then
  CHROMIUM_PKG="chromium"
fi
sudo apt-get install -y \
  "$CHROMIUM_PKG" \
  cage \
  python3 \
  python3-venv \
  python3-pip \
  curl

# --------------------------------------------------------------------------- #
# 2. Python virtualenv
# --------------------------------------------------------------------------- #
echo "==> Creating virtualenv and installing dependencies..."
if [ ! -d "$APPDIR/.venv" ]; then
  python3 -m venv "$APPDIR/.venv"
fi
"$APPDIR/.venv/bin/pip" install --upgrade pip >/dev/null
"$APPDIR/.venv/bin/pip" install -r "$APPDIR/requirements.txt"

# --------------------------------------------------------------------------- #
# 3. systemd services
# --------------------------------------------------------------------------- #
echo "==> Installing systemd services..."
chmod +x "$APPDIR/deploy/start-kiosk.sh"

install_unit() {
  local src="$1" dest="/etc/systemd/system/$1"
  sed -e "s#__APPDIR__#${APPDIR}#g" \
      -e "s#__USER__#${RUN_USER}#g" \
      "$APPDIR/deploy/$src" | sudo tee "$dest" >/dev/null
  echo "    installed $dest"
}
install_unit "home-dashboard.service"
install_unit "home-dashboard-kiosk.service"

sudo systemctl daemon-reload
sudo systemctl enable --now home-dashboard.service
sudo systemctl enable home-dashboard-kiosk.service

# Make sure the Pi boots to a console (not the desktop) so cage owns tty1.
echo "==> Setting boot target to console (cage provides the display)..."
sudo systemctl set-default multi-user.target

echo
echo "============================================================"
echo " Setup complete."
echo "   Backend:  systemctl status home-dashboard.service"
echo "   Kiosk:    systemctl status home-dashboard-kiosk.service"
echo
echo " Reboot to launch the kiosk:   sudo reboot"
echo "============================================================"
