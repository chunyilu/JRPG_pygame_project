# The Last Slayer

A Dragon Quest I (NES, 1986) remake in pygame. One hero, one enemy at a time,
top-down overworld Alefgard, turn-based battles. The appeal is pacing and tone,
not mechanics depth.

## Run it

```bash
python -m venv .venv
.venv/bin/pip install pygame-ce
.venv/bin/python main.py
```

`pygame-ce` — same `import pygame` API, and it builds on Python 3.14 where
plain `pygame` does not.

Controls: **arrows** walk, **Z**/Enter confirm, **X**/Esc cancel, **M** map,
**G** auto-walk to Tantegel. 640×480, keyboard only.

## Other entry points

```bash
.venv/bin/python dq_battle.py          # arena mode: nothing but battles
.venv/bin/python sounds.py             # play every effect once
```

## Tests

Each module keeps its own checks behind `--test` — no test framework.

```bash
for m in dq_battle field sounds sprites tileset interior tiled_map; do
    .venv/bin/python $m.py --test
done
```

## Layout

| Module | What it is |
|---|---|
| `main.py` | entry point; quitting is the save point |
| `app.py` | state stack, window chrome, `MessageLog` |
| `field.py` | overworld and town walking, encounters, world exits |
| `dq_battle.py` | DQ1 damage/escape/crit math, turn engine, `BattleState` |
| `worldmap.py`, `menu.py`, `title.py` | map screen, command windows, title screen |
| `village.py`, `castle.py`, `interior.py`, `npc.py` | towns, interiors, dialogue |
| `sprites.py`, `tileset.py`, `tiled_map.py` | art loaders (CraftPix packs, Tiled maps) |
| `pixelart.py` | snaps every pack to one pixel grid and palette |
| `sounds.py` | synthesised square/noise effects, mp3 music |
| `save.py` | the Adventure Log, JSON |

Maps are plain ASCII text grids (`data/alefgard.txt`, one char per tile).
`field.py --test` BFSes them and fails if a town is unreachable.

## Assets

`data/` is optional. Tiles, monsters and UI draw procedurally and sound is
synthesised, so the game runs with the art packs absent — every loader returns
nothing when files are missing and the caller falls back.

The packs are drawn in different styles — PUNY_WORLD is true 16px pixel art,
CraftPix ships high-resolution vector renders — so every loader passes its art
through `pixelart.snap()`, which puts them all on one pixel grid and one
palette. `GRID` and `LEVELS` in `pixelart.py` are the two dials.

Art packs bundled here: CraftPix desert tileset and Seer chibi sprites, Pipoya
RPG monster pack, Mana Seed starter pack, PUNY_WORLD Tiled maps. Their vector
sources (`.eps`, `.ai`) are included for editing but unused at runtime — the
desert tileset's 150 MB `.eps` ships zipped, since GitHub caps files at 100 MB.

## Build status

Battle and field are done. Field menu, towns, inventory, dungeons, quest flags,
save, and the Charlock endgame are in progress — see
`.claude/skills/dragon-quest/SKILL.md` for the build order and
`references/dq1-data.md` for the DQ1 data tables.
