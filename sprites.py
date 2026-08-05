#!/usr/bin/env python3
"""Animated actors -- the hero and the monsters -- from the packs in data/.

Two source layouts. The hero is a CraftPix *chibi* pack: one 900x900 PNG per frame
in PNG Sequences/<Anim>/, a sequence per animation. Every monster is a Pipoya
battler: one 480x480 PNG, one pose, no animation at all -- which is what a Dragon
Quest monster did anyway, standing there until it was hit.

The hero is preloaded at startup. Monsters load on first encounter -- nine species
of 900x900 frames is a lot to read for the two you might actually meet -- so a
battle calls ensure() before it draws.

Every frame is a 900x900 canvas with the character somewhere inside it, so each
sequence is cropped to the union of its frames -- shared across the sequence, or
the character jitters -- and scaled once at load into the two sizes the game uses.

That crop differs wildly between animations (the slash FX and the dying sprawl are
half again as wide as a standing pose), so sizing and centring go by each
sequence's *opening* frame, which is the same neutral stance in all of them. The
body then comes out the same size and in the same spot whatever the pose.

The pack is optional: with it absent, load() yields nothing, draw() reports False
and the callers fall back to their procedural drawing. Same deal as sounds.py.

    check: .venv/bin/python sprites.py --test
"""
import sys
from pathlib import Path

import pygame

import pixelart

DATA = Path(__file__).parent / "data"
PACK = DATA / "craftpix-net-787868-free-seer-chibi-character-sprites"
MOBS = DATA / "Pipoya RPG Monster Pack" / "shade"
SEER = 1                        # the hero pack ships three palettes: Seer_1..3
FIELD_H = 40                    # walking Alefgard, a little taller than a 32px tile
BATTLE_H = 150

ANIMS = {"idle": "Idle", "walk": "Walking", "slash": "Slashing",
         "cast": "Throwing", "hurt": "Hurt", "die": "Dying"}
FPS = {"idle": 14, "walk": 30, "slash": 20, "cast": 20, "hurt": 18, "die": 14}


# The hero, plus every Pipoya battler the pack ships, keyed by its file: "enemy009",
# "enemy009a", "boss004". Registering the folder rather than a hand-written list means
# a Monster only has to name the picture it wants; nothing loads until it is fought.
ACTORS = {"hero": ("chibi", PACK / f"Seer_{SEER}")}
ACTORS.update({path.stem.removeprefix("pipo-"): ("still", path)
               for path in sorted(MOBS.glob("pipo-*.png"))})

SETS = {}                       # (actor, anim, height) -> [Surface, ...]
ANCHOR = {}                     # (actor, anim, height) -> (offset from centre, pad under feet)


def _raw(actor, anim):
    """The unscaled frames of one animation, in whichever layout the pack uses."""
    kind, path = ACTORS[actor]
    if kind == "chibi":
        paths = sorted((path / "PNG" / "PNG Sequences" / ANIMS[anim]).glob("*.png"))
        return [pygame.image.load(str(p)).convert_alpha() for p in paths], True
    if anim != "idle" or not path.exists():
        return [], True                               # a battler has one pose, no more
    return [pygame.image.load(str(path)).convert_alpha()], True


def ensure(actor, anim, height):
    """Load one animation at one size if it is not cached. False if unavailable."""
    key = (actor, anim, height)
    if key in SETS:
        return True
    if actor not in ACTORS:
        return False
    try:
        images, smooth = _raw(actor, anim)
    except (pygame.error, OSError):
        images = []
    if not images:
        return False
    # min_alpha=CUT, not the default 1: pixelart.snap() throws away everything fainter
    # than that, so measuring the body by pixels it is about to delete sizes the sprite
    # to a halo. Some chibi bosses wear one and came out 10% short.
    stance = images[0].get_bounding_rect(min_alpha=pixelart.CUT)   # neutral opening frame
    box = stance
    for image in images[1:]:
        box = box.union(image.get_bounding_rect(min_alpha=pixelart.CUT))
    if not (box.w and box.h and stance.h):
        return False
    scale = pygame.transform.smoothscale if smooth else pygame.transform.scale
    f = height / stance.h                             # size by the body, not the canvas
    SETS[key] = [pixelart.snap(scale(im.subsurface(box),
                                     (max(1, round(box.w * f)), max(1, round(box.h * f)))))
                 for im in images]
    ANCHOR[key] = (round((stance.centerx - box.centerx) * f),
                   round((box.bottom - stance.bottom) * f))
    return True


