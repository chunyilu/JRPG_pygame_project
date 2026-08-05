#!/usr/bin/env python3
"""The world map: data/map/WorldMap.png, an RPG Maker export of the World_* tilesets.

The export is a finished picture, 16px to the tile, with the autotiled shores,
forests and mountain ranges already assembled. Doubling it lands exactly on the
game's 32px tile, so the map is used as it is and only the collision has to be
worked out -- which is done from the colour of each cell, since a flat PNG carries
nothing else.

The classifier reads ratios, never brightness alone: the export is vignetted, so
the same sea is (36,111,164) mid-map and (6,36,59) in the corner. Blue is blue
either way.

Any map exported the same way drops in beside this one and works: same 16px cells,
same palette.

    check: .venv/bin/python worldmap.py --test
"""
import sys
from pathlib import Path

import pygame

MAPS = Path(__file__).parent / "data" / "map"
SRC = 16                        # the export's tile size
SCALE = 2                       # ...doubled to the game's 32px tile
TILE = SRC * SCALE

SEA, VOID, SAND, GRASS, FOREST, PEAK, SNOW, BLIGHT = "~", "#", ":", ".", "*", "A", "n", "v"

_loaded = {}


def classify(rgb):
    """One cell's mean colour -> a legend char."""
    r, g, b = rgb
    if max(rgb) < 30:
        return VOID                              # the vignette past the map's edge
    if b > g * 1.15 and b > r * 1.5:
        return SEA                               # by ratio: the vignette dims the sea
    if b > g + 18 and b > r + 25:                # to a fifth of its mid-map colour
        return SEA
    if r > g + 18 and b > g + 10:
        return BLIGHT                            # the purple waste in the south-west
    if min(rgb) > 185:
        return SNOW
    if g > r + 20:
        return FOREST
    if g + 12 > r and g > b + 35:
        return GRASS                             # RPG Maker grassland is yellow-green
    if r > g + 12 and g > b + 20:
        return SAND                              # beach, desert, and the roads on them
    return PEAK                                  # whatever is left is rock


def load(name="WorldMap.png"):
    """-> (grid of legend chars, backdrop Surface), or (None, None) with no export."""
    if name in _loaded:
        return _loaded[name]
    path = MAPS / name
    if not path.exists():
        return None, None
    try:
        image = pygame.image.load(str(path)).convert()
    except pygame.error:
        return None, None

    w, h = image.get_width() // SRC, image.get_height() // SRC
    grid = []
    for cy in range(h):
        row = []
        for cx in range(w):
            cell = image.subsurface((cx * SRC, cy * SRC, SRC, SRC))
            row.append(classify(pygame.transform.average_color(cell)[:3]))
        grid.append("".join(row))

    backdrop = pygame.transform.scale(image, (w * TILE, h * TILE))   # 2x, so no blur
    _loaded[name] = (grid, backdrop)
    return _loaded[name]


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    from collections import Counter, deque
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))

    global MAPS
    real, MAPS = MAPS, Path("/nonexistent-map-folder")
    assert load() == (None, None)
    MAPS = real

    grid, backdrop = load()
    if grid is None:
        print("ok (no export installed, fallback path only)")
        return

    h, w = len(grid), len(grid[0])
    assert (w, h) == (51, 39), (w, h)
    assert backdrop.get_size() == (w * TILE, h * TILE)
    assert len({len(row) for row in grid}) == 1

    # it has to come out a *world*: mostly sea, a real continent in it, and one of
    # every climate the export shows -- snow in the north, desert, forest, the waste
    share = Counter("".join(grid))
    assert 35 < 100 * share[SEA] / (w * h) < 65, f"sea is {share[SEA]} cells"
    for ch, least in ((GRASS, 60), (FOREST, 40), (SAND, 90), (PEAK, 40),
                      (SNOW, 8), (BLIGHT, 8)):
        assert share[ch] >= least, f"{ch}: only {share[ch]} cells, expected {least}+"
    north = "".join(grid[y] for y in range(h // 3))
    assert north.count(SNOW) > 0.7 * share[SNOW], "the snowfield is not in the north"

    # the land is one continent, not confetti: the largest walkable body has to hold
    # most of the walkable ground, or the shoreline is being cut in the wrong place
    walk = {(x, y) for y in range(h) for x in range(w) if grid[y][x] not in (SEA, VOID, PEAK)}
    seen, biggest = set(), set()
    for start in walk:
        if start in seen:
            continue
        found, queue = {start}, deque([start])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                step = (x + dx, y + dy)
                if step in walk and step not in found:
                    found.add(step)
                    queue.append(step)
        seen |= found
        biggest = max(biggest, found, key=len)
    assert len(biggest) > 0.55 * len(walk), \
        f"the mainland is only {100 * len(biggest) / len(walk):.0f}% of the land"

    # the vignette must not eat the map: the frame is void, the middle never is
    assert grid[0][0] == VOID and grid[h - 1][w - 1] == VOID
    assert VOID not in "".join(row[10:-10] for row in grid[8:-8])

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
