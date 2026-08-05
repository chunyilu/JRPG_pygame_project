#!/usr/bin/env python3
"""The Highlands: a painted backdrop for the 40x56 valley in data/highland.txt.

The valley has no art pack of its own. The tileset sheet it was designed against
(data/Gemini_Generated_Image_*.png) is a generated picture of a tileset rather than a
tileset: its cells drift between 87 and 97 pixels so there is no grid to slice, and its
terrain does not tile -- the water cell's left and right edges differ by 252 per pixel,
which lays a visible seam across any field built from it. So it served as the *content*
reference -- grass, wood, water with sandy banks, crag, snowfield, volcano, castle,
bridge -- and the terrain here is painted instead.

Painted once into one backdrop, the way tiled_map and worldmap hand theirs over, rather
than drawn per frame: the valley is 1280x1792 and blitting a viewport out of it costs
nothing. Ground goes down for the whole map before any object, so a conifer or a peak
may overflow into the tile above without the next row painting over it.

Every motif is hashed from its tile coordinates, so scatter is stable -- the same tile
draws the same tree every time, and nothing shimmers when the camera moves.

    check: .venv/bin/python highland.py --test
"""
import sys
from pathlib import Path

import pygame

import pixelart

TILE = 32
SNOWLINE = 14                   # rows above this get snow on their peaks

# The one part of that sheet worth cutting up. Its terrain is unusable -- no grid, and it
# does not tile -- but its mountains are discrete objects sitting on a flat cream field,
# which crops cleanly and does not need to tile at all. Five peaks, hashed per tile, are
# what stops a rim of one repeated motif reading as wallpaper. Source rects are measured
# off the sheet by hand, the way village.py names its pack's cells, because the sheet's
# cells drift between 87 and 97 pixels and no arithmetic finds them.
SHEET = Path(__file__).parent / "data" / "Gemini_Generated_Image_j28na0j28na0j28n.png"
KEY, KEY_TOL = (245, 242, 221), 26              # the cream background, and how near counts
# Named by what they look like, not numbered: as PEAKS[0..4] the snow peak sat in both
# pools by mistake and the whole lower rim came out snow-capped in high summer.
ROCK = [(1035, 20, 87, 85), (1128, 20, 89, 85), (890, 20, 94, 85)]      # last one is wooded
SNOWY = [(1225, 20, 84, 85), (1035, 113, 87, 78), (1128, 113, 89, 78)]
CINDER = (1225, 113, 84, 78)                    # the one with lava still in its crater
PEAK_H = 46                                     # drawn taller than a tile, overflowing up

ART = {}                                        # "rock0".., "snow0".., "cinder" -> Surface


def _hash(tx, ty):
    return (tx * 73856093) ^ (ty * 19349663) & 0x7FFFFFFF


def _cut(sheet, rect, height):
    """One sprite off the sheet: key out the cream, crop to it, stand it `height` tall."""
    src = sheet.subsurface(rect).copy().convert_alpha()
    for x in range(src.get_width()):
        for y in range(src.get_height()):
            r, g, b, _ = src.get_at((x, y))
            if abs(r - KEY[0]) + abs(g - KEY[1]) + abs(b - KEY[2]) < KEY_TOL:
                src.set_at((x, y), (0, 0, 0, 0))
    box = src.get_bounding_rect()
    if not (box.w and box.h):
        return None
    wide = max(1, round(box.w * height / box.h))
    return pygame.transform.smoothscale(src.subsurface(box), (wide, height))


def load():
    """Cut the peaks out of the sheet. Missing sheet -> stays empty and paint() falls
    back to drawing them, the same bargain every other pack in this game strikes."""
    if ART or not SHEET.exists():
        return ART
    try:
        sheet = pygame.image.load(str(SHEET)).convert_alpha()
    except pygame.error:
        return ART
    for kind, rects in (("rock", ROCK), ("snow", SNOWY)):
        for i, rect in enumerate(rects):
            art = _cut(sheet, rect, PEAK_H)
            if art:
                ART[f"{kind}{i}"] = art
    art = _cut(sheet, CINDER, PEAK_H)
    if art:
        ART["cinder"] = art
    return ART


