#!/usr/bin/env python3
"""The people of the village, from the RPG Maker character sheets in data/characters.

A sheet holds 4x2 characters; each character is 3 frames across (the walk cycle) by
4 rows down, facing down, left, right, up. Villagers never walk, so only their own
row is cut -- the middle frame to stand in, the outer two for the idle shuffle every
RPG Maker townsfolk has done since 1992.

Talking to one says its next line and remembers where it got to, so a villager with
two things to say says both, then starts again.

Optional like every pack here: without it the villagers still stand there, in
silhouette, and still talk.

    check: .venv/bin/python npc.py --test
"""
import sys
from dataclasses import dataclass, field as dataclasses_field
from pathlib import Path

import pygame

FOLDER = Path(__file__).parent / "data" / "characters"
CELL = 48                       # one frame in the sheet
HEIGHT = 40                     # standing height, matching sprites.FIELD_H
DOWN, LEFT, RIGHT, UP = 0, 1, 2, 3
STEP = (1, 0, 1, 2)             # the shuffle: middle, left, middle, right
PACE = 2.5                      # frames per second, an idle sway rather than a walk


# What a villager can notice about the hero standing in front of them. Each takes the
# talking context: the hero himself, and the flags his Adventure Log remembers.
NEW = lambda c: not c["met"]                                   # never spoken before
HURT = lambda c: c["hero"].hp * 2 <= c["hero"].max_hp
GREEN = lambda c: c["hero"].exp == 0                           # has killed nothing yet
BLOODED = lambda c: c["hero"].level >= 4
RICH = lambda c: c["hero"].gold >= 100
TRAVELLED = lambda c: any(k.startswith("seen:world") for k in c["flags"])
ALWAYS = None                                                  # the usual small talk


@dataclass
class NPC:
    name: str
    sheet: str                  # a PNG in data/characters
    block: tuple                # which of the sheet's 4x2 characters
    facing: int
    lines: list                 # [(condition or ALWAYS, what they say), ...]
    said: int = 0
    told: set = dataclasses_field(default_factory=set)     # remarks already made
    colour: tuple = (120, 90, 70)          # the silhouette, with no pack installed

    def talk(self, context):
        """What this one says now.

        A remark about the moment comes first -- a face not seen before, a wound, a
        heavy purse -- but each of those lands only once, so nobody stands there
        repeating that thou art bleeding while his directions go unheard. Once he has
        made his remarks he falls back to small talk, one line further round each
        time. A new turn of events (a wound taken later, a journey made) unlocks the
        next remark and he speaks up again.
        """
        for when, text in self.lines:
            if when and text not in self.told and when(context):
                self.told.add(text)
                return f"{self.name}: {text}"
        small_talk = [text for when, text in self.lines if when is ALWAYS]
        line = small_talk[self.said % len(small_talk)]
        self.said += 1
        return f"{self.name}: {line}"


