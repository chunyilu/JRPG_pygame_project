#!/usr/bin/env python3
"""The pause menu -- inventory, stats, quest log, system -- and the settings knobs.

Four pages side by side, left and right to change page, up and down inside one, Z to
act, X to put it away. It is a state on App's stack like everything else, so the world
stays drawn behind it and stops dead while it is open: no walking, no encounters.

The pages show what the game actually has and nothing more. There are no equipment
slots because there is no equipment yet, and a page with one Herb on it says so in
one line rather than drawing five empty boxes.

    check: .venv/bin/python menu.py --test
"""
import sys

import pygame

import save
import sounds
from app import BLACK, MessageLog, SIZE, WHITE, window
from dq_battle import LEVELS, SPELL_COST, eat_herb

TABS = ("INVENTORY", "STATS", "QUEST", "SYSTEM")
TABBAR = pygame.Rect(16, 14, 608, 40)
BODY = pygame.Rect(16, 62, 608, 356)
HINT_Y = 432
ROW_H = 26
CAP = (BODY.h - 28) // ROW_H    # rows down one column before the page uses a second
COL_W = 288                     # ...and how wide that column is

# Everything the quest log knows how to tell thee, in the order it happens. Each is a
# flag the world sets as thou goest -- there is no quest engine, only what thou hast
# seen and slain, which for a game this size is the same thing.
QUESTS = (
    ("seen:village", "Wake, and step out of thy own front door"),
    ("seen:world", "Take the road south, out of the valley"),
    ("seen:greenland", "Cross the standing stone to the green land"),
    ("seen:alefgard", "Walk into the desert of Alefgard"),
    ("found:Tantegel Castle", "Stand before the gates of Tantegel"),
    ("found:Charlock Castle", "Find Charlock, across the water"),
    ("slew:Dragonlord", "Slay the Dragonlord"),
)


