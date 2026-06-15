# Home Maintenance Dashboard

A self-contained, touch-friendly home maintenance tracker built to run full-screen
(kiosk mode) on a Raspberry Pi with a 1024×600 touchscreen. It shows what home
maintenance is due, lets you mark tasks complete (which reschedules recurring
tasks automatically), and keeps a completion log — all backed by a single
human-readable JSON file, no database.

The seed task list is tailored to a Florida single-family home (pool, screen
enclosure, hurricane prep, hard-water/HVAC humidity concerns, termite bond, etc.).

---

## Table of contents

- [Architecture & why](#architecture--why)
- [Screens & features](#screens--features)
- [Quick start (any machine)](#quick-start-any-machine)
- [Raspberry Pi kiosk setup](#raspberry-pi-kiosk-setup)
- [Updating via `git pull`](#updating-via-git-pull)
- [Data file format](#data-file-format)
- [Scheduling rules](#scheduling-rules)
- [Troubleshooting](#troubleshooting)
- [Project layout](#project-layout)

---

## Architecture & why

**Python (Flask) backend serving a vanilla-JS single-page app, displayed by
Chromium in kiosk mode under the `cage` Wayland compositor.**

| Decision | Why |
|---|---|
| **Flask backend** | Tiny, mature, ~1 dependency. The backend owns all date math and the atomic JSON writes; the browser is just a renderer. |
| **Vanilla JS / HTML / CSS frontend (no framework, no build step)** | Requirement #3 is "update via `git pull` without a rebuild/compile step." There is nothing to transpile or bundle — the files Chromium loads are the files in the repo. |
| **Local JSON file storage** | Required. Human-readable, hand-editable, trivially backed up. Writes are **atomic** (temp file + `os.replace`) so a power cut mid-write can't corrupt it. |
| **Chromium kiosk under `cage`** | `cage` is a ~minimal single-app Wayland compositor. No desktop environment, taskbar, or window manager is installed or running — lower RAM/CPU (priority #1) and true kiosk with no chrome (the spec's hard requirement). |
| **systemd services** | Two units (`home-dashboard` backend + `home-dashboard-kiosk`) give reliable auto-start on boot and automatic restart on crash (priority #2). |
| **Bind to `127.0.0.1`** | The dashboard is only ever viewed on the Pi itself. Nothing is exposed to the network, so no auth is needed (and none was requested). |

**Why not Electron / a native app / a JS framework?** Each adds a compile/bundle
step (breaks the `git pull` requirement) and/or much higher memory use. A local
web app in Chromium hits every priority with the least moving parts.

The Flask development server is used in production here. That is normally
discouraged, but this is a **single local user on `127.0.0.1`** with no untrusted
traffic — the usual reasons to put gunicorn/nginx in front don't apply. If you'd
rather use a WSGI server anyway, swap the `ExecStart` in
`deploy/home-dashboard.service` for gunicorn; nothing else changes.

---

## Screens & features

- **Due Soon (default view)**
  - **Overdue** — overdue tasks, red-accented and labelled `OVERDUE`.
  - **Due this week** — next 7 days.
  - **Due within 30 days** — 8–30 days out.
- **Upcoming** — everything more than 30 days out.
- **Task detail** (tap a card) — full description, frequency, category, priority,
  DIY/Hire/Either, an `FL` badge for Florida-specific tasks, "last done" date, a
  **Watch how-to video** button when a `video_url` is present, and **Mark complete**.
- **Mark complete**
  - Recurring tasks are rescheduled to their next due date and drop off the list.
  - `as_needed` tasks are simply cleared (no new due date).
  - Every completion is logged with a timestamp.
- **Log** — chronological completion history for all tasks.
- **Settings (gear icon)** — all tasks grouped by category, where you can:
  - Change **DIY / Hire / Either**, **priority**, or **frequency** inline.
  - **Remove** a task (soft delete — `active: false`, restorable) / **Restore** it.
  - **Add to dashboard** an `as_needed` task (surfaces it as "due now").

Priority colours are consistent everywhere: **Critical = red, High = amber,
Medium = blue, Low = gray.** Touch targets are ≥44px; body text ≥16px; dark theme
for low-light/garage viewing.

---

## Quick start (any machine)

You can run the whole thing on your laptop to try it — no Pi required.

```bash
python3 -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. On first run the app creates `data/tasks.json`
from `data/seed_tasks.json`, computing each task's `next_due` relative to
**today**.

Run the tests with `python -m unittest test_scheduler`.

---

## Raspberry Pi kiosk setup

**Assumptions:** Raspberry Pi 4 or 5, Raspberry Pi OS **Bookworm** (64-bit)
fresh install, connected to the 1024×600 touchscreen, with network access for the
initial install.

```bash
# 1. Clone the repo onto the Pi (anywhere in the pi user's home)
git clone <your-repo-url> ~/home-dashboard
cd ~/home-dashboard

# 2. Run the installer (installs Chromium, cage, Python deps; sets up services)
chmod +x setup.sh
./setup.sh

# 3. Reboot — the kiosk launches automatically
sudo reboot
```

What `setup.sh` does:

1. `apt install` Chromium, **cage**, and Python venv tooling.
2. Creates `.venv` and installs Flask.
3. Templates and installs two systemd units into `/etc/systemd/system/`:
   - `home-dashboard.service` — runs `app.py` (the backend).
   - `home-dashboard-kiosk.service` — runs `cage -s -- deploy/start-kiosk.sh`,
     which waits for the backend then execs Chromium with kiosk flags.
4. Sets the default boot target to `multi-user.target` (console, no desktop) so
   `cage` owns the screen, and enables both services.

Check status any time:

```bash
systemctl status home-dashboard.service          # backend
systemctl status home-dashboard-kiosk.service    # kiosk
journalctl -u home-dashboard-kiosk.service -b     # kiosk logs this boot
```

---

## Updating via `git pull`

Because there is no build step, updates are just a pull + service restart:

```bash
cd ~/home-dashboard
./update.sh
```

`update.sh` runs `git pull`, reinstalls Python deps if needed, and restarts both
services. **Your data is safe:** `data/tasks.json` is gitignored, so it is never
overwritten by a pull. (If you only changed frontend files — HTML/CSS/JS — you can
skip the restart and just reload, but the kiosk Chromium caches little, so a quick
`sudo systemctl restart home-dashboard-kiosk.service` guarantees a fresh load.)

---

## Data file format

Two files live in `data/`:

- **`seed_tasks.json`** — the canonical task definitions, committed to git. Edit
  this to change the *default* task list shipped to a new Pi. It does **not**
  contain `next_due` (that's date-dependent and computed at first run).
- **`tasks.json`** — the live state, created on first run and **gitignored**.
  This is the file you'd hand-edit or back up. Structure:

```json
{
  "version": 1,
  "tasks": [
    {
      "id": "hvac-filter",
      "name": "HVAC air filter replacement",
      "category": "HVAC",
      "frequency": "monthly",
      "schedule": { "day_of_week": "Monday" },   // optional; see below
      "diy_status": "diy",                         // diy | hire | either
      "priority": "critical",                      // low | medium | high | critical
      "florida_specific": true,
      "active": true,                              // false = soft-deleted
      "description": "…",
      "video_url": null,                           // or a YouTube URL
      "next_due": "2026-07-15"                     // ISO date, or null for as_needed
    }
  ],
  "history": [
    { "task_id": "hvac-filter", "completed_at": "2026-06-15T11:07:48" }
  ]
}
```

Field notes:

- **`frequency`** — one of `weekly`, `twice_weekly`, `monthly`, `quarterly`,
  `biannual`, `annual`, `as_needed`.
- **`schedule`** (optional) — `{ "day_of_week": "Monday" }` for weekly tasks that
  must land on a specific weekday, or `{ "days_of_week": ["Tuesday","Friday"] }`
  for `twice_weekly`. A `time_of_day` hint may be present and is ignored by the
  scheduler.
- **`next_due`** — `null` means "not on the dashboard." `as_needed` tasks stay
  `null` until you trigger them from Settings.
- **`active: false`** — soft-deleted; hidden from the dashboard and all due-date
  math, restorable from Settings.

**To factory-reset:** stop the app, delete `data/tasks.json`, start it again — it
re-seeds from `seed_tasks.json`. Writes are atomic, so it's always safe to copy
`tasks.json` for a backup even while the app is running.

---

## Scheduling rules

When a task is marked complete, its next due date is computed from the
**completion date**:

| frequency | next due |
|---|---|
| `weekly` | next occurrence of `schedule.day_of_week`, else completion + 7 days |
| `twice_weekly` | next occurrence of any day in `schedule.days_of_week` |
| `monthly` | completion + 1 month (same day-of-month, clamped to last valid day) |
| `quarterly` | completion + 3 months |
| `biannual` | completion + 6 months |
| `annual` | completion + 12 months |
| `as_needed` | no next due — cleared from active lists, completion logged |

**First-run seeding** (relative to *today*, so it's correct whenever you clone it):

- Tasks **with a schedule** → next occurrence of the scheduled day(s), on/after today.
- Tasks **without a schedule** (and not `as_needed`) → **today**, so you see
  everything available to triage on day one.
- `as_needed` tasks → no due date; they stay off the dashboard until triggered
  from Settings.

All of this lives in [`scheduler.py`](scheduler.py) and is covered by
[`test_scheduler.py`](test_scheduler.py).

---

## Troubleshooting

**Screen blanks / goes to sleep.** Disable DPMS blanking. On Bookworm add to the
kiosk: it already passes through `cage`, but if the screen still blanks, run
`sudo raspi-config` → *Display Options* → *Screen Blanking* → off, or add
`consoleblank=0` to `/boot/firmware/cmdline.txt`.

**Display is rotated / wrong orientation.** For the framebuffer console + cage,
add `video=HDMI-A-1:1024x600@60,rotate=90` (or 180/270) to
`/boot/firmware/cmdline.txt`. For touch input rotation use the
`libinput Calibration Matrix` via an xorg/udev rule, or — simplest — rotate the
physical panel. Confirm the connector name with `cat /sys/class/drm/*/status`.

**Touch is offset / uncalibrated.** Most modern USB/DSI touchscreens work without
calibration. If taps land off-target, install `xinput-calibrator` (X) or set a
`libinput Calibration Matrix` udev rule for the touch device. Verify the device
with `libinput list-devices`.

**Chromium shows a GPU/black screen or won't start under cage.** Try forcing
software paths by adding `--disable-gpu` (and, if needed,
`--use-gl=swiftshader`) to the flags in
[`deploy/start-kiosk.sh`](deploy/start-kiosk.sh). Check
`journalctl -u home-dashboard-kiosk.service -b` for the actual error. Also make
sure the Pi has enough GPU memory (`raspi-config` → *Performance* → *GPU Memory*).

**`chromium` vs `chromium-browser`.** The flag/launcher handle both; `setup.sh`
installs whichever the image provides. If you installed Chromium yourself and the
launcher can't find it, symlink it or edit the `command -v` line in
`start-kiosk.sh`.

**Kiosk doesn't start on boot.** Confirm the boot target is console
(`systemctl get-default` → `multi-user.target`) and the unit is enabled
(`systemctl is-enabled home-dashboard-kiosk.service`). The kiosk unit takes over
`tty1`; if you also enabled the desktop autologin, disable it
(`sudo systemctl set-default multi-user.target`).

**Backend not reachable.** `systemctl status home-dashboard.service` and
`curl -sf http://127.0.0.1:5000/api/state`. The launcher waits up to 60s for the
backend, so a slow first boot is fine.

**The YouTube video button.** It opens the URL in a new Chromium tab. In strict
kiosk mode there's no tab strip, so after watching, the back/escape gesture or a
reboot returns to the dashboard. If you prefer the video to replace the dashboard
view and return via a back button instead, that's a small change in
[`static/js/app.js`](static/js/app.js) (`openDetail`'s video handler).

---

## Project layout

```
.
├── app.py                       # Flask backend + JSON API
├── scheduler.py                 # all recurrence / due-date math
├── storage.py                   # atomic JSON load/save + first-run seeding
├── test_scheduler.py            # unit tests for the date logic
├── requirements.txt             # Flask
├── data/
│   ├── seed_tasks.json          # committed task definitions (the seed)
│   └── tasks.json               # live state (generated, gitignored)
├── templates/
│   └── index.html               # single-page shell
├── static/
│   ├── css/style.css            # 1024×600 dark kiosk theme
│   └── js/app.js                # all client logic & views
├── deploy/
│   ├── home-dashboard.service        # backend systemd unit (templated)
│   ├── home-dashboard-kiosk.service  # cage+Chromium kiosk unit (templated)
│   └── start-kiosk.sh                # waits for backend, execs Chromium kiosk
├── setup.sh                     # installs deps + services (run on the Pi)
└── update.sh                    # git pull + restart services
```

### API reference (all JSON, localhost only)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/state` | Full state + server's `today`. |
| `POST` | `/api/tasks/<id>/complete` | Mark complete; reschedule or clear; log it. |
| `POST` | `/api/tasks/<id>/trigger` | Surface an `as_needed` task as due now. |
| `PATCH` | `/api/tasks/<id>` | Edit `diy_status` / `priority` / `frequency` / `active`. |
| `GET` | `/api/history` | Completion log, newest first, with task names. |