def _ground(surf, ch, tile, px, py, tx, ty):
    """The floor of one tile: flat colour, then a little texture so it is not a slab."""
    surf.fill(tile.color, (px, py, TILE, TILE))
    h = _hash(tx, ty)
    if ch == "~":
        for i in range(2):                                       # ripples
            wx, wy = px + (h >> (3 * i + 1)) % 20, py + (h >> (3 * i + 5)) % 26
            pygame.draw.line(surf, (108, 168, 226), (wx, wy), (wx + 9, wy), 2)
    elif ch == ":":
        for i in range(3):
            sx, sy = px + (h >> (2 * i + 1)) % 28, py + (h >> (2 * i + 7)) % 28
            pygame.draw.line(surf, (206, 186, 132), (sx, sy), (sx + 4, sy), 2)
    elif ch == ".":
        for i in range(3):                                       # grass tufts
            gx, gy = px + (h >> (2 * i + 1)) % 26, py + (h >> (2 * i + 9)) % 24
            pygame.draw.line(surf, (78, 138, 62), (gx, gy + 5), (gx + 2, gy), 2)
    elif ch in "nV":                          # the cone stands in the snowfield, so the
        for i in range(2):                    # ground under it is snow, not rock
            sx, sy = px + (h >> (2 * i + 3)) % 26, py + (h >> (2 * i + 11)) % 26
            pygame.draw.line(surf, (198, 210, 228), (sx, sy), (sx + 6, sy), 2)