def centered(app, font, text, y, color=WHITE):
    img = font.render(text, True, color)
    app.screen.blit(img, (SIZE[0] // 2 - img.get_width() // 2, y))


def pair(label, value, width=24):
    """One aligned row of a stat page -- the font is monospaced, so this is enough."""
    return f"{label}{str(value).rjust(width - len(label))}"


class MenuState:
    """Opened with X from the field. `field` is the world it was opened over."""

    def __init__(self, app, field):
        self.app, self.field, self.hero = app, field, field.hero
        self.tab = self.index = 0
        self.note = ""
        self.done = False
        # the world stays visible under the menu, but dimmed -- otherwise the status
        # panel and the log window show through the gaps and fight with the pages
        self.veil = pygame.Surface(SIZE, pygame.SRCALPHA)
        self.veil.fill((0, 0, 0, 232))

    # -- pages ---------------------------------------------------------
    def inventory(self):
        """-> [(text, action or None), ...]. Only what is actually carried."""
        rows = []
        if self.hero.herbs:
            rows.append((pair("Herb", f"x{self.hero.herbs}"), self.eat))
        return rows or [("Thou carriest nothing at all.", None)]

    def stats(self):
        h = self.hero
        to_next = (LEVELS[h.level][0] - h.exp if h.level < len(LEVELS) else None)
        rows = [pair("Name", h.name), pair("Level", h.level),
                pair("Hit Points", f"{h.hp} / {h.max_hp}"),
                pair("Magic Points", f"{h.mp} / {h.max_mp}"),
                pair("Experience", h.exp),
                pair("Next level in", to_next if to_next is not None else "--"),
                pair("Strength", h.strength), pair("Agility", h.agility),
                pair("Attack", h.attack), pair("Defence", h.defense),
                pair("Gold", h.gold)]
        if h.spells:                              # hidden entirely until level 3
            rows += ["", "Spells known"]
            rows += [pair(f"  {s.capitalize()}", f"{SPELL_COST[s]} MP") for s in h.spells]
        return [(text, None) for text in rows]

    def quest(self):
        flags = self.hero.flags
        done = sum(1 for key, _ in QUESTS if key in flags)
        rows = [pair("Deeds done", f"{done} / {len(QUESTS)}"), ""]
        rows += [f"{'[x]' if key in flags else '[ ]'} {text}" for key, text in QUESTS]
        return [(text, None) for text in rows]

    def system(self):
        peace = self.hero.flags.get("no-battles")
        return [(pair("Battles", "SKIPPED" if peace else "ON"), self.no_battles),
                ("Save thy adventure", self.write_log),
                ("Settings", self.open_settings),
                ("Exit game", self.leave)]

    def page(self):
        return (self.inventory, self.stats, self.quest, self.system)[self.tab]()

    # -- actions -------------------------------------------------------
    def eat(self):
        if self.hero.hp >= self.hero.max_hp:
            sounds.play("cancel")
            self.note = "Thou art unhurt. Save the Herb."
            return
        healed = eat_herb(self.hero)
        sounds.play("heal")
        self.note = f"{self.hero.name} eats a Herb. Hit Points recovered by {healed}."

    def no_battles(self):
        """Walk the whole map unmolested. Rides in the hero's flags, so it is saved
        with him -- turn it on to go sightseeing and it stays on until turned off."""
        peace = not self.hero.flags.get("no-battles")
        self.hero.flags["no-battles"] = peace
        sounds.play("place" if peace else "cancel")
        self.note = ("No monster will trouble thee. Go and see the world."
                     if peace else "The wilds are dangerous once more.")

    def write_log(self):
        save.write(self.field)
        sounds.play("place")
        self.note = "Thy adventure is written in the log."

    def open_settings(self):
        self.app.push(SettingsState(self.app))

    def leave(self):
        pygame.event.post(pygame.event.Event(pygame.QUIT))     # App.run saves and shuts

    # -- flow ----------------------------------------------------------
    def update(self, dt):
        pass

    def on_key(self, key):
        rows = self.page()
        picks = [i for i, (_, action) in enumerate(rows) if action]
        if key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.tab = (self.tab + (1 if key == pygame.K_RIGHT else -1)) % len(TABS)
            self.index, self.note = 0, ""
            sounds.play("cursor")
        elif key in (pygame.K_UP, pygame.K_DOWN) and picks:
            step = 1 if key == pygame.K_DOWN else -1
            self.index = picks[(picks.index(self.cursor(picks)) + step) % len(picks)]
            sounds.play("cursor")
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z) and picks:
            sounds.play("confirm")
            rows[self.cursor(picks)][1]()
        elif key in (pygame.K_x, pygame.K_ESCAPE):
            sounds.play("cancel")
            self.done = True

    def cursor(self, picks):
        """The selected row, snapped onto something selectable."""
        return self.index if self.index in picks else picks[0]

    # -- render --------------------------------------------------------
    def draw(self):
        sc = self.app.screen
        sc.blit(self.veil, (0, 0))
        window(sc, TABBAR)
        span = TABBAR.w // len(TABS)
        for i, name in enumerate(TABS):
            label = f"[{name}]" if i == self.tab else f" {name} "
            img = self.app.font.render(label, True, WHITE)
            sc.blit(img, (TABBAR.x + i * span + (span - img.get_width()) // 2,
                          TABBAR.y + 10))
        window(sc, BODY)
        rows = self.page()
        picks = [i for i, (_, action) in enumerate(rows) if action]
        here = self.cursor(picks) if picks else -1
        for i, (text, _) in enumerate(rows):
            col, line = divmod(i, CAP)             # a long page runs into a second column
            x, y = BODY.x + 28 + col * COL_W, BODY.y + 14 + line * ROW_H
            if i == here:
                self.app.text(">", x - 18, y)
            self.app.text(text, x, y)
        if self.note:
            centered(self.app, self.app.font, self.note, BODY.bottom - 34)
        centered(self.app, self.app.font,
                 "left/right: page   up/down: choose   Z: use   X: close", HINT_Y)


class SettingsState:
    """Volume and text speed, applied live. Reached from the title and from the menu.

    ponytail: not persisted -- nothing else in the game is saved between runs except
    the Adventure Log, and these live in the modules they belong to.
    """

    ROWS = ("MUSIC", "SOUND", "TEXT SPEED")
    SLOWEST, PER_STEP = 15.0, 10.0     # letters/second at level 0, and per level

    def __init__(self, app):
        self.app = app
        self.index = 0
        self.done = False

    def level(self, row):
        if row == "MUSIC":
            return round(sounds.MUSIC_VOLUME * 10)
        if row == "SOUND":
            return round(sounds.SFX_VOLUME * 10)
        return round((self.app.log.SPEED - self.SLOWEST) / self.PER_STEP)

    def set_level(self, row, n):
        n = min(10, max(0, n))
        if row == "MUSIC":
            sounds.set_volume(music=n / 10)
        elif row == "SOUND":
            sounds.set_volume(sfx=n / 10)
            sounds.play("cursor")      # hear what you just set
        else:
            self.app.log.SPEED = self.SLOWEST + n * self.PER_STEP

    def update(self, dt):
        pass

    def on_key(self, key):
        row = self.ROWS[self.index]
        if key == pygame.K_UP:
            self.index = (self.index - 1) % len(self.ROWS)
            sounds.play("cursor")
        elif key == pygame.K_DOWN:
            self.index = (self.index + 1) % len(self.ROWS)
            sounds.play("cursor")
        elif key == pygame.K_LEFT:
            self.set_level(row, self.level(row) - 1)
        elif key == pygame.K_RIGHT:
            self.set_level(row, self.level(row) + 1)
        elif key in (pygame.K_x, pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE,
                     pygame.K_z):
            sounds.play("cancel")
            self.done = True           # pops back to whatever pushed us

    def draw(self):
        sc = self.app.screen
        sc.fill(BLACK)
        centered(self.app, self.app.font, "SETTINGS", 120)
        m = pygame.Rect(0, 170, 400, 16 + 30 * len(self.ROWS))
        m.centerx = SIZE[0] // 2
        window(sc, m)
        for i, row in enumerate(self.ROWS):
            n = self.level(row)
            y = m.y + 10 + i * 30
            if i == self.index:
                self.app.text(">", m.x + 14, y)
            self.app.text(row, m.x + 38, y)
            self.app.text("#" * n + "." * (10 - n), m.x + 240, y)
        centered(self.app, self.app.font, "left/right: adjust    X: back", HINT_Y)


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    from pathlib import Path
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from app import App
    from dq_battle import Hero
    from field import HOME_SPAWN, FieldState

    app = App()
    hero = Hero(level=8, hp=20, mp=10, exp=900, gold=250, herbs=2,
                flags={"seen:village": True, "seen:world": True})
    field = FieldState(app, hero, "village", HOME_SPAWN)
    menu = MenuState(app, field)
    app.states[:] = [field, menu]

    # every page draws inside its window: never off the bottom, never past the right
    # edge. Measured in real pixels -- a stat label one word longer is a silent clip
    for tab in range(len(TABS)):
        menu.tab = tab
        rows = menu.page()
        assert rows, TABS[tab]
        assert len(rows) <= 2 * CAP, f"{TABS[tab]} has {len(rows)} rows, {2 * CAP} fit"
        room = COL_W if len(rows) > CAP else BODY.w - 40
        for text, _ in rows:
            assert app.font.size(text)[0] <= room, f"{TABS[tab]}: too wide: {text!r}"
        app.screen.fill(BLACK)
        menu.draw()

    # the pages report the hero as he is
    menu.tab = TABS.index("STATS")
    shown = " ".join(text for text, _ in menu.page())
    for want in ("Loto", "20 / 46", "900", "250", "Heal"):        # hp, exp, gold, spell
        assert want in shown, f"the stats page never mentions {want!r}: {shown}"
    assert "Hurtmore" not in shown, "a spell he cannot cast is listed"
    menu.tab = TABS.index("QUEST")
    quests = " ".join(text for text, _ in menu.page())
    assert "2 / 7" in quests and "[x] Wake" in quests and "[ ] Slay" in quests, quests

    # a Herb is eaten from the inventory, once, and not wasted at full health
    menu.tab = TABS.index("INVENTORY")
    menu.index = 0
    menu.on_key(pygame.K_z)
    assert hero.herbs == 1 and hero.hp > 20, "the Herb did nothing"
    hero.hp = hero.max_hp
    menu.on_key(pygame.K_z)
    assert hero.herbs == 1, "a Herb was wasted at full health"
    assert "unhurt" in menu.note
    hero.herbs = 0
    assert menu.page() == [("Thou carriest nothing at all.", None)]
    menu.on_key(pygame.K_z)                       # nothing to pick: must not raise

    # left and right wrap round the pages, and the cursor never lands on a bare line
    menu.tab = 0
    menu.on_key(pygame.K_LEFT)
    assert TABS[menu.tab] == "SYSTEM"
    menu.on_key(pygame.K_RIGHT)
    assert menu.tab == 0
    for tab in range(len(TABS)):
        menu.tab = tab
        for _ in range(6):
            menu.on_key(pygame.K_DOWN)
            rows = menu.page()
            picks = [i for i, (_, a) in enumerate(rows) if a]
            if picks:
                assert rows[menu.cursor(picks)][1], f"{TABS[tab]}: cursor on a bare line"

    def row_of(label):
        return next(i for i, (text, _) in enumerate(menu.page()) if text == label)

    # BATTLES toggles both ways, says so, and the row reports which way it is set
    menu.tab = TABS.index("SYSTEM")
    menu.index = 0
    assert "ON" in menu.page()[0][0]
    menu.on_key(pygame.K_z)
    assert hero.flags["no-battles"] is True and "No monster" in menu.note
    assert "SKIPPED" in menu.page()[0][0], "the row still claims battles are on"
    menu.on_key(pygame.K_z)
    assert hero.flags["no-battles"] is False and "dangerous" in menu.note
    menu.on_key(pygame.K_z)                       # left on, for the save below

    # SAVE writes the log where CONTINUE will find it
    save.PATH = Path(os.environ.get("TMPDIR", "/tmp")) / "dq_menu_log.json"
    save.PATH.unlink(missing_ok=True)
    menu.index = row_of("Save thy adventure")
    menu.on_key(pygame.K_z)
    assert save.exists() and save.read()[0].level == 8, "SAVE wrote no readable log"
    save.PATH.unlink()

    # SETTINGS stacks on top of the menu and pops back to it, not to the field
    menu.index = row_of("Settings")
    menu.on_key(pygame.K_z)
    assert isinstance(app.top, SettingsState) and len(app.states) == 3
    app.top.on_key(pygame.K_x)
    assert app.top.done and not menu.done, "closing settings closed the menu too"
    app.states.pop()

    # ...and X closes the menu itself
    menu.on_key(pygame.K_x)
    assert menu.done

    # the settings knobs move, clamp, and survive the log clearing itself
    s = SettingsState(app)
    for row in SettingsState.ROWS:
        s.index = SettingsState.ROWS.index(row)
        s.set_level(row, 0)
        assert s.level(row) == 0
        for _ in range(20):
            s.on_key(pygame.K_RIGHT)
        assert s.level(row) == 10, row
        s.on_key(pygame.K_LEFT)
        assert s.level(row) == 9, row
    assert sounds.MUSIC_VOLUME == 0.9 and sounds.SFX_VOLUME == 0.9
    assert app.log.SPEED == 105.0
    app.log.clear()
    assert app.log.SPEED == 105.0, "clearing the log reset the text speed"
    assert isinstance(app.log, MessageLog)

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
