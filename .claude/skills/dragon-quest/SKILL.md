---
name: dragon-quest
description: Build the Dragon Quest I (NES, 1986) JRPG in this repo with pygame — overworld Alefgard, towns/shops/inns, NPC dialogue, dungeons and torches, inventory and equipment, quest items, the Adventure Log save, and the Charlock/Dragonlord endgame, on top of the existing turn-based battle system. Use whenever work touches this game: adding a map, town, shop, monster, spell, item, menu, save file, or extending dq_battle.py.
---

# Dragon Quest (NES) in pygame

Faithful remake of the 1986 original. One hero, one enemy at a time, first-person
battles, top-down overworld, no combos and no ATB — the appeal is pacing and
tone, not mechanics depth. Keep it that way.

## Run it

```bash
cd /Users/luchunyi/Documents/Personal_GitHub/dragon_quest_game
.venv/bin/python main.py               # play
.venv/bin/python dq_battle.py          # arena mode: nothing but battles
.venv/bin/python sounds.py             # play every effect once
.venv/bin/python dq_battle.py --test   # self-checks, no window
.venv/bin/python field.py --test
.venv/bin/python sounds.py --test
.venv/bin/python sprites.py --test
.venv/bin/python tileset.py --test
.venv/bin/python interior.py --test
.venv/bin/python tiled_map.py --test
```

Adding a world is one entry in `field._worlds()` plus an exit tile on each side.
Four more PUNY_WORLD sample maps sit unused in `data/map/PUNY_WORLD_v1/Tiled/` —
`tiled_map.load("samplemap3.tmj")` is the whole cost of a fifth region.

`pygame` itself will not build on this machine's Python 3.14 (no SDL headers).
The venv has **pygame-ce**, same `import pygame` API. Do not "fix" this by
switching packages.

## What already exists

