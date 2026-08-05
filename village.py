#!/usr/bin/env python3
"""Village tiles, cut from Hypnobius' Medieval Village Exterior pack in data/.

The pack is 48px cells, the game is 32px tiles, so everything comes down by two
thirds -- smoothscaled, since at 2/3 nearest-neighbour eats every third pixel row.

A house is built out of tiles rather than one big sprite: a roof row on top, two
wall rows under it, a door in the lower one. The door and window art hang on a
wall, so they paint the wall first, the same trick interior.py uses for its
window. Everything else stands on the ground and may overflow upwards, which
works because a world draws all its ground before any of its objects.

Optional like every pack here: without it the village still draws, in flat colour.

    check: .venv/bin/python village.py --test
"""
import sys
from pathlib import Path

import pygame

PACK = (Path(__file__).parent / "data" / "MedievalVillageExteriorv1.0" / "RawAssets")
CELL, TILE = 48, 32                    # pack cell -> game tile

# char -> (sheet, source rect in sheet pixels, walkable, fallback colour). A ground
# texture names its whole repeating block, not one cell: the pack's grass only tiles
# as a 2x3 patch, and one cell of it repeated lays a visible grid over the field.
SPEC = {
    ".": ("Ground", (0, 0, 96, 144), True, (92, 148, 66)),          # grass
    ",": ("Ground", (192, 0, 96, 144), True, (150, 142, 148)),      # cobbled road
    "G": ("Ground", (192, 0, 96, 144), True, (150, 142, 148)),      # the road out
    "#": ("Walls", (96, 48, 48, 48), False, (206, 178, 130)),       # plaster wall
    "%": ("Walls", (0, 48, 48, 48), False, (150, 90, 70)),          # brick wall
    "^": ("Roofs", (0, 0, 48, 48), False, (86, 58, 52)),            # shingle roof
    "&": ("Roofs", (96, 0, 48, 48), False, (52, 64, 86)),           # slate roof
    "+": ("Props_Decor", (48, 384, 48, 96), True, (122, 82, 44)),   # the hero's door
    "D": ("Props_Decor", (48, 384, 48, 96), False, (122, 82, 44)),  # someone else's
    "w": ("Props_Decor", (48, 288, 48, 48), False, (108, 88, 62)),  # window
    "b": ("Props_Decor", (0, 0, 48, 48), False, (120, 96, 62)),     # barrel
    "c": ("Props_Decor", (48, 0, 48, 48), False, (166, 124, 72)),   # crate
    "f": ("Props_Decor", (48, 192, 48, 96), False, (120, 92, 58)),  # fence
    "t": ("Props_Decor", (144, 96, 48, 96), False, (60, 140, 62)),  # bush
    "l": ("Props_Decor", (0, 192, 48, 96), False, (86, 86, 92)),    # lamp post
    "*": ("Props_Decor", (0, 432, 48, 48), False, (190, 90, 130)),  # flower box
}

GRASS, ROAD = ".", ","
PAVED = {",", "G", "+", "D"}           # road runs under the gate and up to the doors
ON_WALL = {"+": "#", "D": "#", "w": "#"}       # painted over the wall they sit in
CENTRED = {"w"}                        # hung in the middle of its tile, not stood on
TILING = set(".,G#%^&")                # textures laid edge to edge, so no bleed allowed

IMAGES = {}                            # char -> one prop Surface
TEXTURES = {}                          # tiling char -> (tiles, cols, rows)


def _texture(block, w, h):
    """Cut a repeating block into game tiles, indexed later by tile coordinate.

    Smoothscaling art samples past its border, so shrinking the block on its own
    leaves a pale rim on every edge tile -- a grid over the whole field. Laying the
    block out 3x3 first, shrinking that and keeping the middle copy gives each tile
    the neighbours it will actually have.
    """
    cols, rows = w // CELL, h // CELL
    big = pygame.Surface((w * 3, h * 3), pygame.SRCALPHA)
    for i in range(3):
        for j in range(3):
            big.blit(block, (i * w, j * h))
    small = pygame.transform.smoothscale(big, (cols * TILE * 3, rows * TILE * 3))
    return ([small.subsurface(((cols + c) * TILE, (rows + r) * TILE, TILE, TILE)).copy()
             for r in range(rows) for c in range(cols)], cols, rows)


def _pick(ch, tx, ty):
    """The tile of a repeating texture that belongs at this map coordinate."""
    tiles, cols, rows = TEXTURES[ch]
    return tiles[(ty % rows) * cols + (tx % cols)]


