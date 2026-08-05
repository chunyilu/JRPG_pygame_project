#!/usr/bin/env python3
"""Indoor tiles, cut from the CraftPix top-down home pack in data/map/.

The pack is 16px atlas cells; drawn at 2x one cell is exactly one 32px game tile,
so the interior lines up with the overworld. Furniture is bigger than a cell -- the
bed is 2x3, the shelf 2x3, the door 1x2 -- so an object is anchored to the bottom
left of its tile and allowed to overflow up and to the right. That only composites
correctly if every floor is painted before any object, which is why a world draws
in two passes.

Optional like every pack here: without it the room still draws, in flat colour.

    check: .venv/bin/python interior.py --test
"""
import sys
from pathlib import Path

import pygame

PACK = (Path(__file__).parent / "data" / "map"
        / "main-characters-home-free-top-down-pixel-art-asset" / "PNG")
CELL, SCALE = 16, 2
TILE = CELL * SCALE

# char -> (atlas, source rect in atlas pixels, walkable, fallback colour). Pixels,
# not cells: the window art straddles a cell boundary, so cells cannot name it.
SPEC = {
    ".": ("walls_floor", (112, 64, 16, 16), True, (150, 116, 80)),
    "#": ("walls_floor", (0, 96, 16, 32), False, (96, 106, 118)),
    "w": ("walls_floor", (87, 67, 17, 20), False, (90, 130, 190)),
    "+": ("walls_floor", (112, 96, 16, 32), True, (140, 88, 44)),
    "B": ("Interior", (48, 0, 32, 48), False, (80, 90, 170)),
    "S": ("Interior", (160, 80, 32, 48), False, (120, 80, 50)),
    "T": ("Interior", (112, 176, 48, 32), False, (150, 100, 60)),
    "c": ("Interior", (0, 208, 32, 32), False, (130, 90, 55)),
    "p": ("Interior", (0, 368, 32, 32), False, (70, 140, 60)),
    "b": ("Interior", (144, 48, 16, 32), False, (140, 110, 70)),
    "r": ("Interior", (144, 128, 48, 48), False, (110, 80, 60)),
    "s": ("Interior", (128, 368, 16, 32), False, (150, 140, 110)),
}
ON_WALL = {"w"}                 # set into a wall, so the wall is painted first

IMAGES = {}


def load():
    if IMAGES or not PACK.is_dir():
        return IMAGES
    atlases = {}
    try:
        for ch, (atlas, (x, y, w, h), _, _) in SPEC.items():
            if atlas not in atlases:
                atlases[atlas] = pygame.image.load(str(PACK / f"{atlas}.png")).convert_alpha()
            src = atlases[atlas].subsurface((x, y, w, h))
            art = src.get_bounding_rect()        # trim the slack so feet anchor true
            src = src.subsurface(art)
            IMAGES[ch] = pygame.transform.scale(src, (art.w * SCALE, art.h * SCALE))
    except (pygame.error, ValueError, FileNotFoundError):
        IMAGES.clear()                           # a broken pack is no pack
    return IMAGES


def walkable(ch):
    return SPEC[ch][2]


def ground(surf, ch, px, py, tx, ty):
    """Pass one: floorboards under everything, so overflow has something to sit on."""
    floor = IMAGES.get(".")
    if floor is None:
        pygame.draw.rect(surf, SPEC["."][3], (px, py, TILE, TILE))
    else:
        surf.blit(floor, (px, py))


def obj(surf, ch, px, py, tx, ty):
    """Pass two: the thing standing on the tile, anchored by its feet."""
    if ch == ".":
        return
    if ch in ON_WALL:
        obj(surf, "#", px, py, tx, ty)           # the wall it is set into
    image = IMAGES.get(ch)
    if image is None:                            # no pack: a block of its colour
        _, (_, _, w, h), _, colour = SPEC[ch]
        pygame.draw.rect(surf, colour, (px + 2, py + TILE - h * SCALE + 2,
                                        w * SCALE - 4, h * SCALE - 4))
        return
    x = px + (TILE - image.get_width()) // 2     # centred on its tile, standing on it
    if ch in ON_WALL:                            # except a window, hung in the wall
        surf.blit(image, (x, py - TILE + (TILE - image.get_height()) // 2))
        return
    surf.blit(image, (x, py + TILE - image.get_height()))


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))
    canvas = pygame.Surface((320, 320), pygame.SRCALPHA)   # alpha, or bounding_rect
    canvas.fill((0, 0, 0, 0))                              # measures the whole surface

    global PACK
    real, PACK = PACK, Path("/nonexistent-home-pack")
    assert load() == {}
    ground(canvas, ".", 0, 0, 0, 0)              # must not raise without the pack
    obj(canvas, "B", 0, 96, 0, 3)
    PACK = real

    if not PACK.is_dir():
        print("ok (no pack installed, fallback path only)")
        return

    load()
    for ch, (_, (_, _, w, h), _, _) in SPEC.items():
        image = IMAGES[ch]
        assert image.get_bounding_rect().size == image.get_size(), f"{ch} not trimmed"
        assert image.get_width() <= w * SCALE and image.get_height() <= h * SCALE, ch
        assert image.get_height() >= TILE * 0.5, f"{ch} came out too small to see"
    assert IMAGES["."].get_size() == (TILE, TILE), "the floor must be exactly one tile"
    assert IMAGES["#"].get_size() == (TILE, 2 * TILE), "a wall is one tile plus its top"

    # an object taller than its tile grows upwards, never downwards
    canvas.fill((0, 0, 0, 0))
    obj(canvas, "B", 0, 3 * TILE, 0, 3)          # bed standing on row 3
    painted = canvas.get_bounding_rect()
    assert painted.bottom <= 4 * TILE, "object hangs below its tile"
    assert painted.top < 3 * TILE, "a 3-cell object did not overflow upwards"

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
