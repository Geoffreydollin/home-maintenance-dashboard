#!/usr/bin/env bash
#
# update.sh -- pull the latest code and restart the services.
# Your task data (data/tasks.json) is gitignored, so it is never touched.
#
set -euo pipefail
APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APPDIR"

echo "==> Pulling latest..."
git pull --ff-only

# Reinstall deps only if requirements changed (cheap to just run it).
if [ -d "$APPDIR/.venv" ]; then
  "$APPDIR/.venv/bin/pip" install -q -r requirements.txt
fi

echo "==> Restarting services..."
sudo systemctl restart home-dashboard.service
sudo systemctl restart home-dashboard-kiosk.service
echo "==> Done."
