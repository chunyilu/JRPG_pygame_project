#!/usr/bin/env python3
"""One filter that makes every art pack in data/ read as the same pixel art.

The packs disagree, badly. PUNY_WORLD is true 16px pixel art nearest-scaled 2x:
crisp blocks, a dozen colours a tile, hard edges. The CraftPix chibi hero and the
desert tileset are high-resolution vector renders smoothscaled down -- soft
gradients, anti-aliased outlines, 900-odd colours in a 150px sprite. Standing side
by side they look like two different games.

PUNY_WORLD wins, being the only pack already in the style this game wants, so
everything else is snapped to its terms:

  * one art pixel per GRID screen pixels -- the same grid PUNY_WORLD lands on
  * LEVELS steps per colour channel, so gradients band instead of smearing
  * alpha thresholded, because pixel art has hard edges and no soft drop shadow

Colour work is a byte lookup table through bytes.translate: the surfaces are small,
this venv has no numpy, and the C-speed stdlib call is the whole implementation.

GRID and LEVELS are the two dials. Raise GRID for chunkier art, lower LEVELS for a
flatter palette; GRID=1 posterises without pixelating.

    check: .venv/bin/python pixelart.py --test
"""
import sys
from functools import lru_cache

import pygame

GRID = 2                        # screen pixels per art pixel; PUNY_WORLD's 16px @ 2x
LEVELS = 16                     # colour steps per channel. Fewer looks like the obvious
                                # win and is not: at 8 the chibi pack's soft gradients
                                # posterise into *speckle*, and per-channel snapping
                                # drags hues off (olive turbans, a green-banded blue
                                # slime). 16 bands cleanly and holds the hue. The blocky
                                # read comes from GRID anyway, not from the palette
CUT = 64                        # alpha at or above this is opaque, below is gone. Low,
                                # because the chibi pack's bosses wear a soft outer glow
                                # and a 128 cut trims 13% off their silhouette


@lru_cache(maxsize=8)
def _colour(levels):
    """256-byte table snapping a channel to `levels` evenly spaced values."""
    step = 255 / (levels - 1)
    return bytes(min(255, round(round(v / step) * step)) for v in range(256))


_ALPHA = bytes(0 if v < CUT else 255 for v in range(256))


def snap(image, grid=GRID, levels=LEVELS):
    """Pixelate and posterise one Surface, same size out as in.

    Downscale smoothly (averaging the detail away is what makes a *block* rather
    than one arbitrary sampled pixel), then back up with nearest so the blocks stay
    square-edged.
    """
    w, h = image.get_size()
    if grid > 1:
        small = pygame.transform.smoothscale(image, (max(1, w // grid), max(1, h // grid)))
        image = pygame.transform.scale(small, (w, h))
    buf = bytearray(pygame.image.tobytes(image, "RGBA"))
    alpha = bytes(buf[3::4]).translate(_ALPHA)      # hold it: the colour pass eats it
    buf = bytearray(buf.translate(_colour(levels)))
    buf[3::4] = alpha
    return pygame.image.frombytes(bytes(buf), (w, h), "RGBA")


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))

    # the table keeps the ends pure -- black stays black, white stays white, or every
    # sprite comes out washed toward the middle
    for levels in (2, 4, 6, 16):
        table = _colour(levels)
        assert table[0] == 0 and table[255] == 255, levels
        assert len(set(table)) == levels, f"{levels} levels gave {len(set(table))}"
        assert all(table[v] >= table[v - 1] for v in range(1, 256)), "not monotonic"

    # a smooth gradient with a soft edge: exactly what the CraftPix packs look like
    src = pygame.Surface((64, 64), pygame.SRCALPHA)
    for x in range(64):
        for y in range(64):
            src.set_at((x, y), (x * 4, y * 4, 128, min(255, x * 4)))

    out = snap(src)
    assert out.get_size() == src.get_size()
    assert out.get_flags() & pygame.SRCALPHA, "lost transparency"

    def shades(surf):
        w, h = surf.get_size()
        return {surf.get_at((x, y))[:3] for x in range(w) for y in range(h)}

    assert len(shades(out)) < len(shades(src)) / 4, "posterising barely reduced anything"
    assert all(c in _colour(LEVELS) for rgb in shades(out) for c in rgb), "off-palette"

    # hard edges: no half-transparent pixel survives, which is what kills the
    # anti-aliased outline the chibi pack ships with
    alphas = {out.get_at((x, y))[3] for x in range(64) for y in range(64)}
    assert alphas <= {0, 255}, f"soft alpha left over: {sorted(alphas - {0, 255})[:5]}"

    # blocks are GRID wide: sampling every GRID'th pixel loses nothing, sampling
    # every pixel is redundant. Checked on a row inside the opaque half.
    row = [out.get_at((x, 40))[:3] for x in range(GRID * 8)]
    assert all(row[i] == row[i - i % GRID] for i in range(len(row))), "blocks not aligned"

    # the dials do what they say
    assert len(shades(snap(src, levels=2))) < len(shades(out)), "LEVELS does nothing"
    assert snap(src, grid=1).get_size() == src.get_size()
    flat = snap(pygame.Surface((3, 3), pygame.SRCALPHA), grid=8)   # smaller than a block
    assert flat.get_size() == (3, 3), "a sprite thinner than one block must survive"

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