| Piece | Where | Notes |
|---|---|---|
| State stack | `app.py::App` | every state draws, only the top updates and takes keys; a state pops itself with `done = True` |
| Chrome | `app.py` — `window()`, `draw_status()`, `draw_log()`, `MessageLog` | 640×480, black fill + 3px white border; log wraps, scrolls, `skip()` on keypress |
| DQ1 damage/escape/crit math | `dq_battle.py` — `melee_damage`, `hero_attack_damage`, `can_escape`, `foe_ambush` | pure functions, no pygame |
| Actors | `Hero` (stats are `@property` off `LEVELS`), `Monster` dataclass + `MONSTERS` | `replace(proto)` makes a fresh combatant |
| Turn engine | `dq_battle.py::Battle` — every turn is a **generator yielding log lines** | the state pumps `next(script)` when the log goes idle; no state enum |
| Encounters | `dq_battle.py::BattleState(app, hero, foe, on_end=…)` | pops itself, reports `'win'/'lose'/'fled'/'gone'` |
| Worlds | `field.py::World` — grid, walkable, two paint passes, music, encounters, exits | one `FieldState` walks them all; `travel()` steps through a door and `locked` stops the arrival tile bouncing you back. Maps smaller than the screen centre instead of scrolling |
| Overworld | `data/alefgard.txt` | 64×64 ASCII grid, tween-a-step movement, `PLACES` is the trigger table |
| Danger by geography | `field.py` — `zone_pool()` over `_walk_field()` | monsters are picked by **how far you must walk** from Tantegel, not by ruler distance, so mountains, water and bridges gate progression by themselves. Unreachable-on-foot means top band, which is what makes Charlock the deadliest place in the world. `BAND` is the steps-per-tier dial. A ruler put Charlock — 15 tiles away across the strait — in the bat band, softer than Garinham |
| The hero's house | `data/home.txt` + `interior.py` | where the game starts; door at `(4,6)` ↔ the `H` tile at `HOME_DOOR` on the overworld |
| The green land | `tiled_map.py` + PUNY_WORLD's `samplemap1.tmj` | a 50×50 Tiled map behind the Rocky Mountain Cave. Composited once into a backdrop the field blits a viewport from; collision is **derived from the art**, so re-tune `_is_water`/`_is_bridge`/the 0.55 opacity cut if a new map looks wrong |
| Biome | this Alefgard is a **desert** | sand inland, a green oasis fringe only where water reaches (coast and river), palm groves at the oases, `^` rocky ground in blobs. Scattered single `^` tiles read as a checkerboard once tinted — keep them clumped |
| Sound | `sounds.py` — `voices()` builds the bank, `play(name)` never raises | square + LFSR-noise waves at 44100 stereo; a turn names its effect via `Battle.fx(sound, line)` and the UI plays it as the line lands |
| Music | `sounds.py::music(track)`, `TRACKS` → mp3s in `data/` | a state asks for its track every frame and the call no-ops unless it changes, so pushing a battle swaps the music and popping restores it |
| Sprites | `sprites.py::draw(surf, actor, anim, height, t, cx, feet_y)` | `ACTORS` covers the hero and nine monsters across two pack layouts (chibi frame folders, slime spritesheets). Sized and centred on each sequence's opening stance so poses don't jump; `POSE` in `dq_battle.py` maps a turn's effect to slash/cast/hurt/die |
| Monster art | `Monster.art` = an `ACTORS` key, or `""` for procedural | loaded lazily — `BattleState.start` calls `sprites.ensure()` so nine species of 900×900 frames aren't read at boot. Height scales off tier |
| Map art | `tileset.py` — `GROUND` fills a tile, `DECOR` stands an object on it | CraftPix desert pack; the object is hashed from tile coords so it scatters without shimmering. `DECOR[char] = (names, height, density)` is the whole dial |
| One art style | `pixelart.py::snap()` | the packs disagree — PUNY_WORLD is true 16px pixel art, CraftPix is smoothscaled vector renders. `snap()` puts everything on PUNY_WORLD's grid: one art pixel per `GRID` screen px, `LEVELS` steps per channel, alpha thresholded at `CUT`. Called at the end of `sprites.ensure` and `tileset.load`; **`tiled_map.py` is deliberately exempt** — it is already the target style, and its collision is derived from tile colour, so posterising it would move the water. Any new pack goes through `snap()` |
| Checks | `selftest()` under `--test` in both modules | extend them, don't start a test framework |

The map is a plain text grid — one char per tile, `TILES` in `field.py` says what
each char means. Edit it in any editor; `field.py --test` BFSes it and fails if a
town is marooned or if Charlock stops being an island.

## Rules for every addition

1. **Assets are optional, never required.** The game must run with `data/` and
   `audio/` empty: tiles, monsters and UI are drawn procedurally (`draw_monster`,
   `draw_tile`), maps are ASCII `.txt`, sound is synthesised. An art or audio pack
   goes in through a loader that returns nothing when the files are absent, and the
   caller falls back — `sprites.draw()` returning False, `sounds.play()` no-opping,
   `music()` leaving silence when the mp3 is missing. Follow that shape for any new
   pack; never make a `data/` folder load-bearing.
2. **Logic pure, pygame at the edge.** Formulas and state transitions must be
   importable and testable with `SDL_VIDEODRIVER=dummy` and no display.
3. **Generators for anything that talks.** Dialogue, shop haggling, cutscenes and
   turns are all `yield`-a-line generators pumped by the log. Reuse `MessageLog`.
4. **One module per system**, flat in the repo root: `field.py`, `town.py`,
   `dungeon.py`, `save.py`, `data.py`. Import `dq_battle` for combat, don't fork it.
5. **Every system leaves one runnable check** in its own `--test`, asserting the
   thing that would silently rot (a map with no reachable exit, a shop that lets
   you buy at negative gold).