def _object(surf, ch, px, py, tx, ty):
    """What stands on the tile, allowed to overflow upwards into the row above."""
    h = _hash(tx, ty)
    if ch == "A" and ART:                                        # a peak off the sheet
        # Not every tile: a peak on all of them crowds into one undifferentiated mass and
        # reads as wallpaper, which is the whole reason for cutting five of them out.
        # Three in four, hashed, leaves gaps of bare rock and the ridge gains a skyline.
        if h % 4 == 1:
            return
        # snow above the snowline, bare and wooded rock below, so the rim climbs with the
        # valley instead of being one wall of identical stone
        kind = "snow" if ty < SNOWLINE else "rock"
        pool = [k for k in ART if k.startswith(kind)]
        art = ART[pool[(h >> 5) % len(pool)]]
        surf.blit(art, (px + (TILE - art.get_width()) // 2 + (h >> 11) % 7 - 3,
                        py + TILE - art.get_height() + (h >> 17) % 5))
        return
    if ch == "V" and ART:
        return                                    # one sprite for the whole cone: _cinder
    if ch == "A":                                                # a ridge of rock
        cap = ty < SNOWLINE
        for k, (ox, base) in enumerate(((1, 30), (13, 33), (23, 29))):
            ox += (h >> (4 * k + 1)) % 3
            peak = base - 20 - (h >> (4 * k + 3)) % 7
            pygame.draw.polygon(surf, (146, 140, 134),
                                [(px + ox + 8, py + peak), (px + ox - 2, py + base),
                                 (px + ox + 18, py + base)])
            if cap:
                pygame.draw.polygon(surf, (236, 240, 246),
                                    [(px + ox + 8, py + peak), (px + ox + 3, py + peak + 7),
                                     (px + ox + 13, py + peak + 7)])
    elif ch == "*":                                              # conifers
        for k, (ox, oy) in enumerate(((5, 26), (17, 30), (11, 20))):
            ox += (h >> (4 * k + 1)) % 4
            pygame.draw.polygon(surf, (24, 68, 40),
                                [(px + ox, py + oy - 16), (px + ox - 6, py + oy),
                                 (px + ox + 6, py + oy)])
            pygame.draw.polygon(surf, (38, 96, 52),
                                [(px + ox, py + oy - 12), (px + ox - 5, py + oy - 2),
                                 (px + ox + 5, py + oy - 2)])
    elif ch == "^":                                              # crag boulders
        for k, (ox, oy) in enumerate(((4, 24), (18, 27))):
            ox += (h >> (4 * k + 5)) % 4
            pygame.draw.ellipse(surf, (118, 110, 96), (px + ox, py + oy, 12, 8))
            pygame.draw.ellipse(surf, (162, 152, 134), (px + ox + 1, py + oy, 10, 5))
    elif ch == "V":                                              # Mount Cinder
        pygame.draw.polygon(surf, (74, 58, 54), [(px + 16, py - 6), (px - 4, py + 32),
                                                 (px + 36, py + 32)])
        pygame.draw.polygon(surf, (96, 76, 70), [(px + 16, py - 2), (px + 4, py + 32),
                                                 (px + 28, py + 32)])
        if ty == 5:                                              # the crater, once
            pygame.draw.ellipse(surf, (214, 96, 40), (px + 8, py + 2, 16, 8))
            pygame.draw.ellipse(surf, (248, 196, 90), (px + 12, py + 4, 8, 4))
    elif ch == "=":                                              # planks over the water
        surf.fill((34, 96, 168), (px, py, TILE, TILE))
        pygame.draw.rect(surf, (150, 106, 58), (px, py + 5, TILE, 22))
        pygame.draw.rect(surf, (116, 80, 42), (px, py + 5, TILE, 3))
        for x in range(2, TILE, 7):
            pygame.draw.line(surf, (96, 64, 34), (px + x, py + 8), (px + x, py + 26), 2)
    elif ch in "CT":                                             # keep, or a walled town
        big = ch == "C"
        body = (188, 190, 198) if big else (196, 158, 106)
        pygame.draw.rect(surf, body, (px + 3, py + (6 if big else 13), 26, 26 if big else 19))
        if big:
            for x in (3, 12, 21):                                # battlements
                pygame.draw.rect(surf, body, (px + x, py + 1, 7, 7))
            pygame.draw.line(surf, (206, 62, 58), (px + 17, py - 4), (px + 26, py), 2)
        else:
            pygame.draw.polygon(surf, (188, 74, 62), [(px + 1, py + 13), (px + 16, py + 3),
                                                      (px + 31, py + 13)])
        pygame.draw.rect(surf, (30, 26, 30), (px + 13, py + 22, 7, 10))
    elif ch == "O":                                              # a cave mouth
        pygame.draw.rect(surf, (96, 84, 74), (px + 2, py + 8, 28, 24))
        pygame.draw.ellipse(surf, (18, 16, 18), (px + 9, py + 14, 14, 18))
    elif ch == "S":                                              # two pillars and a lintel
        # dark stone, not white: the Shrine of Ash stands in a snowfield, and in pale
        # marble it was invisible against it
        for x in (5, 22):
            pygame.draw.rect(surf, (128, 126, 144), (px + x, py + 12, 5, 20))
            pygame.draw.rect(surf, (168, 166, 184), (px + x, py + 12, 2, 20))
        pygame.draw.rect(surf, (110, 108, 126), (px + 2, py + 5, 28, 7))
        pygame.draw.rect(surf, (46, 42, 54), (px + 12, py + 20, 8, 12))    # the doorway


def _cinder(surf, grid):
    """Mount Cinder as one sprite over its whole cone, not one per tile.

    The anchor is derived from the map rather than written down: the lowest row of `V`,
    centred across it. Hard-coding a tile would go quietly wrong the next time the valley
    is redrawn, and a volcano half off its own mountain is exactly the kind of thing that
    survives a test suite.
    """
    cone = [(x, y) for y, row in enumerate(grid) for x, ch in enumerate(row) if ch == "V"]
    if not (cone and ART):
        return
    foot = max(y for _, y in cone)
    span = [x for x, y in cone if y == foot]
    art = ART["cinder"]
    tall = (foot - min(y for _, y in cone) + 1) * TILE + TILE // 2
    art = pygame.transform.smoothscale(art, (round(art.get_width() * tall / art.get_height()),
                                             tall))
    mid = (min(span) + max(span) + 1) / 2 * TILE
    surf.blit(art, (round(mid - art.get_width() / 2),
                    (foot + 1) * TILE - art.get_height()))


