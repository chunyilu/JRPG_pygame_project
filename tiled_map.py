#!/usr/bin/env python3
"""Load a Tiled JSON map (.tmj) from the PUNY_WORLD overworld pack.

Tiled maps are three tile layers over one atlas: ground (grass, road, water), then
cliff edges, then trees and the odd bridge. They carry no collision data, so both
of the things the game needs are derived from the art itself:

  * the picture -- every layer composited once into one backdrop Surface, which the
    field then blits a viewport out of, instead of painting a few hundred tiles a frame
  * the collision -- from what each layer is for, plus how each tile looks. Ground
    reads blue for water and tan for road. The second layer is cliff edges: a
    mostly-opaque tile there is a rock face and blocks, a sparse one is the lip
    above it and does not. The third is scenery: dense canopy becomes forest, which
    like every other forest in this game you may walk into and regret. A brown tile
    over water is a bridge, and always walkable.

The layer split is this pack's convention, not something Tiled guarantees; a map
that ordered its layers differently would need its own rule.

The result is a char grid in the same one-char-per-tile legend as the rest of the
game, so nothing downstream needs to know this world came from Tiled.

    check: .venv/bin/python tiled_map.py --test
"""
import json
import sys
from pathlib import Path

import pygame

PACK = Path(__file__).parent / "data" / "map" / "PUNY_WORLD_v1"
ATLAS = PACK / "punyworld-overworld-tileset.png"
SRC = 16                        # the pack's tile size
SCALE = 2                       # ...doubled to the game's 32px tile
TILE = SRC * SCALE

WATER, ROAD, GRASS, FOREST, BLOCK = "~", ",", ".", "*", "#"

_loaded = {}


def _is_water(rgb):
    # +50 rather than a smaller margin so the green-cyan shore blends count as water
    # too. Leave them walkable and the river is fordable anywhere, which makes the
    # bridge decorative and the map's geography meaningless.
    r, g, b = rgb
    return b > r + 50


def _is_road(rgb):
    r, g, b = rgb
    return r > 140 and r > b + 45 and g > 110


def _is_bridge(rgb):
    r, g, b = rgb
    return r > g + 40 and r > b + 60


