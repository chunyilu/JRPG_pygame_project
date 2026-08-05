#!/usr/bin/env python3
"""The Adventure Log: one slot, one json file -- the hero and where he stands.

Written when the game exits, read by CONTINUE on the title screen.

    check: .venv/bin/python title.py --test
"""
import json
from dataclasses import asdict
from pathlib import Path

from dq_battle import Hero

PATH = Path(__file__).parent / "adventure_log.json"


def exists():
    return PATH.exists()


def write(field):
    """Snapshot a FieldState: the hero, the map he is on, the tile he stands on."""
    PATH.write_text(json.dumps({"hero": asdict(field.hero),
                                "place": field.world.name,
                                "pos": [field.x, field.y]}, indent=1))


def read():
    """-> (hero, place, pos), or None if the log is missing, corrupt or stale."""
    try:
        log = json.loads(PATH.read_text())
        return Hero(**log["hero"]), log["place"], tuple(log["pos"])
    except (OSError, ValueError, TypeError, KeyError):
        return None            # a half-written or hand-edited log is just no log