def paint(grid, tiles):
    """-> one Surface holding the whole valley, snapped to the game's pixel grid."""
    load()
    h, w = len(grid), len(grid[0])
    surf = pygame.Surface((w * TILE, h * TILE))
    for objects in (False, True):                     # all ground, then all objects
        for ty, row in enumerate(grid):
            for tx, ch in enumerate(row):
                px, py = tx * TILE, ty * TILE
                if objects:
                    _object(surf, ch, px, py, tx, ty)
                else:
                    _ground(surf, ch, tiles[ch], px, py, tx, ty)
    _cinder(surf, grid)
    return pixelart.snap(surf)


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    from collections import Counter
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))
    import field                                     # for the legend and the real map

    grid = field.load_map("highland.txt", field.HIGHLAND_TILES)
    art = paint(grid, field.HIGHLAND_TILES)
    assert art.get_size() == (len(grid[0]) * TILE, len(grid) * TILE)

    # every legend char has to paint something distinguishable, or the map reads as mush.
    # Painted on its own tile and compared: no two terrains may come out identical.
    shots = {}
    for ch in field.HIGHLAND_TILES:
        cell = pygame.Surface((TILE, TILE))
        _ground(cell, ch, field.HIGHLAND_TILES[ch], 0, 0, 3, 20)
        _object(cell, ch, 0, 0, 3, 20)
        shots[ch] = pygame.image.tobytes(cell, "RGB")
    # "V" is exempt: its cone is one sprite over the whole region, drawn by _cinder, so a
    # single V tile is bare snowfield by design. It gets checked on the real map below.
    shots.pop("V")
    same = [(a, b) for a in shots for b in shots if a < b and shots[a] == shots[b]]
    assert not same, f"these tiles paint identically: {same}"

    # ...and the cone does land: the painted V region must differ from plain snowfield,
    # whether it came off the sheet or was drawn. A volcano that quietly failed to draw
    # would leave a suspiciously smooth white patch and nothing else would complain.
    cone = [(x, y) for y, row in enumerate(grid) for x, ch in enumerate(row) if ch == "V"]
    snowy = [(x, y) for y, row in enumerate(grid) for x, ch in enumerate(row)
             if ch == "n" and (x, y) not in cone]
    assert cone and snowy
    def patch(spots):
        return {art.get_at((x * TILE + TILE // 2, y * TILE + TILE // 2))[:3] for x, y in spots}
    assert patch(cone) - patch(snowy), "Mount Cinder painted as bare snowfield"

    # the scatter is stable per tile and does vary between tiles, the same contract
    # tileset.decor holds: a shimmering forest is the bug this catches
    def shot(ch, tx, ty):
        cell = pygame.Surface((TILE, TILE))
        _ground(cell, ch, field.HIGHLAND_TILES[ch], 0, 0, tx, ty)
        _object(cell, ch, 0, 0, tx, ty)
        return pygame.image.tobytes(cell, "RGB")
    assert shot("*", 7, 22) == shot("*", 7, 22), "the wood is not stable per tile"
    assert len({shot("*", x, 22) for x in range(20)}) > 1, "every wood tile is identical"
    # the snowline: compared across a run of columns, not two tiles, because one in four
    # rim tiles deliberately draws no peak at all and a single pair can be two of those
    high = {shot("A", x, 4) for x in range(24)}
    low = {shot("A", x, 40) for x in range(24)}
    assert high - low, "peaks ignore the snowline"

    # and the painting is not a flat slab: a real spread of colour, mostly land
    seen = Counter()
    for x in range(0, art.get_width(), 9):
        for y in range(0, art.get_height(), 9):
            seen[art.get_at((x, y))[:3]] += 1
    assert len(seen) > 40, f"the backdrop uses only {len(seen)} colours"

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
