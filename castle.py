#!/usr/bin/env python3
"""Castle tiles, cut from the generated castle sheet in data/map/.

That sheet is not a tileset in the usual sense -- it was drawn as a *picture* of one,
so its cells are on no grid at all: about 94px apart, drifting, with the odd narrow
piece wedged in. So there is no cell arithmetic here. Every tile names the exact
rectangle it occupies, found once by walking out from a seed pixel to the cream paper
around it, and written down. If the sheet is ever redrawn these numbers all move.

Tiles come out at 32px, floors and walls exactly, and anything standing on the floor
scaled by its width and allowed to overflow upwards -- so a throne is taller than the
square it sits on, the way interior.py and village.py do it.

    check: .venv/bin/python castle.py --test
"""
import sys
from pathlib import Path

import pygame

SHEET = (Path(__file__).parent / "data" / "map"
         / "Gemini_Generated_Image_d2l3k8d2l3k8d2l3.png")
TILE = 32

# char -> (source rect on the sheet, walkable, fallback colour)
SPEC = {
    ".": ((425, 107, 90, 91), True, (128, 130, 134)),      # flagstone floor
    ",": ((705, 199, 90, 91), True, (150, 40, 44)),         # the red carpet
    "-": ((520, 201, 90, 89), True, (150, 40, 44)),         # ...running crossways
    "=": ((798, 200, 90, 90), True, (150, 118, 70)),        # boards, by the hearths
    "#": ((96, 21, 90, 85), False, (156, 158, 162)),        # wall, torch brackets
    "%": ((425, 201, 90, 89), False, (140, 142, 146)),      # plain block wall
    "w": ((423, 20, 91, 86), False, (110, 112, 118)),       # barred window
    "+": ((990, 22, 48, 84), True, (122, 82, 44)),          # the door out
    "D": ((107, 389, 69, 87), False, (100, 68, 40)),        # a door that stays shut
    "T": ((902, 293, 70, 90), False, (170, 40, 50)),        # the throne
    "t": ((985, 318, 138, 58), False, (146, 100, 56)),      # the banquet table
    "b": ((1130, 215, 86, 74), False, (96, 68, 48)),        # bookshelves
    "f": ((901, 482, 72, 92), False, (200, 120, 50)),       # a lit fireplace
    "n": ((985, 391, 45, 81), False, (176, 40, 44)),        # the King's banner
}

FLOOR, CARPET = ".", ","
UNDER = {",": ".", "-": ".", "=": ".", "+": ",",   # what is painted beneath each tile:
         "T": ",", "n": "%", "D": "%", "w": "%"}   # carpet under the throne, and so on
SQUARE = set(".,-=#%w")                # fills its tile exactly; everything else stands

IMAGES = {}


def load():
    if IMAGES or not SHEET.exists():
        return IMAGES
    try:
        sheet = pygame.image.load(str(SHEET)).convert_alpha()
    except pygame.error:
        return IMAGES                              # unreadable sheet: no castle art
    for ch, (rect, _, _) in SPEC.items():
        art = sheet.subsurface(rect)
        if ch in SQUARE:
            size = (TILE, TILE)
        else:                                      # keep the shape, one tile wide
            size = (TILE, max(1, round(rect[3] * TILE / rect[2])))
        IMAGES[ch] = pygame.transform.smoothscale(art, size)
    return IMAGES


def walkable(ch):
    return SPEC[ch][1]


def _blit(surf, ch, px, py):
    """One tile of art, standing on the bottom of its square and overflowing up."""
    image = IMAGES.get(ch)
    if image is None:
        rect, _, colour = SPEC[ch]
        high = TILE if ch in SQUARE else min(2 * TILE, round(rect[3] * TILE / rect[2]))
        pygame.draw.rect(surf, colour, (px, py + TILE - high, TILE, high))
        return
    surf.blit(image, (px, py + TILE - image.get_height()))


def ground(surf, ch, px, py, tx, ty):
    """Pass one: flagstones everywhere, with the carpet laid over them where it lies."""
    base = ch if ch in SQUARE else UNDER.get(ch, FLOOR)
    if base != FLOOR:
        _blit(surf, FLOOR, px, py)                 # it is all one stone floor beneath
    _blit(surf, base, px, py)


def obj(surf, ch, px, py, tx, ty):
    """Pass two: what stands in the hall, painted over every floor already down."""
    if ch not in SQUARE:
        _blit(surf, ch, px, py)


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))
    canvas = pygame.Surface((320, 320), pygame.SRCALPHA)
    canvas.fill((0, 0, 0, 0))

    global SHEET
    real, SHEET = SHEET, Path("/nonexistent-castle-sheet.png")
    assert load() == {}
    ground(canvas, ".", 0, 0, 0, 0)                # must not raise without the sheet
    obj(canvas, "T", 0, 96, 0, 3)
    SHEET = real

    if not SHEET.exists():
        print("ok (no sheet installed, fallback path only)")
        return

    load()
    for ch in SPEC:
        image = IMAGES[ch]
        assert image.get_width() == TILE, f"{ch} is {image.get_width()}px wide"
        assert image.get_flags() & pygame.SRCALPHA, f"{ch} lost transparency"
        if ch in SQUARE:
            assert image.get_height() == TILE, f"{ch} must fill its tile exactly"
        else:
            assert TILE * 0.4 <= image.get_height() <= TILE * 3, ch
    # the pieces have to be told apart: a floor that matches its wall is no map
    assert len({pygame.image.tobytes(IMAGES[c], "RGB") for c in SQUARE}) == len(SQUARE)

    # the throne is taller than its square and grows upwards, never down
    canvas.fill((0, 0, 0, 0))
    obj(canvas, "T", 0, 3 * TILE, 0, 3)
    painted = canvas.get_bounding_rect()
    assert painted.bottom <= 4 * TILE, "the throne hangs below its tile"
    assert painted.top < 3 * TILE, "the throne did not overflow upwards"

    # the carpet is laid on the floor, not instead of it -- so a carpet tile and a
    # bare floor tile are not the same picture
    shots = []
    for ch in (FLOOR, CARPET):
        canvas.fill((0, 0, 0, 0))
        ground(canvas, ch, 0, 0, 0, 0)
        shots.append(pygame.image.tobytes(canvas, "RGBA"))
    assert shots[0] != shots[1], "the carpet did not cover the flagstones"

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
