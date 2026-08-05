#!/usr/bin/env python3
"""Map decoration from the CraftPix desert tileset in data/.

The pack is desert-themed, so it is used where it reads correctly and no further:
sand under the desert, palms and cacti on it, leafy trees for forest, boulders on
the hills, adobe houses for towns. Sea, swamp, mountain and the landmark buildings
stay procedural -- a saguaro on every tile would turn Alefgard into Arizona.

Ground fills tile-for-tile; decor is an object standing on the tile, allowed to
overflow upwards, which is why the field draws rows top to bottom. Which object a
tile gets is hashed from its coordinates, so it is scattered but never shimmers.

Optional, like every pack here: no files, nothing draws, the caller falls back.

    check: .venv/bin/python tileset.py --test
"""
import sys
from pathlib import Path

import pygame

import pixelart

PACK = Path(__file__).parent / "data" / "craftpix-891121-free-2d-rpg-desert-tileset" / "PNG"
TILE = 32

# terrain char -> (ground texture, tint). Only bg tiles seamlessly; the land_*
# pieces have a dark border baked in and show a grid when repeated. One texture
# tinted per terrain is cheaper than sourcing three, and keeps the world coherent.
GROUND = {
    ":": ("bg", None),                  # open sand
    "^": ("bg", (226, 212, 190)),       # rocky ground: barely duller, or it grids
    "A": ("bg", (165, 155, 145)),       # bare rock, procedural peaks drawn over it.
                                        # Darker than it needs to look: pixelart's
                                        # palette has to be able to tell it from "^"
    "=": ("bg", None),                  # the bridge paints its own water and planks
    "C": ("bg", None), "T": ("bg", None), "O": ("bg", None),
    "S": ("bg", None), "X": ("bg", None), "H": ("bg", None),
}

# terrain char -> (objects, how tall in pixels, how many tiles in 100 get one)
DECOR = {
    "*": (["tree_1", "tree_2", "tree_5", "tree_9", "tree_10"], 40, 100),
    ":": (["greenery_1", "greenery_2", "greenery_3", "greenery_4", "greenery_5",
           "tree_3", "tree_11", "tree_12", "stones_2", "stones_5"], 30, 22),
    "^": (["stones_1", "stones_4", "stones_5", "stones_6", "tree_11"], 24, 50),
    ".": (["greenery_6"], 18, 30),      # tufts on the oasis fringe
    "T": (["building_1", "building_2", "building_3", "building_4", "building_5"], 34, 100),
    "H": (["building_4"], 32, 100),     # the hero's own house
}

IMAGES = {}                     # name -> scaled Surface
TILES = {}                      # terrain char -> ground Surface


def _hash(tx, ty):
    return (tx * 73856093) ^ (ty * 19349663) & 0x7FFFFFFF


def _scaled(name, height=None):
    """Load, crop away the transparent margin, scale to `height` (or to a tile)."""
    image = pygame.image.load(str(PACK / f"{name}.png")).convert_alpha()
    box = image.get_bounding_rect()
    if not box.w or not box.h:
        return None
    if height is None:
        return pygame.transform.smoothscale(image.subsurface(box), (TILE, TILE))
    width = max(1, round(box.w * height / box.h))
    return pygame.transform.smoothscale(image.subsurface(box), (width, height))


def load():
    if IMAGES or not PACK.is_dir():
        return IMAGES
    try:
        for ch, (name, tint) in GROUND.items():
            image = _scaled(name)
            if tint:
                image.fill(tint, special_flags=pygame.BLEND_MULT)
            TILES[ch] = pixelart.snap(image)     # after the tint: multiplying a
                                                 # snapped colour unsnaps it again
        for names, height, _ in DECOR.values():
            for name in names:                   # keyed by size too: an object may
                image = _scaled(name, height)    # serve two terrains
                IMAGES[name, height] = image and pixelart.snap(image)
    except (pygame.error, FileNotFoundError):
        IMAGES.clear()                           # a broken pack is no pack
        TILES.clear()
    return IMAGES


def ground(surf, ch, px, py, tx, ty):
    image = TILES.get(ch)
    if image is None:
        return False
    surf.blit(image, (px, py))
    return True


def decor(surf, ch, px, py, tx, ty):
    entry = DECOR.get(ch)
    if not entry:
        return False
    names, height, density = entry
    names = [n for n in names if IMAGES.get((n, height))]
    h = _hash(tx, ty)
    if not names or h % 100 >= density:
        return False
    image = IMAGES[names[(h >> 7) % len(names)], height]
    jitter = (h >> 13) % 7 - 3                   # nudge, so rows do not line up
    surf.blit(image, (px + (TILE - image.get_width()) // 2 + jitter,
                      py + TILE - image.get_height()))
    return True


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))
    canvas = pygame.Surface((TILE, TILE), pygame.SRCALPHA)

    global PACK
    real, PACK = PACK, Path("/nonexistent-tileset")
    assert load() == {} and not ground(canvas, ":", 0, 0, 1, 1)
    assert not decor(canvas, "*", 0, 0, 1, 1)
    PACK = real

    if not PACK.is_dir():
        print("ok (no pack installed, fallback path only)")
        return

    load()
    for ch in GROUND:
        assert TILES[ch].get_size() == (TILE, TILE), ch
    # the tints must actually differ, or the terrains read as one
    assert len({pygame.image.tobytes(TILES[c], "RGB") for c in (":", "^", "A")}) == 3
    for names, height, _ in DECOR.values():
        for name in names:
            image = IMAGES[name, height]
            assert image.get_height() == height, name
            assert image.get_width() <= 2 * TILE, f"{name} is wider than two tiles"
            assert image.get_flags() & pygame.SRCALPHA, f"{name} lost transparency"

    # the same tile always draws the same thing; different tiles vary
    def shot(ch, tx, ty):
        canvas.fill((0, 0, 0, 0))
        decor(canvas, ch, 0, 0, tx, ty)
        return pygame.image.tobytes(canvas, "RGBA")
    assert shot("*", 7, 9) == shot("*", 7, 9), "decor is not stable per tile"
    assert len({shot("*", x, 3) for x in range(40)}) > 1, "every forest tile is identical"

    # density: desert is sprinkled, forest is solid, sea gets nothing
    hits = sum(decor(canvas, ":", 0, 0, x, y) for x in range(40) for y in range(40))
    rate, want = 100 * hits / 1600, DECOR[":"][2]
    assert abs(rate - want) < 8, f"desert decorated at {rate:.0f}%, configured {want}%"
    assert all(decor(canvas, "*", 0, 0, x, 3) for x in range(40))
    assert not any(decor(canvas, "~", 0, 0, x, 3) for x in range(40))

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
