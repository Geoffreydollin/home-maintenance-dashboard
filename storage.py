"""
storage.py
==========

Thin persistence layer over a single local JSON file. All writes are atomic:
the new content is written to a temp file in the same directory and then
os.replace()'d over the target, so a power loss mid-write can never leave a
half-written (corrupt) data file -- the worst case is losing the most recent
change, not the whole file.

The live data file (data/tasks.json) is the single source of truth at runtime.
On first run it is created by seeding from data/seed_tasks.json (the raw task
definitions checked into git) with `next_due` computed relative to *today*.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import date

import scheduler

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SEED_FILE = os.path.join(DATA_DIR, "seed_tasks.json")
DATA_FILE = os.path.join(DATA_DIR, "tasks.json")

SCHEMA_VERSION = 1

# A single process-wide lock serialises reads/writes. The app is single-user
# and low-traffic, so a coarse lock is simpler and plenty fast.
_lock = threading.Lock()


def _atomic_write(path: str, data: dict) -> None:
    """Write `data` as pretty JSON to `path` atomically."""
    directory = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)  # atomic on POSIX and Windows
    except Exception:
        # Clean up the temp file if anything went wrong before the replace.
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _seed_state(today: date) -> dict:
    """Build the initial state dict from the checked-in seed definitions."""
    with open(SEED_FILE, "r", encoding="utf-8") as fh:
        seed_tasks = json.load(fh)

    tasks = []
    for raw in seed_tasks:
        task = dict(raw)
        task.setdefault("active", True)
        task["next_due"] = _date_to_str(scheduler.seed_next_due(task, today))
        tasks.append(task)

    return {
        "version": SCHEMA_VERSION,
        "tasks": tasks,
        "history": [],
    }


def _date_to_str(d: date | None) -> str | None:
    return d.isoformat() if d is not None else None


def load_state(today: date | None = None) -> dict:
    """Load the live state, seeding the data file on first run."""
    today = today or date.today()
    with _lock:
        if not os.path.exists(DATA_FILE):
            state = _seed_state(today)
            _atomic_write(DATA_FILE, state)
            return state
        with open(DATA_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)


def save_state(state: dict) -> None:
    with _lock:
        _atomic_write(DATA_FILE, state)


def mutate(fn):
    """Load state, apply `fn(state)` (which may return a value), persist, and
    return whatever `fn` returned. The whole read-modify-write is locked."""
    with _lock:
        if not os.path.exists(DATA_FILE):
            state = _seed_state(date.today())
        else:
            with open(DATA_FILE, "r", encoding="utf-8") as fh:
                state = json.load(fh)
        result = fn(state)
        _atomic_write(DATA_FILE, state)
        return result