def _look(tile):
    """(opaque fraction, mean colour of the opaque pixels) of one atlas tile."""
    opaque = [c for x in range(SRC) for y in range(SRC)
              for c in [tile.get_at((x, y))] if c[3] > 128]
    if not opaque:
        return 0.0, (0, 0, 0)
    n = len(opaque)
    return n / (SRC * SRC), tuple(sum(c[i] for c in opaque) // n for i in range(3))


def load(name="samplemap1.tmj"):
    """-> (grid of legend chars, backdrop Surface), or (None, None) with no pack."""
    if name in _loaded:
        return _loaded[name]
    path = PACK / "Tiled" / name
    if not (path.exists() and ATLAS.exists()):
        return None, None
    try:
        spec = json.loads(path.read_text())
        atlas = pygame.image.load(str(ATLAS)).convert_alpha()
    except (OSError, ValueError, pygame.error):
        return None, None

    cols = atlas.get_width() // SRC
    w, h = spec["width"], spec["height"]
    layers = [layer["data"] for layer in spec["layers"] if layer.get("data")]

    art, seen = {}, {}                           # gid -> Surface, gid -> (frac, rgb)
    for gid in {g for data in layers for g in data if g}:
        i = gid - 1
        art[gid] = atlas.subsurface(((i % cols) * SRC, (i // cols) * SRC, SRC, SRC))
        seen[gid] = _look(art[gid])

    backdrop = pygame.Surface((w * SRC, h * SRC), pygame.SRCALPHA)
    for data in layers:
        for i, gid in enumerate(data):
            if gid:
                backdrop.blit(art[gid], ((i % w) * SRC, (i // w) * SRC))
    backdrop = pygame.transform.scale(backdrop, (w * TILE, h * TILE))

    ground = layers[0]
    cliffs = layers[1] if len(layers) > 1 else []
    scenery = layers[2:]

    def dense(data, i):
        gid = data[i] if data else 0
        if not gid:
            return False
        frac, rgb = seen[gid]
        return frac > 0.55 and not _is_road(rgb)

    grid = []
    for y in range(h):
        row = []
        for x in range(w):
            i = y * w + x
            base = ground[i]
            water = bool(base) and _is_water(seen[base][1])
            bridge = any(data[i] and _is_bridge(seen[data[i]][1])
                         for data in (cliffs, *scenery) if data)
            if bridge:
                row.append(ROAD)                 # a crossing, and safe footing
            elif dense(cliffs, i):
                row.append(BLOCK)                # a rock face
            elif water:
                row.append(WATER)
            elif any(dense(data, i) for data in scenery):
                row.append(FOREST)               # canopy: walk in at your own risk
            elif _is_road(seen[base][1]) if base else False:
                row.append(ROAD)
            else:
                row.append(GRASS)
        grid.append("".join(row))

    _loaded[name] = (grid, backdrop)
    return _loaded[name]


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    from collections import deque
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))

    global PACK
    real, PACK = PACK, Path("/nonexistent-tiled-pack")
    assert load("samplemap1.tmj") == (None, None)
    PACK = real

    grid, backdrop = load()
    if grid is None:
        print("ok (no pack installed, fallback path only)")
        return

    h, w = len(grid), len(grid[0])
    assert (w, h) == (50, 50), (w, h)
    assert backdrop.get_size() == (w * TILE, h * TILE)
    assert len({len(r) for r in grid}) == 1
    assert set("".join(grid)) <= {WATER, ROAD, GRASS, FOREST, BLOCK}

    # the classifier has to find all five, in sane proportions: a map that is 90%
    # cliff, or has no water at all, means the thresholds have drifted
    flat = "".join(grid)
    share = {ch: 100 * flat.count(ch) / (w * h) for ch in (WATER, ROAD, GRASS, FOREST, BLOCK)}
    assert 1 < share[WATER] < 20, f"water is {share[WATER]:.0f}% of the map"
    assert 3 < share[ROAD] < 25, f"road is {share[ROAD]:.0f}%"
    assert 15 < share[FOREST] < 60, f"forest is {share[FOREST]:.0f}%"
    assert 5 < share[BLOCK] < 40, f"cliff is {share[BLOCK]:.0f}%"
    assert share[GRASS] > 15, f"open ground is {share[GRASS]:.0f}%"

    # and it has to be a *world*: most of it reachable from one spot, both banks of
    # the river included, or the bridge was classified wrong
    walk = {(x, y) for y in range(h) for x in range(w) if grid[y][x] != BLOCK
            and grid[y][x] != WATER}
    start = max(walk, key=lambda p: sum((p[0] + dx, p[1] + dy) in walk
                                        for dx in (-1, 0, 1) for dy in (-1, 0, 1)))
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            step = (x + dx, y + dy)
            if step in walk and step not in seen:
                seen.add(step)
                queue.append(step)
    assert len(seen) > 0.8 * len(walk), \
        f"only {100 * len(seen) / len(walk):.0f}% of open ground is connected"
    west = [p for p in seen if p[0] < 10]
    east = [p for p in seen if p[0] > 40]
    assert west and east, "the river cuts the map in two — is the bridge blocked?"

    # the bridge specifically: it must be walkable, and it must matter. Blocking it
    # has to strand a real part of the map, or the river is being forded somewhere
    # and the geography means nothing
    spec = json.loads((PACK / "Tiled" / "samplemap1.tmj").read_text())
    art = {}
    cols = pygame.image.load(str(ATLAS)).convert_alpha().get_width() // SRC
    atlas = pygame.image.load(str(ATLAS)).convert_alpha()
    for gid in {g for layer in spec["layers"] for g in layer["data"] if g}:
        i = gid - 1
        art[gid] = _look(atlas.subsurface(((i % cols) * SRC, (i // cols) * SRC, SRC, SRC)))
    spans = {(i % w, i // w) for layer in spec["layers"]
             for i, g in enumerate(layer["data"]) if g and _is_bridge(art[g][1])}
    assert spans, "the map has no bridge art at all"
    assert all(grid[y][x] != BLOCK and grid[y][x] != WATER for x, y in spans), \
        "a bridge tile came out impassable"

    def reach(blocked):
        found, queue = {start}, deque([start])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                step = (x + dx, y + dy)
                if step in walk and step not in found and step not in blocked:
                    found.add(step)
                    queue.append(step)
        return len(found)

    assert reach(set()) - reach(spans) > 50, "closing the bridge changes nothing"

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
