#!/usr/bin/env python3
"""The overworld: Alefgard as an ASCII grid, tile-by-tile walking, random encounters.

The map is `data/alefgard.txt` — plain text, editable in any editor, one character
per tile. Landmark tiles double as the trigger table, keyed by tile coordinate the
way steelx/py-rpg-01 keys its triggers; movement is the same tween-a-step-then-fire-
on-arrival loop, and interaction reads the faced tile.

    play:  .venv/bin/python main.py
    check: .venv/bin/python field.py --test
"""
import random
import sys
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path

import pygame

import castle
import interior
import menu
import npc
import sounds
import sprites
import tiled_map
import tileset
import village
import worldmap
from app import BLACK, SIZE, WHITE, window
from dq_battle import MONSTERS, BattleState, Hero, revive, rnd

TILE = 32
COLS, ROWS = SIZE[0] // TILE, SIZE[1] // TILE     # 20 x 15 tiles on screen
MINIMAP = pygame.Rect(SIZE[0] - 152, 16, 136, 136)   # top right: 2px a tile, 64x64 map
MAPWIN = pygame.Rect(16, 44, 344, 344)               # M: the whole map, 5px a tile
LEGEND = pygame.Rect(368, 44, 256, 366)              # ...and its named landmarks
FOUND, UNFOUND = (250, 210, 60), (200, 80, 66)       # gold once seen, red while not
KEY = ("gold: found    red: not yet", "white: thou art here")
DESTS = {"castle": "Tantegel Castle", "village": "the village", "home": "thy own house",
         "alefgard": "Alefgard"}                      # where G may carry thee
STEP = 0.16                                       # seconds to walk one tile
STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIRS = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
        pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}


@dataclass(frozen=True)
class Tile:
    name: str
    passable: bool
    encounter: int          # chance in 256, per step
    color: tuple
    damage: int = 0


# Alefgard is a desert: sand inland, green only where water reaches, palm groves
# at the oases. `.` is the fringe, not the norm, so it keeps the lowest danger.
TILES = {
    "~": Tile("sea", False, 0, (30, 60, 170)),
    ".": Tile("oasis", True, 8, (66, 152, 74)),
    "*": Tile("grove", True, 16, (44, 112, 58)),
    "^": Tile("rocky ground", True, 14, (178, 152, 104)),
    "A": Tile("mountain", False, 0, (146, 118, 90)),
    "%": Tile("swamp", True, 12, (94, 84, 112), damage=2),
    ":": Tile("desert", True, 9, (204, 184, 112)),
    "=": Tile("bridge", True, 0, (204, 184, 112)),
    "C": Tile("castle", True, 0, (204, 184, 112)),
    "T": Tile("town", True, 0, (204, 184, 112)),
    "O": Tile("cave", True, 0, (146, 118, 90)),
    "S": Tile("shrine", True, 0, (204, 184, 112)),
    "X": Tile("Charlock", True, 0, (204, 184, 112)),
    "H": Tile("home", True, 0, (204, 184, 112)),
}

# The world map, from the RPG Maker export. Same idea: its legend is whatever
# worldmap.py's classifier emits, so the two stay in step.
WORLD_TILES = {
    worldmap.SEA: Tile("sea", False, 0, (30, 90, 150)),
    worldmap.VOID: Tile("the edge of the world", False, 0, (0, 0, 0)),
    worldmap.SAND: Tile("sand", True, 8, (222, 198, 152)),
    worldmap.GRASS: Tile("grassland", True, 6, (150, 180, 110)),
    worldmap.FOREST: Tile("forest", True, 14, (78, 132, 72)),
    worldmap.PEAK: Tile("mountain", False, 0, (120, 116, 108)),
    worldmap.SNOW: Tile("snowfield", True, 10, (226, 228, 232)),
    worldmap.BLIGHT: Tile("the blighted waste", True, 18, (120, 84, 140)),
}

# The green land beyond the mountains, from the PUNY_WORLD Tiled map. Its legend is
# whatever tiled_map.py's classifier emits, so it stays in step with that module.
GREEN_TILES = {
    tiled_map.GRASS: Tile("meadow", True, 8, (120, 170, 80)),
    tiled_map.ROAD: Tile("road", True, 4, (196, 178, 110)),
    tiled_map.FOREST: Tile("wood", True, 16, (60, 110, 60)),
    tiled_map.BLOCK: Tile("cliff", False, 0, (70, 70, 70)),
    tiled_map.WATER: Tile("river", False, 0, (30, 140, 190)),
}

TANTEGEL = (20, 34)
START = (21, 34)                                  # outside the castle gate
HOME_DOOR = (21, 35)                              # the hero's village, next door
HOME_SPAWN = (5, 5)                               # inside his house, by the hearth
VILLAGE_GATE = (12, 19)                           # the road out, to Alefgard
VILLAGE_ENTRY = (12, 18)                          # ...and where it lets you in
VILLAGE_DOOR = (6, 14)                            # the hero's front door
VILLAGE_STREET = (6, 15)                          # the street outside it
ROCKY_CAVE = (50, 12)                             # the tunnel through the mountains
GREEN_SPAWN = (30, 25)                            # ...and where it lets out
GREEN_ROAD = (5, 7)                               # the crossroads by the standing stone
WORLD_GATE = (27, 23)                             # the world map: the road out of town
WORLD_STONE = (22, 8)                             # ...and the stone on the north shore
CASTLE_DOOR = (10, 14)                            # Tantegel's throne room: the door,
CASTLE_SPAWN = (10, 13)                           # and the carpet just inside it

# The trigger table: what sits on which tile. Phase 3 turns these into interiors.
PLACES = {
    (20, 34): "Tantegel Castle", (24, 36): "Brecconary", (22, 42): "Erdrick's Cave",
    (9, 9): "Garinham", (9, 6): "the Grave of Garinham", (30, 8): "Kol",
    (50, 12): "the Rocky Mountain Cave", (39, 20): "the Swamp Cave",
    (39, 26): "the Swamp Cave", (53, 30): "Rimuldar", (57, 22): "the Rainbow Shrine",
    (12, 52): "the Rain Shrine", (10, 57): "Cantlin", (34, 57): "Hauksness",
    (35, 46): "Charlock Castle",
}

WILD = [m for m in MONSTERS if m.name != "Dragonlord"]   # he waits in Charlock


# ------------------------------------------------------------------ map

def load_map(name="alefgard.txt", legend=None):
    path = Path(__file__).parent / "data" / name
    grid = path.read_text().rstrip("\n").split("\n")
    assert len({len(row) for row in grid}) == 1, f"{name}: rows are ragged"
    unknown = set("".join(grid)) - set(legend or TILES)
    assert not unknown, f"{name}: unknown tiles {unknown}"
    return grid