# Where everyone stands in village.txt, and what they know. Between them they point
# at every way out of the village, which is the only map the game ever gives you.
VILLAGERS = {
    (11, 18): NPC("The gate guard", "People3", (3, 1), UP, [
        (NEW, "Halt. -- nay, go on, it is only thee. Past this gate the valley ends "
              "and the world begins. Be sure thou meanest it."),
        (HURT, "Thou art bleeding on my gate. Get thee home and mend before the road "
               "finishes what it started."),
        (TRAVELLED, "Thou hast walked the wide world and come back on thy own feet. "
                    "Not many of us can say it."),
        (ALWAYS, "The road south runs out of the valley and into the wide world. "
                 "Mind thy step past the gate."),
        (ALWAYS, "Slimes on the plain have killed better men than thee. Keep to the "
                 "road until thou hast a sword."),
    ], colour=(150, 150, 165)),
    (11, 10): NPC("The village elder", "People3", (1, 1), RIGHT, [
        (NEW, "So thou art awake. The Dragonlord's shadow lies over all Alefgard, "
              "and someone must walk out to meet it. There is only thee."),
        (BLOODED, "Thou art harder than the boy who left this village. Go on to "
                  "Tantegel -- the King himself should look at thee."),
        (ALWAYS, "Long ago the Dragonlord took the Ball of Light, and no dawn since "
                 "has been as bright."),
        (ALWAYS, "On the northern shore of the world there stands an old grey stone. "
                 "Set foot upon it and thou shalt wake in a greener country."),
    ], colour=(170, 170, 175)),
    (4, 5): NPC("The merchant", "People1", (1, 1), DOWN, [
        (RICH, "Now that is a heavy purse! And my cart still broken. The gods are "
               "cruel to merchants."),
        (GREEN, "Thou hast killed nothing, carried nothing, and bought nothing. We "
                "are a poor match, thee and I."),
        (ALWAYS, "My cart lost a wheel on the mountain road, so I have naught to "
                 "sell thee. Come again."),
        (ALWAYS, "Gold buys nothing in a village this small. Save it for the towns "
                 "beyond."),
    ], colour=(210, 200, 170)),
    (8, 15): NPC("The old woman", "People1", (3, 1), LEFT, [
        (HURT, "Child, thou art hurt! Chew a herb, quickly -- I have watched too "
               "many young men bleed out on this street."),
        (NEW, "Awake at last! Thy bed has been cold since dawn, and the world does "
              "not wait for sleepers."),
        (ALWAYS, "Thy mother's house still stands. Whatever else is lost, thou hast "
                 "a door of thine own."),
        (ALWAYS, "Eat before thou goest. Nobody ever slew a dragon hungry."),
    ], colour=(180, 170, 180)),
    (6, 17): NPC("A child", "People1", (1, 0), UP, [
        (TRAVELLED, "Thou hast been out past the gate! What was there? Was it slimes? "
                    "Did they wobble?"),
        (BLOODED, "Everyone says thou art strong now. When I am grown I shall be "
                  "stronger, and then we shall see."),
        (ALWAYS, "When I am grown I shall have a sword, and I shall slay the "
                 "Dragonlord!"),
        (ALWAYS, "Past the green country lies a desert, and in the desert a castle. "
                 "Father says a King lives there."),
    ], colour=(180, 120, 200)),
    (19, 16): NPC("A villager", "People1", (2, 1), DOWN, [
        (HURT, "Thou lookest like a man who has met something bigger than himself. "
               "There is a bed in thy house, thou knowest."),
        (ALWAYS, "Tantegel Castle is far off east, past the green land and the "
                 "desert both."),
        (ALWAYS, "Four ways out of one small valley, and I have taken none of them."),
    ], colour=(120, 140, 190)),
}

SLEW_HIM = lambda c: "slew:Dragonlord" in c["flags"]