6. **DQ1 voice.** "Thou hast done well in defeating the Slime." "But nothing
   happened." "Thy Hit Points have been reduced by 12." Second-person archaic,
   full sentences, no exclamation spam.
7. Keyboard only: arrows, `Z`/Enter confirm, `X`/Esc cancel. 640×480, dt-based.

## Headless verification (use this before claiming anything works)

```python
import os; os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame, dq_battle as dq
g = dq.Game()
for _ in range(300):
    g.log.update(1/60); g.pump(); g.draw()
    g.on_key(pygame.K_z)               # drive the menus
pygame.image.save(g.screen, "/tmp/shot.png")   # then Read the png
```
Screenshot it and **look at the image**. A soak loop that plays thousands of
random battles/steps catches the crashes; the screenshot catches the layout.

## Build order

Each phase must be playable on its own before the next starts.

- [x] **0. Battle** — `dq_battle.py`.
- [x] **1. Field** — `field.py`, `data/alefgard.txt`, `app.py`'s stack under both.
- [ ] **2. Field menu** — the DQ1 command window: TALK, STATUS, STAIRS, SEARCH,
      SPELL, ITEM, DOOR, TAKE. Extract the battle's menu drawing into `app.py` when
      you do — that's the second caller, so now it earns being shared.
- [ ] **3. Towns** — the `World` plumbing and the first interior (the hero's house)
      are done; add each town as another entry in `field._worlds()` with an `H`-style
      tile on the overworld. Then NPCs with fixed dialogue, inn (pay per head,
      restores HP/MP), weapon/armour shop, item shop, key shop. Selling is half price.
- [ ] **4. Inventory & equipment** — 10-slot bag, one weapon/armour/shield equipped.
      Then flip `Hero.attack` to `strength + weapon` and `Hero.defense` to
      `agility//2 + armour + shield` (the `ponytail:` comments in `dq_battle.py`
      mark the two lines).
- [ ] **5. Dungeons** — multi-floor caves, stairs, chests, locked doors consuming a
      Magic Key, and darkness: only a radius of tiles is drawn, widened by a Torch
      or RADIANT.
- [ ] **6. Quest** — flags for the tablet, Gwaelin's rescue, the three relics, the
      Rainbow Drop bridge. See `references/dq1-data.md`.
- [ ] **7. Adventure Log** — save/load to JSON at Tantegel; death warps to the King,
      restores HP/MP, halves gold.
- [ ] **8. Charlock & endings** — barrier damage tiles, Dragonlord's two forms, the
      "join me" choice (accepting really does end the game), Ball of Light ending.

## Faithfulness that matters

- Encounters are always **1 v 1**, always random, no escape from the Dragonlord.
- One deliberate break from the original: DQ1's battles are first-person with no
  hero on screen. This one shows the hero stage left, DQ3-style, because the sprite
  pack has the animations for it. Keep the monster stage right.
- Monster difficulty is a function of **walking** distance from Tantegel, so terrain
  gates progression on its own. Don't level-gate with invisible walls — the world is
  open, it just kills you.
- Bridges are *supposed* to mark the difficulty jumps and currently do not: deleting
  all three of Alefgard's `=` tiles costs 3 walkable tiles and splits nothing, because
  there are no rivers for them to span. 99.4% of the walkable map is one open blob, so
  five landmarks (Garinham, Kol, Rimuldar, Hauksness, the Grave) all sit 36–39 steps
  out and draw the identical monster band. Cutting rivers into `alefgard.txt` and
  putting the bridges on them is what spreads that cluster apart — the gating machinery
  is already in place and waiting for the geography.
- The hero's name seeds their stat growth in the original. Optional, but if added,
  keep it a pure function of the name string.
- `XP_MULT = 20` in `dq_battle.py` is demo pacing. Set it to 1 for the real game.
- Numbers live in `references/dq1-data.md` (spells, prices, monsters, world layout).
  Load that file when touching data; don't inline tables into code comments.