def load():
    if IMAGES or not PACK.is_dir():
        return IMAGES
    sheets = {}
    try:
        for ch, (sheet, (x, y, w, h), _, _) in SPEC.items():
            if sheet not in sheets:
                sheets[sheet] = pygame.image.load(str(PACK / f"{sheet}.png")).convert_alpha()
            src = sheets[sheet].subsurface((x, y, w, h))
            if ch in TILING:
                TEXTURES[ch] = _texture(src, w, h)
                continue
            art = src.get_bounding_rect()          # trim the slack so feet anchor true
            if not art.w:
                continue
            IMAGES[ch] = pygame.transform.smoothscale(
                src.subsurface(art),
                (max(1, round(art.w * TILE / CELL)), max(1, round(art.h * TILE / CELL))))
    except (pygame.error, ValueError, FileNotFoundError):
        IMAGES.clear()                             # a broken pack is no pack
        TEXTURES.clear()
    return IMAGES


def walkable(ch):
    return SPEC[ch][2]


def ground(surf, ch, px, py, tx, ty):
    """Pass one: road under the road, grass under everything else."""
    base = ROAD if ch in PAVED else GRASS
    if base not in TEXTURES:
        pygame.draw.rect(surf, SPEC[base][3], (px, py, TILE, TILE))
    else:
        surf.blit(_pick(base, tx, ty), (px, py))


def obj(surf, ch, px, py, tx, ty):
    """Pass two: what stands on the tile, anchored by its feet, overflowing upwards."""
    if ch in (GRASS, ROAD, "G"):
        return
    if ch in ON_WALL:
        obj(surf, ON_WALL[ch], px, py, tx, ty)     # the wall it is set into
    if ch in TILING:                               # a wall or a roof: fills its tile
        if ch in TEXTURES:
            surf.blit(_pick(ch, tx, ty), (px, py))
        else:
            pygame.draw.rect(surf, SPEC[ch][3], (px, py, TILE, TILE))
        return
    image = IMAGES.get(ch)
    if image is None:                              # no pack: a block of its colour
        _, (_, _, w, h), _, colour = SPEC[ch]
        top = py + TILE - round(h * TILE / CELL)
        pygame.draw.rect(surf, colour, (px + 1, top + 1, TILE - 2, py + TILE - top - 2))
        return
    x = px + (TILE - image.get_width()) // 2
    y = (py + (TILE - image.get_height()) // 2 if ch in CENTRED
         else py + TILE - image.get_height())
    surf.blit(image, (x, y))


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))
    canvas = pygame.Surface((320, 320), pygame.SRCALPHA)
    canvas.fill((0, 0, 0, 0))

    global PACK
    real, PACK = PACK, Path("/nonexistent-village-pack")
    assert load() == {}
    ground(canvas, ".", 0, 0, 0, 0)                # must not raise without the pack
    obj(canvas, "^", 0, 0, 0, 0)
    obj(canvas, "+", 0, 96, 0, 3)
    PACK = real

    if not PACK.is_dir():
        print("ok (no pack installed, fallback path only)")
        return

    load()
    for ch in set(SPEC) - TILING:
        image = IMAGES[ch]
        assert image.get_bounding_rect().size == image.get_size(), f"{ch} not trimmed"
        assert image.get_height() >= TILE * 0.4, f"{ch} came out too small to see"
        assert image.get_width() <= TILE, f"{ch} is wider than its tile"
    for ch in TILING:
        tiles, cols, rows = TEXTURES[ch]
        assert len(tiles) == cols * rows and all(t.get_size() == (TILE, TILE)
                                                 for t in tiles), f"{ch} does not tile"
        # a repeating block must vary across itself, or it may as well be one cell
        if cols * rows > 1:
            assert len({pygame.image.tobytes(t, "RGB") for t in tiles}) > 1, ch
    # the same coordinate always draws the same tile, and grass is not road
    assert _pick(GRASS, 5, 7) is _pick(GRASS, 5, 7)
    assert (pygame.image.tobytes(_pick(GRASS, 0, 0), "RGB")
            != pygame.image.tobytes(_pick(ROAD, 0, 0), "RGB"))

    # a door is taller than its tile: it grows up into the wall, never down
    canvas.fill((0, 0, 0, 0))
    obj(canvas, "+", 0, 3 * TILE, 0, 3)
    painted = canvas.get_bounding_rect()
    assert painted.bottom <= 4 * TILE, "the door hangs below its tile"
    assert painted.top < 3 * TILE, "the door did not reach up into the wall"

    # ...and a window sits inside its tile, wall and all
    canvas.fill((0, 0, 0, 0))
    obj(canvas, "w", 0, 3 * TILE, 0, 3)
    painted = canvas.get_bounding_rect()
    assert 3 * TILE <= painted.top and painted.bottom <= 4 * TILE, "the window drifted"

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