@dataclass
class World:
    """A map and how it behaves: what blocks, what it looks like, what lurks."""
    name: str
    grid: list
    walkable: callable                            # char -> bool
    ground: callable                              # (surf, ch, px, py, tx, ty)
    obj: callable
    music: str
    encounters: bool
    exits: dict                                   # (x, y) -> (world name, (x, y))
    tiles: dict = None                            # char -> Tile, for damage/danger
    pool: callable = None                         # (x, y) -> monsters that roam here
    places: dict = None                           # (x, y) -> what is announced
    backdrop: object = None                       # pre-rendered map, if it has one
    npcs: dict = None                             # (x, y) -> someone standing there


def _over_ground(surf, ch, px, py, tx, ty):
    if not tileset.ground(surf, ch, px, py, tx, ty):
        pygame.draw.rect(surf, TILES[ch].color, (px, py, TILE, TILE))


def _mark(backdrop, pos, cave=True):
    """Paint a way out onto the Tiled backdrop, which carries no markers of its own:
    a cave mouth into the rock, or a timber gate where a road leaves the map."""
    x, y = pos[0] * TILE, pos[1] * TILE
    if cave:
        pygame.draw.rect(backdrop, (86, 74, 66), (x + 3, y + 6, TILE - 6, TILE - 6))
        pygame.draw.ellipse(backdrop, BLACK, (x + 9, y + 12, 14, 20))
        return
    for post in (x + 4, x + TILE - 9):
        pygame.draw.rect(backdrop, (110, 78, 48), (post, y + 6, 5, TILE - 6))
    pygame.draw.rect(backdrop, (110, 78, 48), (x + 2, y + 3, TILE - 4, 5))


def _worlds():
    vgrid = load_map("village.txt", village.SPEC)
    gates = [(x, y) for y, row in enumerate(vgrid)          # the road south, however
             for x, ch in enumerate(row) if ch == "G"]       # wide village.txt draws it
    built = {
        "alefgard": World("alefgard", load_map(), lambda ch: TILES[ch].passable,
                          _over_ground, draw_feature, "field", True,
                          {HOME_DOOR: ("village", VILLAGE_ENTRY),
                           TANTEGEL: ("castle", CASTLE_SPAWN)},
                          tiles=TILES, pool=zone_pool, places=PLACES),
        # Tantegel's throne room, where the King tells thee where the Dragonlord is
        "castle": World("castle", load_map("castle.txt", castle.SPEC), castle.walkable,
                        castle.ground, castle.obj, "field", False,
                        {CASTLE_DOOR: ("alefgard", START)}, npcs=npc.COURT),
        "home": World("home", load_map("home.txt", interior.SPEC), interior.walkable,
                      interior.ground, interior.obj, "field", False,
                      {(4, 6): ("village", VILLAGE_STREET)}),
        # the village his house stands in: no monsters, and two ways out -- his own
        # front door, and the road south. Without the Tiled pack that road falls back
        # to the desert, so the village is never a dead end
        "village": World("village", vgrid, village.walkable, village.ground,
                         village.obj, "field", False,
                         {**{gate: ("alefgard", HOME_DOOR) for gate in gates},
                          VILLAGE_DOOR: ("home", HOME_SPAWN)},
                         npcs=npc.VILLAGERS),
    }
    grid, backdrop = tiled_map.load()
    if grid:                                      # the pack is optional like the rest
        _mark(backdrop, GREEN_SPAWN)                          # the cave to Alefgard
        _mark(backdrop, GREEN_ROAD, cave=False)               # the gate onward
        built["greenland"] = World(
            "greenland", grid, lambda ch: GREEN_TILES[ch].passable, None, None,
            "field", True, {GREEN_SPAWN: ("alefgard", ROCKY_CAVE),
                            GREEN_ROAD: ("village", VILLAGE_ENTRY)},
            tiles=GREEN_TILES, backdrop=backdrop,
            # as dangerous as the cave mouth it is reached through
            pool=lambda x, y: zone_pool(*ROCKY_CAVE))
        built["alefgard"].exits[ROCKY_CAVE] = ("greenland", GREEN_SPAWN)
        # the village road runs out into the wide world now, not into the desert
        built["village"].exits.update({gate: ("greenland", GREEN_ROAD) for gate in gates})

    wgrid, wbackdrop = worldmap.load()
    if wgrid:
        # no markers painted on this one: both its doorways already stand on a
        # landmark the export drew -- the town, and the stone on the north shore
        built["world"] = World(
            "world", wgrid, lambda ch: WORLD_TILES[ch].passable, None, None,
            "field", True, {WORLD_GATE: ("village", VILLAGE_ENTRY)},
            tiles=WORLD_TILES, backdrop=wbackdrop,
            # danger by distance from town, the way Alefgard measures it from Tantegel
            pool=lambda x, y: zone_pool(x, y, WORLD_GATE))
        # the village road opens onto the world map, and the green land moves one hop
        # out, behind the standing stone on its northern shore
        built["village"].exits.update({gate: ("world", WORLD_GATE) for gate in gates})
        if "greenland" in built:
            built["world"].exits[WORLD_STONE] = ("greenland", GREEN_ROAD)
            built["greenland"].exits[GREEN_ROAD] = ("world", WORLD_STONE)
    return built


WORLDS = {}


def world(name):
    if not WORLDS:
        WORLDS.update(_worlds())
    return WORLDS[name]


def passable(grid, x, y, walkable=None, npcs=None):
    if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
        return False
    if npcs and (x, y) in npcs:
        return False                              # someone is standing there
    return (walkable or (lambda ch: TILES[ch].passable))(grid[y][x])


def reachable(grid, start, walkable=None, npcs=None):
    """Every tile walkable from `start`, each mapped to the tile it was reached from —
    the check that catches a marooned town, and the paths autopilot walks back down."""
    seen, queue = {start: None}, deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in STEPS:
            step = (x + dx, y + dy)
            if step not in seen and passable(grid, *step, walkable, npcs):
                seen[step] = (x, y)
                queue.append(step)
    return seen


def steps_to(grid, start, goal, walkable=None, npcs=None):
    """The shortest walk from `start` to `goal` as a list of steps, [] if there is none."""
    seen = reachable(grid, start, walkable, npcs)
    walk, here = [], goal
    while here != start:
        if here not in seen:
            return []
        back = seen[here]
        walk.append((here[0] - back[0], here[1] - back[1]))
        here = back
    return walk[::-1]


