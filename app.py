"""
app.py
======

Flask backend for the Home Maintenance Dashboard. Serves a single-page web app
(templates/index.html + static assets) and a small JSON API. All state lives in
data/tasks.json (see storage.py).

Run locally:   python app.py
On the Pi:     gunicorn-free; runs via systemd using the Flask dev server bound
               to 127.0.0.1 (single local user, kiosk only -- see README).
"""

from __future__ import annotations

from datetime import date, datetime

from flask import Flask, jsonify, render_template, request

import scheduler
import storage

app = Flask(__name__)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _find_task(state: dict, task_id: str) -> dict | None:
    for task in state["tasks"]:
        if task["id"] == task_id:
            return task
    return None


def _log_completion(state: dict, task_id: str, when: datetime) -> None:
    state.setdefault("history", []).append(
        {"task_id": task_id, "completed_at": when.isoformat(timespec="seconds")}
    )


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.route("/api/state")
def api_state():
    """Return the full live state plus today's date so the client and server
    agree on what 'today' is for due-date math."""
    state = storage.load_state()
    return jsonify(
        {
            "today": date.today().isoformat(),
            "tasks": state["tasks"],
            "history": state.get("history", []),
        }
    )


@app.route("/api/tasks/<task_id>/complete", methods=["POST"])
def api_complete(task_id):
    """Mark a task complete. Recurring tasks are rescheduled; as_needed tasks
    are simply cleared from the active lists. Either way a history entry is
    recorded."""
    now = datetime.now()
    today = now.date()

    def _do(state):
        task = _find_task(state, task_id)
        if task is None:
            return None
        _log_completion(state, task_id, now)
        next_due = scheduler.compute_next_due(task, today)
        task["next_due"] = next_due.isoformat() if next_due else None
        return task

    task = storage.mutate(_do)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/api/tasks/<task_id>/trigger", methods=["POST"])
def api_trigger(task_id):
    """Surface an as_needed task on the dashboard as 'due now'."""
    def _do(state):
        task = _find_task(state, task_id)
        if task is None:
            return None
        task["next_due"] = date.today().isoformat()
        return task

    task = storage.mutate(_do)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/api/tasks/<task_id>", methods=["PATCH"])
def api_update(task_id):
    """Edit a task: diy_status, priority, frequency, or active (soft-delete /
    restore). Only whitelisted fields are accepted."""
    payload = request.get_json(silent=True) or {}
    allowed = {"diy_status", "priority", "frequency", "active"}
    valid = {
        "diy_status": {"diy", "hire", "either"},
        "priority": {"low", "medium", "high", "critical"},
        "frequency": scheduler.RECURRING_FREQUENCIES | {"as_needed"},
    }

    def _do(state):
        task = _find_task(state, task_id)
        if task is None:
            return None
        for key, value in payload.items():
            if key not in allowed:
                continue
            if key in valid and value not in valid[key]:
                continue
            task[key] = value
        return task

    task = storage.mutate(_do)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/api/history")
def api_history():
    """Completion log, newest first, joined with task names for display."""
    state = storage.load_state()
    names = {t["id"]: t["name"] for t in state["tasks"]}
    entries = [
        {
            "task_id": h["task_id"],
            "name": names.get(h["task_id"], h["task_id"]),
            "completed_at": h["completed_at"],
        }
        for h in state.get("history", [])
    ]
    entries.sort(key=lambda e: e["completed_at"], reverse=True)
    return jsonify(entries)


if __name__ == "__main__":
    # Bound to localhost: the dashboard is only ever viewed on the Pi itself.
    app.run(host="127.0.0.1", port=5000, debug=False)