# Tantegel's throne room, in castle.txt. The King is the one who tells thee where the
# Dragonlord is; everyone else in the hall is there to make that matter.
COURT = {
    (10, 3): NPC("The King", "People3", (0, 0), DOWN, [
        (SLEW_HIM, "It is done. The Ball of Light is come home, and so art thou. "
                   "Alefgard will remember thy name longer than mine."),
        (NEW, "So. The boy out of the valley, with Erdrick's blood in him. I have sat "
              "here a long while waiting for someone to walk in."),
        (HURT, "Thou art bleeding on my floor, and I have no healer left to give thee. "
               "Rest, then go on."),
        (ALWAYS, "The Dragonlord keeps the Ball of Light in Charlock, across the water "
                 "to the south. No bridge stands, and no boat of mine will go."),
        (ALWAYS, "My knights hold the gate and will not leave it. Thou wilt leave, "
                 "which is why I am speaking to thee and not to them."),
    ], colour=(190, 60, 70)),
    (12, 4): NPC("The Chancellor", "People3", (1, 0), LEFT, [
        (RICH, "That purse would have paid a garrison, once. Keep it -- the treasury "
               "here is dust and ledgers."),
        (ALWAYS, "Address him as Majesty. He has little else left of the word King."),
        (ALWAYS, "Erdrick's line ended in a valley farm. The heralds are still "
                 "arguing about how to write that down."),
    ], colour=(200, 140, 70)),
    (9, 13): NPC("A knight of the gate", "People3", (2, 1), RIGHT, [
        (HURT, "Wounded, in the King's own hall. Eat a herb, lad, before he sees."),
        (ALWAYS, "I have held this door eleven years. It has never once been the "
                 "door that mattered."),
    ], colour=(170, 90, 100)),
    (11, 13): NPC("A knight of the hall", "People3", (3, 1), LEFT, [
        (BLOODED, "Thou hast the walk of a man who has been hit and got up. Good."),
        (ALWAYS, "Beyond the desert is water, and beyond the water is Charlock. That "
                 "is all any of us knows."),
    ], colour=(150, 155, 170)),
    (14, 8): NPC("A lady of the court", "People3", (0, 1), UP, [
        (NEW, "Thou art the first stranger through that door in a year. We had "
              "stopped setting a place."),
        (ALWAYS, "The Princess is not spoken of here. Ask the King, if thou art "
                 "braver than the rest of us."),
    ], colour=(190, 90, 110)),
    (3, 2): NPC("The King's scribe", "People1", (2, 1), DOWN, [
        (ALWAYS, "I keep the rolls of everyone who set out. It is not a long book, "
                 "and no one has come back to sign it."),
        (ALWAYS, "Erdrick's own account is on that shelf, and half of it is missing."),
    ], colour=(120, 140, 190)),
}

IMAGES = {}                     # (sheet, block, facing) -> [Surface, Surface, Surface]


def everyone():
    """Every NPC in the game, whichever map they stand on."""
    return [who for roster in (VILLAGERS, COURT) for who in roster.values()]


def load():
    if IMAGES or not FOLDER.is_dir():
        return IMAGES
    sheets = {}
    try:
        for who in everyone():
            key = (who.sheet, who.block, who.facing)
            if key in IMAGES:
                continue
            if who.sheet not in sheets:
                sheets[who.sheet] = pygame.image.load(
                    str(FOLDER / f"{who.sheet}.png")).convert_alpha()
            bx, by = who.block
            frames = [sheets[who.sheet].subsurface(
                ((bx * 3 + c) * CELL, (by * 4 + who.facing) * CELL, CELL, CELL))
                for c in range(3)]
            # cropped to the union of the three, so the shuffle does not jitter, but
            # sized by the standing frame, so everyone stands the same height
            box = frames[0].get_bounding_rect()
            for frame_ in frames[1:]:
                box = box.union(frame_.get_bounding_rect())
            stance = frames[1].get_bounding_rect()
            if not (box.w and stance.h):
                continue
            f = HEIGHT / stance.h
            IMAGES[key] = [pygame.transform.scale(
                frame_.subsurface(box), (max(1, round(box.w * f)), max(1, round(box.h * f))))
                for frame_ in frames]
    except (pygame.error, ValueError, FileNotFoundError):
        IMAGES.clear()                             # a broken pack is no pack
    return IMAGES


