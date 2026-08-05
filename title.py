#!/usr/bin/env python3
"""The title screen: NEW GAME, CONTINUE, SETTINGS, QUIT.

It is an ordinary state on App's stack, and it replaces itself with the field once a
game starts, so there is nothing behind the world once you are in it. SETTINGS is the
same screen the pause menu opens, and lives with it in menu.py.

    play:  .venv/bin/python main.py
    check: .venv/bin/python title.py --test
"""
import sys

import pygame

import save
import sounds
from app import BLACK, SIZE, window
from dq_battle import Hero
from field import HOME_SPAWN, FieldState
from menu import SettingsState, centered

OPENING = ("Morning in the desert. Thy bed is cold, and the Dragonlord "
           "waits beyond the door.")
HINT = "arrows: choose    Z: confirm    X: back"


class TitleState:
    """The first thing on the stack. Nothing here touches the hero until you pick."""

    def __init__(self, app):
        self.app = app
        self.done = False
        self.big = pygame.font.SysFont(
            "couriernew,menlo,dejavusansmono,monospace", 46, bold=True)
        self.items = (["NEW GAME"] + (["CONTINUE"] if save.exists() else [])
                      + ["SETTINGS", "QUIT"])
        self.index = self.items.index("CONTINUE") if "CONTINUE" in self.items else 0

    def update(self, dt):
        sounds.music("field")          # carries straight over into the overworld

    def on_key(self, key):
        if key in (pygame.K_UP, pygame.K_LEFT):
            self.index = (self.index - 1) % len(self.items)
            sounds.play("cursor")
        elif key in (pygame.K_DOWN, pygame.K_RIGHT):
            self.index = (self.index + 1) % len(self.items)
            sounds.play("cursor")
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
            sounds.play("confirm")
            self.choose(self.items[self.index])

    def choose(self, item):
        if item == "QUIT":
            pygame.event.post(pygame.event.Event(pygame.QUIT))   # App.run shuts down
        elif item == "SETTINGS":
            self.app.push(SettingsState(self.app))
        elif item == "CONTINUE":
            log = save.read()
            if log:
                self.start(*log)
            else:                      # the file is there but unreadable: drop the option
                sounds.play("cancel")
                self.items.remove("CONTINUE")
                self.index = 0
        else:
            field = self.start(Hero(), "home", HOME_SPAWN)
            self.app.log.push(OPENING)
            field.msg_timer = 5.0

    def start(self, hero, place, pos):
        field = FieldState(self.app, hero, place, pos)
        self.app.states[:] = [field]   # the title is gone for good, not stacked under
        return field

    def draw(self):
        sc = self.app.screen
        sc.fill(BLACK)
        centered(self.app, self.big, "THE LAST", 46)
        centered(self.app, self.big, "SLAYER", 96)
        centered(self.app, self.app.font, "PROJECT 2026", 152)
        m = pygame.Rect(0, 210, 250, 16 + 26 * len(self.items))
        m.centerx = SIZE[0] // 2
        window(sc, m)
        for i, item in enumerate(self.items):
            y = m.y + 8 + i * 26
            if i == self.index:
                self.app.text(">", m.x + 30, y)
            self.app.text(item, m.x + 56, y)
        centered(self.app, self.app.font, HINT, 420)


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from pathlib import Path
    from app import App

    app = App()

    # a log round-trips the hero and his footing, and a corrupt one reads as nothing
    save.PATH = Path(os.environ.get("TMPDIR", "/tmp")) / "dq_test_log.json"
    save.PATH.unlink(missing_ok=True)
    assert not save.exists() and save.read() is None
    hero = Hero(level=7, gold=140, hp=3, herbs=2,
                flags={"seen:world": True, "met:The gate guard": True})
    field = FieldState(app, hero, "home", HOME_SPAWN)
    field.x, field.y = HOME_SPAWN
    save.write(field)
    back, place, pos = save.read()
    assert back == hero and place == "home" and pos == HOME_SPAWN
    save.PATH.write_text("{ not json")
    assert save.read() is None

    # no log: no CONTINUE. NEW GAME starts a fresh hero and leaves nothing behind it
    save.PATH.unlink()
    app.states[:] = [TitleState(app)]
    assert "CONTINUE" not in app.top.items
    app.top.choose("NEW GAME")
    assert len(app.states) == 1 and isinstance(app.top, FieldState)
    assert app.top.hero.level == 1 and app.top.world.name == "home"

    # a log: CONTINUE is offered, sits under the cursor, and restores that hero
    save.write(field)
    title = TitleState(app)
    assert title.items[title.index] == "CONTINUE"
    app.states[:] = [title]
    title.choose("CONTINUE")
    assert app.top.hero == hero and (app.top.x, app.top.y) == HOME_SPAWN
    save.PATH.unlink()

    # QUIT asks App.run to shut down rather than emptying the stack under itself
    pygame.event.clear()
    app.states[:] = [TitleState(app)]
    app.top.choose("QUIT")
    assert app.states, "QUIT left the stack empty mid-frame"
    assert any(e.type == pygame.QUIT for e in pygame.event.get())

    # SETTINGS stacks on the title and pops off it again. What the knobs actually do
    # is menu.py's business -- it owns that screen and tests it there
    title = TitleState(app)
    app.states[:] = [title]
    title.choose("SETTINGS")
    assert isinstance(app.top, SettingsState) and len(app.states) == 2
    app.top.on_key(pygame.K_x)
    assert app.top.done and not title.done, "leaving the settings left the title too"

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
    else:
        print(__doc__.strip().splitlines()[-2].strip())