def doorway(here, goal):
    """Which tile in world `here` to head for to get one world nearer `goal`: the worlds
    are a graph joined by their exits, so this is the same walk one level up."""
    seen, queue = {here: None}, deque([here])
    while queue:
        name = queue.popleft()
        for spot, (dest, _) in world(name).exits.items():
            if dest not in seen:
                seen[dest] = (name, spot)
                queue.append(dest)
    if goal not in seen or goal == here:
        return None
    name, spot = seen[goal]
    while name != here:                           # back down to the first door of many
        name, spot = seen[name]
    return spot


def zone_pool(x, y, home=TANTEGEL):
    """DQ1 scales by geography, not by level: the further from home, the worse."""
    dist = max(abs(x - home[0]), abs(y - home[1]))
    band = min(len(WILD), 1 + dist // 3)     # //3 so the band reaches the last
    return WILD[max(0, band - 4):band]       # monster within the map's 40-odd tiles


# ------------------------------------------------------------------ drawing

def draw_feature(surf, ch, px, py, tx=0, ty=0):
    """Pass two on the overworld: what stands on the tile, over the ground fill."""
    if tileset.decor(surf, ch, px, py, tx, ty):
        return                                    # the pack dressed this one
    if ch == "~":
        for x, y in ((5, 9), (18, 20)):
            pygame.draw.line(surf, (95, 140, 235), (px + x, py + y), (px + x + 9, py + y), 2)
    elif ch == "*":
        for x, y in ((7, 7), (20, 5), (13, 19)):
            pygame.draw.polygon(surf, (18, 66, 34), [(px + x, py + y),
                                                     (px + x - 6, py + y + 10),
                                                     (px + x + 6, py + y + 10)])
    elif ch == "^":
        for x, y in ((4, 22), (17, 24)):
            pygame.draw.arc(surf, (96, 96, 40), (px + x, py + y - 12, 14, 20), 0.2, 2.9, 4)
    elif ch == "A":
        for x, y in ((2, 28), (14, 30)):
            pygame.draw.polygon(surf, (150, 132, 120), [(px + x + 8, py + y - 22),
                                                        (px + x, py + y),
                                                        (px + x + 16, py + y)])
    elif ch == "%":
        for x, y in ((6, 8), (19, 14), (11, 23)):
            pygame.draw.ellipse(surf, (66, 58, 82), (px + x, py + y, 8, 5))
    elif ch == ":":
        for x, y in ((6, 10), (18, 18), (24, 7)):
            pygame.draw.line(surf, (176, 156, 88), (px + x, py + y), (px + x + 5, py + y), 2)
    elif ch == "=":
        pygame.draw.rect(surf, (30, 60, 170), (px, py, TILE, TILE))
        pygame.draw.rect(surf, (146, 100, 52), (px, py + 6, TILE, 20))
        for x in range(2, TILE, 7):
            pygame.draw.line(surf, (92, 60, 30), (px + x, py + 6), (px + x, py + 25), 2)
    elif ch in "CX":                                  # castle: keep, battlements, flag
        body = (170, 170, 180) if ch == "C" else (120, 60, 140)
        pygame.draw.rect(surf, body, (px + 4, py + 10, 24, 20))
        for x in (4, 12, 20):
            pygame.draw.rect(surf, body, (px + x, py + 4, 5, 8))
        pygame.draw.line(surf, (210, 60, 60), (px + 16, py + 2), (px + 24, py + 5), 2)
        pygame.draw.rect(surf, BLACK, (px + 13, py + 20, 6, 10))
    elif ch == "T":                                   # town: walls and a red roof
        pygame.draw.rect(surf, (186, 146, 96), (px + 4, py + 14, 24, 16))
        pygame.draw.polygon(surf, (188, 70, 60), [(px + 2, py + 14), (px + 16, py + 4),
                                                  (px + 30, py + 14)])
        pygame.draw.rect(surf, BLACK, (px + 13, py + 21, 6, 9))
    elif ch == "O":                                   # cave mouth
        pygame.draw.rect(surf, (86, 74, 66), (px + 2, py + 8, 28, 22))
        pygame.draw.ellipse(surf, BLACK, (px + 9, py + 13, 14, 17))
    elif ch == "S":                                   # shrine: two pillars
        pygame.draw.rect(surf, (214, 214, 224), (px + 5, py + 12, 5, 18))
        pygame.draw.rect(surf, (214, 214, 224), (px + 22, py + 12, 5, 18))
        pygame.draw.rect(surf, (214, 214, 224), (px + 2, py + 6, 28, 6))


_MINI = {}                                        # (world, side) -> its scaled-up map


def minimap(w, side=MINIMAP.w - 8):
    """One pixel per tile, blown up to fill `side`. Cached: the map never changes."""
    if (w.name, side) not in _MINI:
        cols, rows = len(w.grid[0]), len(w.grid)
        small = pygame.Surface((cols, rows))
        for y, row in enumerate(w.grid):
            for x, ch in enumerate(row):
                small.set_at((x, y), w.tiles[ch].color)
        zoom = max(1, min(side // cols, side // rows))
        _MINI[w.name, side] = pygame.transform.scale(small, (cols * zoom, rows * zoom))
    return _MINI[w.name, side]


def draw_hero(surf, px, py, facing):
    pygame.draw.polygon(surf, (70, 90, 200), [(px + 16, py + 12), (px + 7, py + 29),
                                              (px + 25, py + 29)])
    pygame.draw.circle(surf, (232, 196, 150), (px + 16, py + 10), 7)
    pygame.draw.circle(surf, (200, 180, 60), (px + 16, py + 6), 7, 2)      # helm
    eye = (px + 16 + facing[0] * 4, py + 11 + max(0, facing[1]) * 2)
    if facing[1] >= 0:
        pygame.draw.circle(surf, BLACK, eye, 2)
    pygame.draw.circle(surf, (190, 60, 60), (px + 25 - facing[0] * 3, py + 22), 4)  # shield


# ------------------------------------------------------------------ state

class FieldState:
    """Walk Alefgard. Pushes a BattleState when something draws near."""

    def __init__(self, app, hero, place="alefgard", start=START):
        self.app, self.hero = app, hero
        self.dx = self.dy = 0
        self.t = 0.0                                  # progress into the current step
        self.facing = (0, 1)
        self.flip = False                             # sprite faces left
        self.anim_t = 0.0
        self.msg_timer = 0.0
        self.queued = None                            # a direction tapped mid-step
        self.going = None                             # autopilot: the world it heads for
        self.route = []                               # ...and the steps left in this one
        self.done = False
        self.travel(place, start, quietly=True)

    def travel(self, place, pos, quietly=False):
        """Step through a door. `locked` stops the arrival tile bouncing us back."""
        self.hero.flags[f"seen:{place}"] = True    # the villagers ask where thou hast been
        self.world = world(place)
        self.grid = self.world.grid
        self.x, self.y = self.locked = pos
        self.dx = self.dy = 0
        self.t = 0.0
        self.route = []
        if self.going == place:                    # autopilot: arrived, hand back the reins
            self.going = None
        elif self.going:                           # ...or through this door and on to the next
            self.autopilot(self.going, quiet=True)
        if not quietly:
            sounds.play("place")

    # -- flow ----------------------------------------------------------
    def say(self, text, hold=2.6):
        self.app.log.clear()
        self.app.log.push(text)
        self.msg_timer = hold

    def autopilot(self, goal="castle", quiet=False):
        """Walk to another world on thy own feet: G, and the map does the rest. Only the
        leg through this world is planned; each door recomputes the next one."""
        self.going, self.route = None, []
        if self.world.name == goal:
            return self.say("Thou art there already.")
        door = doorway(self.world.name, goal)
        if not door:
            return self.say("Thou knowest no way there from here.")
        self.route = steps_to(self.grid, (self.x, self.y), door,
                              self.world.walkable, self.world.npcs)
        if not self.route:
            return self.say("Thy way there is blocked.")
        self.going = goal
        if not quiet:
            self.say(f"Thy feet know the way to {DESTS.get(goal, goal)}. "
                     "Press any key to stop.", hold=3.0)

    def update(self, dt):
        sounds.music(self.world.music)                # no-op once it is already playing
        self.anim_t += dt                             # idle breathing runs regardless
        if not self.app.log.idle:
            return                                    # stand still while text types
        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0:
                self.app.log.clear()
        if self.dx or self.dy:
            self.t += dt / STEP
            if self.t < 1.0:
                return
            self.x, self.y = self.x + self.dx, self.y + self.dy
            self.dx = self.dy = 0
            self.t -= 1.0                             # keep the overshoot: a step that
            self.arrive()                             # ends mid-frame is not rounded off
            if self.app.top is not self:              # a battle, or a door we walked in
                return
        keys = pygame.key.get_pressed()               # ...and the arrival frame may
        for key, step in DIRS.items():                # start the next step at once
            if keys[key]:
                return self.try_step(step)
        if self.queued:                               # nothing held, but something was
            step, self.queued = self.queued, None     # tapped while the step ran
            return self.try_step(step)
        if self.route:                                # autopilot walks the planned leg
            return self.try_step(self.route.pop(0))
        self.t = 0.0                                  # standing still: no head start

    def try_step(self, step):
        """Turn to face the step; take it only if the tile beyond allows."""
        self.facing = step
        if step[0]:
            self.flip = step[0] < 0
        if passable(self.grid, self.x + step[0], self.y + step[1],
                    self.world.walkable, self.world.npcs):
            self.dx, self.dy = step

    def arrive(self):
        here = (self.x, self.y)
        place = (self.world.places or {}).get(here)
        if place:
            # noted before the exits below, or walking straight into Tantegel would
            # mean never having found it as far as the quest log is concerned
            self.hero.flags[f"found:{place}"] = True
        if here != self.locked:
            self.locked = None
            if here in self.world.exits:
                return self.travel(*self.world.exits[here])
        if not self.world.encounters:
            return
        tile = self.world.tiles[self.grid[self.y][self.x]]
        if tile.damage:
            self.hero.hp -= tile.damage
            sounds.play("hurt")
            self.say(f"The poisonous swamp reduces {self.hero.name}'s "
                     f"Hit Points by {tile.damage}.")
            if self.hero.hp <= 0:
                sounds.play("death")
                return self.die()
        if place:
            sounds.play("place")
            return self.say(f"Thou hast come to {place}.")
        if self.hero.flags.get("no-battles"):     # set from the menu, to go sightseeing
            return
        if tile.encounter and not self.near_home() and rnd(1, 256) <= tile.encounter:
            foe = replace(random.choice(self.world.pool(self.x, self.y)))
            self.app.push(BattleState(self.app, self.hero, foe, on_end=self.after_battle))

    def near_home(self):
        """No monsters within sight of Tantegel's walls."""
        return (self.world.name == "alefgard"
                and max(abs(self.x - TANTEGEL[0]), abs(self.y - TANTEGEL[1])) <= 3)

    def after_battle(self, outcome):
        self.app.log.clear()
        self.msg_timer = 0.0
        if outcome == "lose":
            self.die()

    def die(self):
        revive(self.hero)
        self.travel("alefgard", START, quietly=True)
        self.say("The King restores thee to life at Tantegel, "
                 "but half thy gold is gone.", hold=4.0)

    def on_key(self, key):
        if not self.app.log.idle:
            self.app.log.skip()
            return
        if key == pygame.K_g:
            sounds.play("confirm")
            return self.autopilot("castle")
        if self.going:                            # any key at all takes the reins back
            self.going, self.route = None, []
            sounds.play("cancel")
            self.say("Thou stoppest where thou art.", hold=1.4)
            if key not in DIRS:
                return
        if key in DIRS:
            self.queued = DIRS[key]               # remembered, so a tap is never lost
            return                                # mid-step; the poll takes it from here
        if key in (pygame.K_x, pygame.K_ESCAPE):
            sounds.play("confirm")
            self.app.log.clear()                  # the menu covers the log window
            self.msg_timer = 0.0
            return self.app.push(menu.MenuState(self.app, self))
        if key == pygame.K_m:
            if not self.world.tiles:              # indoors there is nothing to chart
                sounds.play("cancel")
                return self.say("No map is drawn of these walls.")
            sounds.play("confirm")
            self.app.log.clear()
            self.msg_timer = 0.0
            return self.app.push(MapState(self.app, self))
        if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
            faced = (self.x + self.facing[0], self.y + self.facing[1])
            person = (self.world.npcs or {}).get(faced)
            if person:
                sounds.play("confirm")
                met = f"met:{person.name}"
                line = person.talk({"hero": self.hero, "flags": self.hero.flags,
                                    "met": self.hero.flags.get(met, False)})
                self.hero.flags[met] = True
                return self.say(line, hold=5.0)
            place = PLACES.get((self.x, self.y)) or PLACES.get(faced)
            sounds.play("confirm" if place else "cancel")
            # ponytail: interiors are phase 3, so a landmark just names itself
            self.say(f"{place} bars its gates for now." if place
                     else "But there found nothing.")

    # -- render --------------------------------------------------------
    def draw(self):
        sc = self.app.screen
        cam_x = (self.x + self.dx * self.t) * TILE + TILE / 2 - SIZE[0] / 2
        cam_y = (self.y + self.dy * self.t) * TILE + TILE / 2 - SIZE[1] / 2
        span_x, span_y = len(self.grid[0]) * TILE, len(self.grid) * TILE
        if span_x <= SIZE[0]:                        # a room smaller than the screen
            cam_x = (span_x - SIZE[0]) / 2           # sits centred instead of scrolling
        if span_y <= SIZE[1]:
            cam_y = (span_y - SIZE[1]) / 2
        if self.world.backdrop is not None:
            cam_x = min(max(cam_x, 0), span_x - SIZE[0])      # stay on the painting
            cam_y = min(max(cam_y, 0), span_y - SIZE[1])
            sc.blit(self.world.backdrop, (0, 0), (cam_x, cam_y, *SIZE))
        else:
            left, top = int(cam_x // TILE), int(cam_y // TILE)
            outside = "~" if self.world.encounters else None  # black around a room
            # two passes: every floor, then every object, so tall objects may
            # overflow up and left without the next tile painting over them
            visible = [(tx, ty, tx * TILE - cam_x, ty * TILE - cam_y)
                       for row in range(-1, ROWS + 2) for col in range(-1, COLS + 2)
                       for tx, ty in [(left + col, top + row)]]
            for paint in (self.world.ground, self.world.obj):
                for tx, ty, px, py in visible:
                    in_map = 0 <= ty < len(self.grid) and 0 <= tx < len(self.grid[0])
                    ch = self.grid[ty][tx] if in_map else outside
                    if ch is not None:
                        paint(sc, ch, px, py, tx, ty)
        cx = (self.x + self.dx * self.t) * TILE + TILE / 2 - cam_x
        feet = (self.y + self.dy * self.t) * TILE + TILE - cam_y
        walking = bool(self.dx or self.dy)

        # the townsfolk, painted around the hero by row: whoever stands further down
        # the screen is nearer the eye, and so goes over whoever is behind them
        def crowd(rows):
            for (tx, ty), person in (self.world.npcs or {}).items():
                px, py = tx * TILE - cam_x, ty * TILE - cam_y
                if ty in rows and -TILE <= px <= SIZE[0] and -TILE <= py <= SIZE[1]:
                    npc.draw(sc, person, int(px + TILE / 2), int(py + TILE), self.anim_t)

        here = self.y + self.dy * self.t
        crowd(range(-1, int(here) + 1))
        if not sprites.draw(sc, "hero", "walk" if walking else "idle", sprites.FIELD_H,
                            self.anim_t, cx, feet, flip=self.flip):
            draw_hero(sc, cx - TILE // 2, feet - TILE, self.facing)
        crowd(range(int(here) + 1, len(self.grid)))
        # ponytail: status box hidden while walking around; it's still drawn in battle
        self.draw_minimap()
        if self.app.log.lines:
            self.app.draw_log()

    def draw_minimap(self):
        """Where thou art, and which landmarks are still unfound: gold once seen,
        dim before that, so the dim ones read as somewhere left to walk."""
        if not self.world.tiles:              # a room already fits on one screen
            return
        sc = self.app.screen
        mini = minimap(self.world)
        window(sc, MINIMAP)
        at = mini.get_rect(center=MINIMAP.center)
        sc.blit(mini, at)
        cell = mini.get_width() / len(self.grid[0])

        def dot(x, y, color, r):
            at_px = (at.x + int((x + 0.5) * cell), at.y + int((y + 0.5) * cell))
            pygame.draw.circle(sc, BLACK, at_px, r + 1)   # a ring, or sand hides it
            pygame.draw.circle(sc, color, at_px, r)

        for (x, y), place in (self.world.places or {}).items():
            dot(x, y, FOUND if self.hero.flags.get(f"found:{place}") else UNFOUND, 2)
        if self.anim_t % 0.8 < 0.5:           # blink, or the hero is lost in the dots
            dot(self.x, self.y, WHITE, 3)


class MapState:
    """The world map, opened with M over the field: the whole of it at once, every
    landmark numbered and named down the side. A state like the menu, so the world
    stands still while it is open, and M or X puts it away."""

    def __init__(self, app, field):
        self.app, self.field = app, field
        self.t = 0.0
        self.done = False
        self.small = pygame.font.SysFont("couriernew,menlo,dejavusansmono,monospace",
                                         13, bold=True)

    def update(self, dt):
        self.t += dt

    def on_key(self, key):
        if key in (pygame.K_m, pygame.K_x, pygame.K_ESCAPE, pygame.K_RETURN,
                   pygame.K_SPACE, pygame.K_z):
            sounds.play("cancel")
            self.done = True

    def draw(self):
        sc, w = self.app.screen, self.field.world
        sc.fill(BLACK)
        menu.centered(self.app, self.app.font, w.name.upper(), 14)
        mini = minimap(w, MAPWIN.w - 8)
        window(sc, MAPWIN)
        at = mini.get_rect(center=MAPWIN.center)
        sc.blit(mini, at)
        cell = mini.get_width() / len(w.grid[0])
        # one number per name: the Swamp Cave has two mouths and one line in the list
        names = list(dict.fromkeys((w.places or {}).values()))
        for (x, y), place in (w.places or {}).items():
            color = FOUND if self.field.hero.flags.get(f"found:{place}") else UNFOUND
            px, py = at.x + int((x + 0.5) * cell), at.y + int((y + 0.5) * cell)
            castle_here = "Castle" in place
            if castle_here:                        # a keep with battlements, not a dot:
                pygame.draw.rect(sc, BLACK, (px - 5, py - 6, 11, 12))   # the two castles
                pygame.draw.rect(sc, color, (px - 4, py - 2, 9, 7))     # are the whole
                for notch in (-4, -1, 2):                               # point of Alefgard
                    pygame.draw.rect(sc, color, (px + notch, py - 5, 2, 4))
            else:
                pygame.draw.circle(sc, BLACK, (px, py), 4)
                pygame.draw.circle(sc, color, (px, py), 3)
            # castles carry their name on the map itself; the rest go by number
            label = self.small.render(place if castle_here
                                      else str(names.index(place) + 1), True, WHITE)
            spot = label.get_rect(midleft=(px + 7, py))
            if spot.right > MAPWIN.right - 6:      # a name that would run off the map
                spot = label.get_rect(midright=(px - 7, py))            # sits to the left
            sc.blit(label, spot)
        if self.t % 0.8 < 0.5:                     # the hero, blinking, over the rest
            px, py = (at.x + int((self.field.x + 0.5) * cell),
                      at.y + int((self.field.y + 0.5) * cell))
            pygame.draw.circle(sc, BLACK, (px, py), 5)
            pygame.draw.circle(sc, WHITE, (px, py), 4)

        window(sc, LEGEND)
        for i, place in enumerate(names):
            found = self.field.hero.flags.get(f"found:{place}")
            line = self.small.render(f"{i + 1:>2}. {place}", True,
                                     FOUND if found else UNFOUND)
            sc.blit(line, (LEGEND.x + 12, LEGEND.y + 12 + i * 22))
        for i, hint in enumerate(KEY):
            sc.blit(self.small.render(hint, True, WHITE),
                    (LEGEND.x + 12, LEGEND.bottom - 44 + i * 18))
        menu.centered(self.app, self.app.font, "M or X: close the map", menu.HINT_Y)


# ------------------------------------------------------------------ self-check

def selftest():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from app import App

    random.seed(5)
    app = App()          # the window first: the packs need it to convert their art,
    hero = Hero()        # and without it every optional world quietly fails to build
    grid = load_map()
    assert len(grid) == 64 and len(grid[0]) == 64

    # every landmark stands on walkable ground, and is walkable to — except
    # Charlock, which must stay cut off until the Rainbow Drop bridges the strait
    mainland = reachable(grid, START)
    island = reachable(grid, (35, 47))
    for xy, name in PLACES.items():
        assert TILES[grid[xy[1]][xy[0]]].passable, f"{name} sits on blocked ground"
        if name == "Charlock Castle":
            assert xy not in mainland and xy in island, "Charlock is not an island"
        else:
            assert xy in mainland, f"{name} is cut off from Tantegel"
    straits = [(x, y) for y in range(64) for x in range(64) if grid[y][x] == "~"
               and any((x + a, y + b) in mainland for a, b in STEPS)
               and any((x + a, y + b) in island for a, b in STEPS)]
    assert straits, "no single water tile links the mainland to Charlock"

    # encounters get worse with distance and never spawn the Dragonlord
    assert [m.name for m in zone_pool(*START)] == ["Slime"]
    assert len(zone_pool(53, 30)) == 4
    assert all(m.name != "Dragonlord" for x in (0, 40, 63) for m in zone_pool(x, x))
    # ...and every wild monster has somewhere it can actually turn up
    roams = {m.name for x, y in mainland for m in zone_pool(x, y)}
    assert roams == {m.name for m in WILD}, f"never spawns: {set(m.name for m in WILD) - roams}"

    # the house: a closed room whose only way out is the door, and it leads home
    house = world("home")
    inside = reachable(house.grid, HOME_SPAWN, house.walkable)
    door, = house.exits
    assert door in inside, "the front door cannot be reached from the bed"
    assert len(inside) > 20, "the room is barely walkable"
    edge = {(x, y) for x, y in inside
            if x in (0, len(house.grid[0]) - 1) or y in (0, len(house.grid) - 1)}
    assert edge == {door}, f"the room leaks at {edge - {door}}"
    assert house.exits[door] == ("village", VILLAGE_STREET)
    assert grid[HOME_DOOR[1]][HOME_DOOR[0]] == "H", "no house stands on the overworld"

    # the village: walk out of the house and the whole of it is open to you, the
    # road out included, and both its doorways lead where they say
    town = world("village")
    assert not town.encounters, "monsters in the village"
    street = reachable(town.grid, VILLAGE_STREET, town.walkable, town.npcs)
    assert VILLAGE_GATE in street and VILLAGE_DOOR in street
    assert VILLAGE_ENTRY in street, "coming in from Alefgard drops you in a wall"
    assert len(street) > 200, f"only {len(street)} tiles of the village are walkable"
    assert town.grid[VILLAGE_DOOR[1]][VILLAGE_DOOR[0]] == "+", "the hero's door moved"
    assert town.exits[VILLAGE_DOOR] == ("home", HOME_SPAWN)

    # everyone with something to say -- villagers and the King's court alike -- stands
    # on open ground, blocks it while they do, stands out of every doorway, and can be
    # walked up to and faced. The ground is walked with them in it, so anyone standing
    # in the wrong place shows up here as a room that cannot be crossed
    for where, spawn in (("village", VILLAGE_STREET), ("castle", CASTLE_SPAWN)):
        room = world(where)
        floor = reachable(room.grid, spawn, room.walkable, room.npcs)
        assert len(floor) > 60, f"{where}: only {len(floor)} tiles can be walked"
        for spot, person in room.npcs.items():
            standing = room.grid[spot[1]][spot[0]]
            assert room.walkable(standing), f"{person.name} stands in a wall"
            assert spot not in room.exits, f"{person.name} is standing in a doorway"
            assert spot not in floor, f"{person.name} can be walked through"
            assert any(step in floor for step in
                       [(spot[0] + dx, spot[1] + dy) for dx, dy in STEPS]), \
                f"{person.name} cannot be reached to talk to"

    road = town.exits[VILLAGE_GATE]                        # wherever the packs put it
    assert all(town.exits.get((x, y)) == road              # the whole road leads there,
               for y, row in enumerate(town.grid)          # not just one lane of it
               for x, ch in enumerate(row) if ch == "G")
    # every house is a house: a roof over walls, and no roof left standing on grass
    for y, row in enumerate(town.grid):
        for x, ch in enumerate(row):
            if ch in "^&":
                assert town.grid[y + 1][x] in "#%w", f"roof floats at {(x, y)}"
            if ch in "#%":
                assert town.grid[y - 1][x] in "^&#%w", f"wall has no roof at {(x, y)}"

    # the castle: the King's own tile is Tantegel on the overworld, the throne stands
    # at the head of the carpet, and the door lets out where thou camest in
    hall = world("castle")
    assert not hall.encounters, "monsters in the throne room"
    assert world("alefgard").exits[TANTEGEL] == ("castle", CASTLE_SPAWN)
    assert hall.exits[CASTLE_DOOR] == ("alefgard", START)
    assert hall.grid[CASTLE_DOOR[1]][CASTLE_DOOR[0]] == "+", "the castle door moved"
    throne = [(x, y) for y, row in enumerate(hall.grid)
              for x, ch in enumerate(row) if ch == "T"]
    assert len(throne) == 1, f"{len(throne)} thrones in one hall"
    king = next((spot for spot, who in hall.npcs.items() if who.name == "The King"), None)
    assert king and abs(king[0] - throne[0][0]) <= 1 and king[1] == throne[0][1] + 1, \
        "the King is not standing at his own throne"
    assert PLACES[TANTEGEL] == "Tantegel Castle"           # ...and the log records it
    field_at_gate = FieldState(app, hero, "alefgard", START)
    field_at_gate.x, field_at_gate.y = TANTEGEL
    field_at_gate.locked = None
    field_at_gate.arrive()
    assert field_at_gate.world.name == "castle", "walking into Tantegel did not enter it"
    assert hero.flags["found:Tantegel Castle"], "entering Tantegel went unrecorded"

    # every doorway in the game -- however the optional packs wired it -- leads to a
    # world that was built, lands on ground you can stand on, and is itself standable
    for name in list(WORLDS):
        here = world(name)
        for spot, (dest, arrival) in here.exits.items():
            assert dest in WORLDS, f"{name}{spot} leads to {dest}, which is not built"
            assert passable(here.grid, *spot, here.walkable), f"{name}{spot} is blocked"
            there = world(dest)
            assert passable(there.grid, *arrival, there.walkable), \
                f"{name}{spot} lands in a wall at {dest}{arrival}"

    # ...and every world is reachable from the hero's own bed, door by door
    seen, queue = {"home"}, deque(["home"])
    while queue:
        for dest, _ in world(queue.popleft()).exits.values():
            if dest not in seen:
                seen.add(dest)
                queue.append(dest)
    assert seen == set(WORLDS), f"walled off from home: {set(WORLDS) - seen}"

    field = FieldState(app, hero)

    # a door moves you between worlds, and does not bounce you straight back
    field.travel("home", HOME_SPAWN)
    assert field.world.name == "home" and not field.world.encounters
    field.x, field.y = door
    field.arrive()                                    # arriving on the door: outside
    assert field.world.name == "village" and (field.x, field.y) == VILLAGE_STREET
    field.arrive()                                    # still standing on it: stay put
    assert field.world.name == "village", "the doorway bounced us back inside"
    field.locked = None                               # the front door again, inwards
    field.x, field.y = VILLAGE_DOOR
    field.arrive()
    assert field.world.name == "home" and (field.x, field.y) == HOME_SPAWN

    # ...and the road south of the village runs out into the world beyond, and back
    field.travel("village", VILLAGE_GATE)
    field.locked = None
    field.arrive()
    assert (field.world.name, (field.x, field.y)) == road, f"the road led {field.world.name}"
    field.arrive()                                    # standing on the gate: stay put
    assert field.world.name == road[0], "the road bounced us straight back"
    field.locked = None
    field.arrive()                                    # step onto it again: village
    assert field.world.name == "village" and (field.x, field.y) == VILLAGE_ENTRY

    # a villager blocks the tile he stands on, and answers when talked to
    spot, person = next(iter(town.npcs.items()))
    beside = next(s for s in [(spot[0] + dx, spot[1] + dy) for dx, dy in STEPS]
                  if s in street)
    field.travel("village", beside)
    field.try_step((spot[0] - beside[0], spot[1] - beside[1]))
    assert (field.dx, field.dy) == (0, 0), f"the hero walked through {person.name}"
    app.log.clear()
    field.on_key(pygame.K_z)
    spoken = "".join(line for line, _ in app.log.pending)
    assert person.name in spoken, f"{person.name} said nothing: {spoken!r}"
    app.log.clear()
    field.on_key(pygame.K_z)                          # and something else next time
    assert "".join(line for line, _ in app.log.pending) != spoken
    assert hero.flags[f"met:{person.name}"], "talking to someone was not remembered"
    assert hero.flags["seen:village"], "walking into the village was not remembered"
    person.said, person.told = 0, set()

    # the desert still reaches the village too, through the house tile by the castle
    field.travel("alefgard", START, quietly=True)
    field.x, field.y = HOME_DOOR
    field.arrive()
    assert field.world.name == "village", "stepping onto the village did not enter it"
    field.travel("alefgard", START, quietly=True)

    # the green land: reached through the mountain cave, and it leads back
    if "greenland" in WORLDS:
        green = world("greenland")
        assert green.backdrop is not None and green.pool and green.encounters
        assert set(green.grid[GREEN_SPAWN[1]][GREEN_SPAWN[0]]) <= set(GREEN_TILES)
        assert green.walkable(green.grid[GREEN_SPAWN[1]][GREEN_SPAWN[0]])
        assert world("alefgard").exits[ROCKY_CAVE] == ("greenland", GREEN_SPAWN)
        # its two ways out stand on open road, with walkable ground between them, so
        # the map is one land and not two islands
        assert GREEN_SPAWN in reachable(green.grid, GREEN_ROAD, green.walkable), \
            "the gate and the Alefgard cave are on separate ground"
        field.x, field.y = ROCKY_CAVE
        field.locked = None
        field.arrive()
        assert field.world.name == "greenland" and (field.x, field.y) == GREEN_SPAWN
        # its danger matches the cave it came through, and it is not the desert's
        assert {m.name for m in field.world.pool(0, 0)} == \
               {m.name for m in zone_pool(*ROCKY_CAVE)}
        field.locked = None
        field.arrive()
        assert field.world.name == "alefgard", "the green land had no way home"
        field.travel("alefgard", START, quietly=True)

    if "world" in WORLDS:
        earth = world("world")
        assert earth.backdrop is not None and earth.encounters
        assert set("".join(earth.grid)) <= set(WORLD_TILES)
        assert not earth.walkable(worldmap.SEA) and not earth.walkable(worldmap.PEAK)
        # the town and the standing stone are one walk apart, so the ring is a ring
        assert WORLD_STONE in reachable(earth.grid, WORLD_GATE, earth.walkable)
        # and danger is measured from the town, not from Tantegel's coordinates
        assert [m.name for m in earth.pool(*WORLD_GATE)] == ["Slime"]
        assert len(earth.pool(2, 2)) == 4, "the far shore is no worse than the town"

    # walking is worth what STEP promises: a held key covers 1/STEP tiles a second,
    # not a tile less for the frames an arrival used to throw away
    hero.flags["no-battles"] = True                    # measure walking, not fighting
    app.log.clear()                                    # ...and walking, not reading
    app.states[:] = [field]                            # update() checks it is on top
    field.travel("alefgard", (30, 25), quietly=True)
    field.queued = None
    held = type("Held", (dict,), {"__missing__": lambda self, k: False})()
    held[pygame.K_RIGHT] = True
    real_keys, pygame.key.get_pressed = pygame.key.get_pressed, lambda: held
    start = field.x
    for _ in range(60):                               # one second at 60fps
        field.update(1 / 60)
    walked, want = field.x - start, 1 / STEP
    assert walked >= want - 1, f"{walked} tiles a second, {want:.2f} promised"

    # ...and a tap while a step is running is taken up when it ends, not dropped
    pygame.key.get_pressed = real_keys                 # nothing held from here on
    field.dx = field.dy = 0
    field.t = 0.0
    field.travel("alefgard", (30, 25), quietly=True)
    field.try_step((1, 0))
    field.update(STEP / 2)                             # mid-step: the tap lands here
    field.on_key(pygame.K_DOWN)
    assert field.queued == (0, 1), "the tap was dropped"
    for _ in range(30):
        field.update(1 / 60)
    assert (field.x, field.y) == (31, 26), f"the tapped step never ran: {field.x, field.y}"
    assert field.queued is None, "the tap fired twice"
    hero.flags["no-battles"] = False
    app.states.clear()

    # a blocked tile turns the hero without moving them; open ground starts the step
    field.x, field.y = 14, 30                         # beside the western spur
    assert not passable(grid, 13, 30)
    field.try_step((-1, 0))
    assert (field.dx, field.dy) == (0, 0) and field.facing == (-1, 0)
    field.try_step((1, 0))
    assert (field.dx, field.dy) == (1, 0)
    field.dx = field.dy = 0

    # swamp bites, and the safe apron round Tantegel never rolls an encounter
    field.x, field.y = 38, 20
    field.arrive()
    assert hero.hp == hero.max_hp - 2
    field.x, field.y = START
    assert field.near_home()
    for _ in range(500):
        field.arrive()
    assert not app.states, "something attacked within sight of Tantegel"

    # ...but the wilds do attack, and hand back a battle over the right monster
    field.x, field.y = 30, 20
    for _ in range(4000):
        field.arrive()
        if app.states:
            break
    assert app.states, "no encounter ever fired in the open field"
    assert app.states[0].battle.foe.name in [m.name for m in zone_pool(30, 20)]
    app.states.clear()

    # landmarks announce themselves on arrival
    field.x, field.y = 24, 36
    field.arrive()
    assert "Brecconary" in "".join(line for line, _ in app.log.pending)

    # a step across the map keeps the hero on walkable ground the whole way
    field.x, field.y = START
    for _ in range(2000):
        field.dx, field.dy = random.choice(STEPS)
        if not passable(grid, field.x + field.dx, field.y + field.dy):
            continue
        field.x, field.y = field.x + field.dx, field.y + field.dy
        assert passable(grid, field.x, field.y)
    field.dx = field.dy = 0

    # autopilot: G from the hero's own bed carries him door by door to the throne room,
    # however many worlds the optional packs put in between, and lets go on arrival
    hero.flags["no-battles"] = True
    app.states[:] = [field]
    app.log.clear()
    field.going = None
    field.travel("home", HOME_SPAWN, quietly=True)
    field.on_key(pygame.K_g)
    assert field.going == "castle" and field.route, "G planned no route"
    for _ in range(6000):                             # a hundred seconds of walking
        app.log.update(1 / 60)
        field.update(1 / 60)
        if field.world.name == "castle":
            break
    assert field.world.name == "castle", f"autopilot stalled in {field.world.name}"
    assert (field.x, field.y) == CASTLE_SPAWN
    assert field.going is None and not field.route, "autopilot never let go"

    # ...and any key takes the reins back, wherever it has got to
    field.travel("alefgard", START, quietly=True)
    field.on_key(pygame.K_g)
    assert field.route, "G planned no route out of Alefgard"
    app.log.clear()                                   # the player must be able to read
    field.on_key(pygame.K_z)
    assert field.going is None and not field.route, "a keypress did not stop autopilot"
    hero.flags["no-battles"] = False

    # every planned step is a legal one, and it ends where it was aimed
    walk = steps_to(grid, START, (24, 36))
    x, y = START
    for dx, dy in walk:
        x, y = x + dx, y + dy
        assert passable(grid, x, y), f"the route walks into {(x, y)}"
    assert (x, y) == (24, 36) and len(walk) >= 5, f"{len(walk)} steps to Brecconary"
    assert not steps_to(grid, START, (35, 46)), "a route was found across the water"
    assert doorway("castle", "castle") is None and doorway("home", "castle")
    app.states.clear()

    # the minimap: one cached picture per world, fitting inside its frame, and it
    # draws for the overworld without touching the interiors' colourless tiles
    mini = minimap(world("alefgard"))
    assert mini is minimap(world("alefgard")), "the minimap is rebuilt every frame"
    assert mini.get_size() == (128, 128), f"the minimap is {mini.get_size()}"
    assert MINIMAP.contains(mini.get_rect(center=MINIMAP.center)), "it overflows its frame"
    field.travel("alefgard", START, quietly=True)
    field.draw_minimap()
    field.travel("castle", CASTLE_SPAWN, quietly=True)
    field.draw_minimap()                              # no tiles, no colours: skipped
    assert not any(name == "castle" for name, _ in _MINI), "an interior drew a minimap"

    # M indoors says so and opens nothing; M in the open world opens the map screen,
    # and M again closes it
    app.log.clear()
    field.on_key(pygame.K_m)
    assert not app.states and "No map" in "".join(l for l, _ in app.log.pending)
    field.travel("alefgard", START, quietly=True)
    app.log.clear()
    field.on_key(pygame.K_m)
    assert isinstance(app.top, MapState), "M did not open the map"
    chart = app.top

    # every landmark is listed once, under a number that fits its window, and the
    # names fit the legend column -- a longer name would be silently clipped
    names = list(dict.fromkeys(PLACES.values()))
    assert len(names) == len(set(names)) == len(PLACES) - 1, "the Swamp Cave listed twice"
    assert LEGEND.y + 12 + len(names) * 22 < LEGEND.bottom - 44, "the legend overflows"
    for text in [f"{i + 1:>2}. {p}" for i, p in enumerate(names)] + list(KEY):
        assert chart.small.size(text)[0] <= LEGEND.w - 24, f"clipped: {text!r}"
    # the castles are named on the map itself, and the name stays on the map: one side
    # of the keep or the other, whichever fits
    cell = minimap(world("alefgard"), MAPWIN.w - 8).get_width() / 64
    for (x, y), place in PLACES.items():
        if "Castle" not in place:
            continue
        px = MAPWIN.centerx - MAPWIN.w / 2 + 4 + (x + 0.5) * cell
        wide = chart.small.size(place)[0]
        assert (px + 7 + wide < MAPWIN.right - 6 or px - 7 - wide > MAPWIN.left + 6), \
            f"{place} has nowhere to write its name"
    app.screen.fill(BLACK)
    chart.draw()
    chart.on_key(pygame.K_m)
    assert chart.done, "M did not close the map"
    app.states.clear()

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
    else:
        print(__doc__.strip().splitlines()[-2].strip())