def draw(surf, who, cx, feet_y, elapsed):
    """Draw one villager standing on (cx, feet_y), shuffling in place."""
    frames = IMAGES.get((who.sheet, who.block, who.facing))
    if not frames:                                 # no pack: a figure of the right size
        pygame.draw.rect(surf, who.colour, (cx - 8, feet_y - HEIGHT + 12, 16, HEIGHT - 12))
        pygame.draw.circle(surf, who.colour, (cx, feet_y - HEIGHT + 8), 8)
        return
    image = frames[STEP[int(elapsed * PACE) % len(STEP)]]
    surf.blit(image, (cx - image.get_width() // 2, feet_y - image.get_height()))


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))
    canvas = pygame.Surface((320, 320), pygame.SRCALPHA)

    from dq_battle import Hero

    def context(hero, met=True, **flags):
        return {"hero": hero, "flags": flags, "met": met}

    # small talk cycles, in order, and then starts over
    who = VILLAGERS[(11, 18)]
    plain = [text for when, text in who.lines if when is ALWAYS]
    hale = context(Hero(level=1, hp=15))
    said = [who.talk(hale) for _ in range(2 * len(plain))]
    assert said[:len(plain)] == said[len(plain):], "the villager lost his place"
    assert all(line.startswith(who.name + ":") for line in said)
    assert len({who.name for who in everyone()}) == len(everyone()), "two share a name"

    # everyone, village and court alike, has small talk to fall back on, and every
    # condition of theirs is something that can actually be called
    for person in everyone():
        assert any(when is ALWAYS for when, _ in person.lines), person.name
        assert all(when is ALWAYS or callable(when) for when, _ in person.lines)
        person.said, person.told = 0, set()

    # a first meeting is noticed; a wound taken later is noticed too; and each remark
    # is made once, so his directions are never drowned out by the same observation
    who = VILLAGERS[(11, 18)]
    assert "only thee" in who.talk(context(Hero(), met=False)), "no greeting for a stranger"
    hurt = context(Hero(level=1, hp=4))
    assert "bleeding" in who.talk(hurt), "the wound went unremarked"
    rest = [who.talk(hurt) for _ in range(4)]
    assert not any("bleeding" in line for line in rest), f"he will not stop: {rest}"
    assert any("Mind thy step past the gate" in line for line in rest), \
        f"his directions never got through: {rest}"
    # ...and a fresh turn of events unlocks the next remark
    assert "wide world and come back" in who.talk(
        context(Hero(level=1, hp=15), **{"seen:world": True}))

    # the merchant reads thy purse: rich and broke are different conversations
    trader = VILLAGERS[(4, 5)]
    assert "heavy purse" in trader.talk(context(Hero(gold=500)))
    assert "bought nothing" in trader.talk(context(Hero(exp=0, gold=0)))
    for person in everyone():
        person.said, person.told = 0, set()

    # the court answers to the same rules, and the King answers to the deed
    king = COURT[(10, 3)]
    assert "Erdrick's blood" in king.talk(context(Hero(), met=False))
    assert "Ball of Light is come home" in king.talk(
        context(Hero(level=20), **{"slew:Dragonlord": True})), "the King ignored the deed"
    for person in everyone():
        person.said, person.told = 0, set()

    global FOLDER
    real, FOLDER = FOLDER, Path("/nonexistent-character-pack")
    assert load() == {}
    draw(canvas, who, 40, 40, 0.0)                 # must not raise without the pack
    FOLDER = real

    if not FOLDER.is_dir():
        print("ok (no pack installed, fallback path only)")
        return

    load()
    for person in everyone():
        frames = IMAGES[person.sheet, person.block, person.facing]
        assert len(frames) == 3, person.name
        assert len({f.get_size() for f in frames}) == 1, f"{person.name} jitters"
        assert frames[0].get_flags() & pygame.SRCALPHA, f"{person.name} lost transparency"
        assert abs(frames[1].get_bounding_rect().h - HEIGHT) <= 2, \
            f"{person.name} stands {frames[1].get_bounding_rect().h}px"
        assert frames[1].get_width() <= 2 * CELL
    # two different characters must not be the same picture
    art = {tuple(pygame.image.tobytes(f, "RGBA") for f in v) for v in IMAGES.values()}
    assert len(art) == len(IMAGES), "two villagers were cut from the same block"

    # the shuffle returns to the standing frame twice a cycle, and loops
    seen = [STEP[int(t * PACE) % len(STEP)] for t in (0, 0.4, 0.8, 1.2, 1.6)]
    assert seen == [1, 0, 1, 2, 1], seen

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