def load():
    """Preload the hero at both sizes. Missing pack -> stays empty."""
    if SETS or not PACK.is_dir():
        return SETS
    for anim in ANIMS:
        for height in (FIELD_H, BATTLE_H):
            ensure("hero", anim, height)
    return SETS


def frame(actor, anim, height, elapsed, loop=True):
    """The frame showing at `elapsed` seconds in, or None if it never loaded."""
    frames = SETS.get((actor, anim, height))
    if not frames:
        return None
    i = int(elapsed * FPS[anim])
    return frames[i % len(frames)] if loop else frames[min(i, len(frames) - 1)]


def duration(actor, anim):
    frames = SETS.get((actor, anim, BATTLE_H)) or SETS.get((actor, anim, FIELD_H))
    return len(frames) / FPS[anim] if frames else 0.0


def draw(surf, actor, anim, height, elapsed, cx, feet_y, flip=False, loop=True):
    """Draw the current frame with the body centred on cx and standing on feet_y.

    Returns False when there is no pack, which is the caller's cue to fall back.
    """
    image = frame(actor, anim, height, elapsed, loop)
    if image is None:
        return False
    dx, pad = ANCHOR[actor, anim, height]
    if flip:
        image, dx = pygame.transform.flip(image, True, False), -dx
    surf.blit(image, (cx - image.get_width() // 2 - dx,
                      feet_y - image.get_height() + pad))
    return True


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))

    # with no pack, nothing raises and every lookup is None
    global PACK
    real, PACK = PACK, Path("/nonexistent-sprite-pack")
    ACTORS["hero"] = ("chibi", PACK)
    assert load() == {} and frame("hero", "walk", FIELD_H, 0.0) is None
    assert duration("hero", "walk") == 0.0 and not ensure("hero", "idle", 40)
    assert not ensure("no-such-actor", "idle", 40)
    PACK = real
    ACTORS["hero"] = ("chibi", PACK / f"Seer_{SEER}")

    if not PACK.is_dir():
        print("ok (no pack installed, fallback path only)")
        return

    load()
    assert set(ANIMS) <= {anim for _, anim, _ in SETS}, "an animation failed to load"

    # every battler in the pack loads on demand, and each one is its own picture
    battlers = [a for a in ACTORS if a != "hero"]
    assert len(battlers) > 100, f"only {len(battlers)} battlers found in {MOBS}"
    for actor in battlers:
        assert ensure(actor, "idle", 90), actor
    assert not ensure("enemy009", "walk", 90), "a battler has one pose only"
    art = {pygame.image.tobytes(SETS[a, "idle", 90][0], "RGBA") for a in battlers}
    assert len(art) == len(battlers), "two battlers are the same picture"

    for (actor, anim, height), frames in SETS.items():
        what = f"{actor}/{anim}"
        assert frames, f"{what} loaded empty"
        assert len({f.get_size() for f in frames}) == 1, f"{what} frames differ in size"
        assert frames[0].get_flags() & pygame.SRCALPHA, f"{what} lost its transparency"
        # the anchor's whole job: the standing pose is the same size and in the
        # same place in every animation, however wide that animation's crop is
        body = frames[0].get_bounding_rect()
        dx, pad = ANCHOR[actor, anim, height]
        assert abs(body.h - height) <= 2, f"{what} stands {body.h}px, wanted {height}"
        assert abs(body.centerx - (frames[0].get_width() / 2 + dx)) <= 2, f"{what} off-centre"
        assert abs(body.bottom - (frames[0].get_height() - pad)) <= 2, f"{what} floats"

    # looping wraps, non-looping holds the last frame instead of wrapping
    walk = SETS["hero", "walk", FIELD_H]
    assert frame("hero", "walk", FIELD_H, 0.0) is walk[0]
    assert frame("hero", "walk", FIELD_H, len(walk) / FPS["walk"]) is walk[0]
    dying = SETS["hero", "die", BATTLE_H]
    assert frame("hero", "die", BATTLE_H, 99.0, loop=False) is dying[-1]
    assert 0.3 < duration("hero", "die") < 3.0

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
