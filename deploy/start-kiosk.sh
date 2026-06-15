#!/usr/bin/env bash
#
# start-kiosk.sh
# Waits for the Flask backend to come up, then launches Chromium full-screen
# in kiosk mode pointed at the local dashboard. Intended to be run *inside* the
# `cage` Wayland compositor (see deploy/home-dashboard-kiosk.service), but works
# under a normal desktop session too if you just want to test it.
#
set -euo pipefail

URL="http://127.0.0.1:5000"

# Wait (up to ~60s) for the backend to start serving before opening the browser,
# so the first paint is never a "connection refused" page.
for _ in $(seq 1 60); do
  if curl -sf "$URL" >/dev/null 2>&1; then break; fi
  sleep 1
done

# Raspberry Pi OS ships the browser as either `chromium-browser` or `chromium`.
CHROMIUM="$(command -v chromium-browser || command -v chromium || true)"
if [ -z "$CHROMIUM" ]; then
  echo "Chromium not found (install chromium-browser)." >&2
  exit 1
fi

# A fresh profile dir keeps kiosk state clean across reboots.
PROFILE="${HOME}/.cache/home-dashboard-chromium"
mkdir -p "$PROFILE"

exec "$CHROMIUM" \
  --kiosk "$URL" \
  --user-data-dir="$PROFILE" \
  --ozone-platform=wayland \
  --window-size=1024,600 \
  --start-fullscreen \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --disable-features=TranslateUI,Translate \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  --hide-scrollbars
