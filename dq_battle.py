#!/usr/bin/env python3
"""The Last Slayer: Project 2026 -- the battle system, modelled on Dragon Quest (NES).

Structure follows Silvio Carrera's three-part series:
  I   - Character / Command / StateBattle loop
  II  - typewriter log window (textSpeed, TOTAL_LINES, CHARS_PER_LINE, scroll)
  III - player window + command window, DQ1 damage + escape formulas

The math is the original Dragon Warrior's, which is what the series is modelling.

Battles are a state on the app's stack: push a BattleState, it pops itself when
the fight ends and calls `on_end(outcome)`.

    endless arena:  .venv/bin/python dq_battle.py
    check:          .venv/bin/python dq_battle.py --test
"""
import random
import sys
from dataclasses import dataclass, field, replace

import pygame

import sounds
import sprites
from app import App, BLACK, MENU_AT, NAME, MessageLog, RED, WHITE, rect, window

# ------------------------------------------------------------------ rules

def rnd(a, b):
    return random.randint(a, b)


# DQ1 level table: exp to reach, strength, agility, max hp, max mp
LEVELS = [
    (0, 4, 4, 15, 0), (7, 5, 4, 22, 0), (23, 7, 6, 24, 5), (47, 7, 8, 31, 16),
    (110, 12, 10, 35, 20), (220, 16, 10, 38, 24), (450, 18, 17, 40, 26),
    (800, 22, 20, 46, 29), (1300, 30, 22, 50, 36), (2000, 35, 31, 54, 40),
    (2900, 40, 35, 62, 50), (4000, 48, 40, 63, 58), (5500, 52, 48, 70, 64),
    (7500, 60, 55, 78, 70), (10000, 68, 64, 86, 72), (13000, 72, 70, 92, 95),
    (16000, 72, 78, 100, 100), (19000, 85, 84, 115, 108), (22000, 87, 86, 130, 115),
    (26000, 92, 88, 138, 128),
]
SPELL_LEVELS = {3: "HEAL", 4: "HURT", 7: "SLEEP", 10: "STOPSPELL",
                17: "HEALMORE", 19: "HURTMORE"}
SPELL_COST = {"HEAL": 4, "HURT": 2, "SLEEP": 2, "STOPSPELL": 2,
              "HEALMORE": 8, "HURTMORE": 5}
XP_MULT = 20  # ponytail: demo pacing, you reach the Dragonlord in an evening. 1 = authentic grind.


def melee_damage(attack, defense):
    """DQ1 physical hit. `defense` is the target's agility (monster) or defense (hero)."""
    if attack < defense // 2:                       # outclassed: glancing blow only
        return rnd(0, (attack + 4) // 6)
    base = attack - defense // 2
    return rnd(base // 4, base // 2)


def hero_attack_damage(hero, foe):
    if rnd(1, 32) == 1:                             # "Excellent move!" ignores defense
        return rnd(hero.attack // 2, hero.attack), True
    dmg = melee_damage(hero.attack, foe.agility)
    if dmg < 1:
        dmg = rnd(0, 1)                             # coin flip for a scratch
    return dmg, False


def can_escape(hero, foe):
    return hero.agility * rnd(0, 255) >= foe.agility * rnd(0, 255) * foe.group_factor


def foe_ambush(hero, foe):
    return hero.agility * rnd(0, 255) < foe.agility * rnd(0, 255) * 0.25


def try_wake(actor, odds):
    """First turn asleep is always lost; after that 1-in-`odds` to wake."""
    actor.asleep += 1
    if actor.asleep > 2 and rnd(1, odds) == 1:
        actor.asleep = 0
        return True
    return False


def resisted(strength_16ths):
    return rnd(0, 15) < strength_16ths


# ------------------------------------------------------------------ actors

@dataclass
class Monster:
    name: str
    hp: int
    strength: int
    agility: int
    xp: int
    gold: int
    shape: str
    color: tuple
    tier: int = 1
    dodge: int = 1           # in 64ths
    sleep_resist: int = 0    # in 16ths
    stop_resist: int = 0
    hurt_resist: int = 0
    group_factor: int = 1    # escape difficulty
    moves: tuple = ()        # ((action, weight), ...) alongside a plain attack
    art: str = ""            # a sprites.ACTORS key, or "" to draw it procedurally
    asleep: int = 0
    stopped: bool = False


# Ordered by tier: field.zone_pool() slices this list by distance from home. Every
# one of them is a Pipoya battler -- `art` names the picture, `shape` and `color` are
# only the procedural stand-in for when the pack is not installed.
MONSTERS = [
    Monster("Slime", 3, 5, 3, 1, 2, "slime", (110, 180, 210), tier=1, art="enemy009"),
    Monster("Red Slime", 4, 7, 3, 1, 4, "slime", (210, 120, 180), tier=2,
            art="enemy009a"),
    Monster("Bat", 6, 9, 6, 2, 6, "bat", (140, 120, 170), tier=3, dodge=4,
            art="enemy001"),
    Monster("Ghost", 7, 11, 8, 3, 8, "ghost", (210, 210, 215), tier=4, dodge=4,
            sleep_resist=4, moves=(("SLEEP", 1), ("attack", 3)), art="enemy010"),
    Monster("Imp", 13, 11, 12, 4, 16, "humanoid", (130, 90, 200), tier=5,
            sleep_resist=2, moves=(("HURT", 2), ("attack", 3)), art="enemy024"),
    Monster("Scorpion", 20, 18, 16, 6, 20, "beast", (200, 80, 60), tier=6,
            art="enemy028"),
    Monster("Skeleton", 30, 28, 22, 11, 30, "humanoid", (230, 230, 210), tier=8,
            dodge=4, sleep_resist=6, group_factor=2, art="enemy039"),
    Monster("Wolf", 34, 40, 30, 16, 50, "beast", (120, 130, 170), tier=10,
            dodge=2, group_factor=2, art="enemy014"),
    Monster("Grizzly", 46, 60, 42, 37, 90, "beast", (140, 100, 70), tier=11,
            dodge=2, sleep_resist=4, group_factor=2, art="enemy037"),
    Monster("Metal Slime", 4, 10, 255, 115, 6, "slime", (170, 175, 185), tier=11,
            dodge=15, sleep_resist=15, stop_resist=15, hurt_resist=15,
            group_factor=1, moves=(("flee", 4), ("HURT", 1), ("attack", 2)),
            art="enemy009b"),
    Monster("Green Dragon", 65, 47, 12, 45, 160, "dragon", (70, 140, 90), tier=13,
            sleep_resist=8, group_factor=2, moves=(("fire", 2), ("attack", 3)),
            art="enemy021"),
    Monster("Armored Knight", 90, 94, 42, 90, 150, "humanoid", (180, 180, 190),
            tier=14, dodge=1, sleep_resist=10, stop_resist=6, group_factor=2,
            art="enemy018"),
    Monster("Golem", 70, 120, 60, 5, 10, "humanoid", (210, 195, 140), tier=15,
            sleep_resist=15, stop_resist=15, hurt_resist=15, group_factor=4,
            art="enemy033"),         # DQ1: only the Fairy Flute stops this one
    Monster("Stoneman", 160, 100, 40, 155, 140, "humanoid", (200, 90, 130), tier=16,
            sleep_resist=12, stop_resist=12, group_factor=2, art="enemy033b"),
    Monster("Dragonlord", 100, 90, 75, 0, 0, "dragon", (190, 90, 210), tier=18,
            dodge=2, sleep_resist=15, stop_resist=15, hurt_resist=8, group_factor=4,
            moves=(("HURTMORE", 2), ("STOPSPELL", 1), ("attack", 3)), art="enemy044"),
]


@dataclass
class Hero:
    name: str = "Loto"
    level: int = 1
    exp: int = 0
    gold: int = 0
    hp: int = 15
    mp: int = 0
    herbs: int = 6
    asleep: int = 0
    stopped: bool = False
    # what the Adventure Log remembers besides numbers: "seen:<world>", "met:<name>".
    # It rides along with the hero because the hero is what gets saved.
    flags: dict = field(default_factory=dict)

    @property
    def strength(self):
        return LEVELS[self.level - 1][1]

    @property
    def agility(self):
        return LEVELS[self.level - 1][2]

    @property
    def max_hp(self):
        return LEVELS[self.level - 1][3]

    @property
    def max_mp(self):
        return LEVELS[self.level - 1][4]

    @property
    def attack(self):
        return self.strength            # ponytail: no shop, so no weapon bonus

    @property
    def defense(self):
        return self.agility // 2        # ponytail: no armour either

    @property
    def spells(self):
        return [s for lv, s in SPELL_LEVELS.items() if lv <= self.level]


def eat_herb(hero):
    """Chew one Herb: 23-30 hit points back, capped at full.

    -> the points recovered, or None if there was no Herb to eat. Shared by the battle
    ITEM command and the pause menu, so a Herb is worth the same either way.
    """
    if hero.herbs <= 0:
        return None
    hero.herbs -= 1
    healed = min(rnd(23, 30), hero.max_hp - hero.hp)
    hero.hp += healed
    return healed


def revive(hero):
    """DQ1: the King brings thee back, and it costs half thy gold."""
    hero.hp, hero.mp = hero.max_hp, hero.max_mp
    hero.gold //= 2
    hero.asleep, hero.stopped = 0, False


def encounter_pool(level):
    """Arena mode: monsters near the hero's own level. The field picks by geography."""
    eligible = [m for m in MONSTERS if m.tier <= level] or MONSTERS[:1]
    return eligible[-4:]


# ------------------------------------------------------------------ battle

class Battle:
    """One encounter. Every turn is a generator of log lines; the UI pumps it."""

    def __init__(self, hero, foe):
        self.hero, self.foe = hero, foe
        self.over = None                # 'win' | 'lose' | 'fled' | 'gone'
        self.shake = 0.0
        self.flash = 0.0
        self.sfx = None
        self.script = self.opening()

    def fx(self, sound, text):
        """Name the effect that plays as this line appears, then hand back the line."""
        self.sfx = sound
        return text

    # -- turns ---------------------------------------------------------
    def opening(self):
        yield self.fx("encounter", f"A {self.foe.name} draws near!")
        if foe_ambush(self.hero, self.foe):
            yield f"The {self.foe.name} attacked before {self.hero.name} was ready."
            yield from self.foe_turn()

    def command(self, cmd, arg=None):
        self.script = self.round(cmd, arg)

    def round(self, cmd, arg):
        yield from self.hero_turn(cmd, arg)
        if self.over:
            return
        yield from self.foe_turn()

    def hero_turn(self, cmd, arg):
        h, f = self.hero, self.foe
        if h.asleep:
            if try_wake(h, 2):
                yield f"{h.name} awakes."
            else:
                yield f"{h.name} is asleep."
                return

        if cmd == "FIGHT":
            yield self.fx("attack", f"{h.name} attacks!")
            if rnd(1, 64) <= f.dodge:
                yield self.fx("miss", f"The {f.name} dodges {h.name}'s attack.")
                return
            dmg, crit = hero_attack_damage(h, f)
            if crit:
                yield self.fx("crit", "Excellent move!")
            f.hp -= dmg
            self.shake = 0.3
            if dmg == 0:
                yield self.fx("miss", f"{h.name}'s attack does no damage.")
            else:
                yield self.fx("hit_foe",
                              f"The {f.name}'s Hit Points have been reduced by {dmg}.")
            yield from self.check_win()

        elif cmd == "SPELL":
            if h.stopped:
                yield f"{h.name}'s spell has been blocked."
                return
            if h.mp < SPELL_COST[arg]:
                yield f"{h.name} does not have enough Magic Power."
                return
            h.mp -= SPELL_COST[arg]
            yield self.fx("spell", f"{h.name} chants the spell of {arg.capitalize()}.")
            yield from self.hero_spell(arg)

        elif cmd == "ITEM":
            healed = eat_herb(h)
            if healed is None:
                yield f"{h.name} has no Herbs."
                return
            yield self.fx("heal",
                          f"{h.name} eats a Herb. Hit Points recovered by {healed}.")

        elif cmd == "RUN":
            yield self.fx("run", f"{h.name} started to run away.")
            if can_escape(h, f):
                self.over = "fled"
            else:
                yield self.fx("miss", f"But was blocked in front.")

    def hero_spell(self, spell):
        h, f = self.hero, self.foe
        if spell in ("HEAL", "HEALMORE"):
            healed = min(rnd(10, 17) if spell == "HEAL" else rnd(85, 100),
                         h.max_hp - h.hp)
            h.hp += healed
            yield (self.fx("heal", f"{h.name}'s Hit Points have been restored by {healed}.")
                   if healed else self.fx("miss", "But nothing happened."))
        elif spell in ("HURT", "HURTMORE"):
            if resisted(f.hurt_resist):
                yield self.fx("miss", f"But the {f.name} is unaffected.")
                return
            dmg = rnd(5, 12) if spell == "HURT" else rnd(58, 65)
            f.hp -= dmg
            self.shake = 0.3
            yield self.fx("hit_foe",
                          f"The {f.name}'s Hit Points have been reduced by {dmg}.")
            yield from self.check_win()
        elif spell == "SLEEP":
            if resisted(f.sleep_resist):
                yield self.fx("miss", "But nothing happened.")
            else:
                f.asleep = 1
                yield self.fx("sleep", f"The {f.name} is asleep.")
        elif spell == "STOPSPELL":
            if resisted(f.stop_resist):
                yield self.fx("miss", "But nothing happened.")
            else:
                f.stopped = True
                yield self.fx("cancel", f"The {f.name}'s spell is blocked.")

    def foe_turn(self):
        h, f = self.hero, self.foe
        if f.asleep:
            if try_wake(f, 3):
                yield f"The {f.name} awakes."
            else:
                yield f"The {f.name} is asleep."
                return

        move = self.pick_move()
        if move == "flee":
            self.over = "gone"
            yield self.fx("run", f"The {f.name} is running away.")
            return
        if move == "attack":
            yield self.fx("attack", f"The {f.name} attacks!")
            dmg = melee_damage(f.strength, h.defense)
        elif move == "fire":
            yield self.fx("fire", f"The {f.name} breathes fire!")
            dmg = rnd(16, 23)
        else:
            yield self.fx("spell", f"The {f.name} chants the spell of {move.capitalize()}.")
            if move == "SLEEP":
                h.asleep = 1
                yield self.fx("sleep", f"{h.name} is asleep.")
                return
            if move == "STOPSPELL":
                if rnd(1, 2) == 1:                  # hero shrugs it off half the time
                    yield self.fx("miss", "But nothing happened.")
                else:
                    h.stopped = True
                    yield self.fx("cancel", f"{h.name}'s spell is blocked.")
                return
            dmg = rnd(3, 10) if move == "HURT" else rnd(30, 45)

        if dmg <= 0:
            yield self.fx("miss", f"The {f.name}'s attack misses {h.name}.")
            return
        h.hp -= dmg
        self.flash = 0.25
        yield self.fx("hurt", f"{h.name}'s Hit Points have been reduced by {dmg}.")
        if h.hp <= 0:
            h.hp = 0
            self.over = "lose"
            yield self.fx("death", f"Thou art dead.")

    def pick_move(self):
        f = self.foe
        pool = [(m, w) for m, w in f.moves if not (f.stopped and m in SPELL_COST)]
        if not pool:
            return "attack"
        return random.choices([m for m, _ in pool], [w for _, w in pool])[0]

    # -- resolution ----------------------------------------------------
    def check_win(self):
        f, h = self.foe, self.hero
        if f.hp > 0:
            return
        self.over = "win"
        gained = f.xp * XP_MULT
        h.exp += gained
        h.gold += f.gold
        h.flags[f"slew:{f.name}"] = True          # the quest log reads these

        yield self.fx("victory", f"Thou hast done well in defeating the {f.name}.")
        yield f"Thy experience increases by {gained}. Thy gold increases by {f.gold}."
        yield from self.level_up()

    def level_up(self):
        h = self.hero
        while h.level < len(LEVELS) and h.exp >= LEVELS[h.level][0]:
            hp, mp = h.max_hp, h.max_mp
            h.level += 1
            h.hp += h.max_hp - hp
            h.mp += h.max_mp - mp
            yield self.fx("levelup", "Courage and wit have served thee well.")
            yield f"Thou hast been promoted to level {h.level}."
            if h.level in SPELL_LEVELS:
                yield f"Thou hast learned a new spell: {SPELL_LEVELS[h.level].capitalize()}."


# ------------------------------------------------------------------ drawing

ROOT_MENU = ["FIGHT", "SPELL", "RUN", "ITEM"]

def draw_monster(surf, foe, cx, cy, r):
    c = foe.color
    dark = tuple(max(0, v - 90) for v in c)
    if foe.shape == "slime":
        pygame.draw.polygon(surf, c, [(cx, cy - r), (cx - r * .5, cy), (cx + r * .5, cy)])
        pygame.draw.ellipse(surf, c, rect(cx - r, cy - r * .5, 2 * r, r * 1.5))
        for dx in (-.35, .35):
            pygame.draw.ellipse(surf, BLACK, rect(cx + r * dx - 7, cy + r * .1, 14, 18))
        pygame.draw.arc(surf, BLACK, rect(cx - r * .3, cy + r * .45, r * .6, r * .4), 3.5, 5.9, 3)
    elif foe.shape == "bat":
        for s in (-1, 1):
            pygame.draw.polygon(surf, dark, [(cx + s * r * .4, cy - r * .3),
                                             (cx + s * r * 1.6, cy - r * .9),
                                             (cx + s * r * 1.3, cy + r * .5)])
        pygame.draw.ellipse(surf, c, rect(cx - r * .6, cy - r * .7, r * 1.2, r * 1.5))
        pygame.draw.ellipse(surf, WHITE, rect(cx - r * .3, cy - r * .4, r * .6, r * .45))
        pygame.draw.ellipse(surf, BLACK, rect(cx - r * .1, cy - r * .3, r * .22, r * .3))
    elif foe.shape == "ghost":
        pygame.draw.ellipse(surf, c, rect(cx - r * .8, cy - r, r * 1.6, r * 1.4))
        pygame.draw.polygon(surf, c, [(cx - r * .8, cy), (cx + r * .8, cy),
                                      (cx + r * .8, cy + r * .7), (cx + r * .4, cy + r * .4),
                                      (cx, cy + r * .8), (cx - r * .4, cy + r * .4),
                                      (cx - r * .8, cy + r * .7)])
        for dx in (-.32, .32):
            pygame.draw.ellipse(surf, BLACK, rect(cx + r * dx - 8, cy - r * .5, 16, 20))
    elif foe.shape == "humanoid":
        pygame.draw.polygon(surf, c, [(cx, cy - r * .2), (cx - r * .8, cy + r),
                                      (cx + r * .8, cy + r)])
        pygame.draw.circle(surf, c, (int(cx), int(cy - r * .55)), int(r * .38))
        for dx in (-.32, .32):
            pygame.draw.circle(surf, BLACK, (int(cx + r * dx), int(cy - r * .6)), 5)
        for s in (-1, 1):
            pygame.draw.line(surf, dark, (cx + s * r * .3, cy),
                             (cx + s * r * .95, cy + r * .35), 6)
    elif foe.shape == "beast":
        pygame.draw.ellipse(surf, c, rect(cx - r, cy - r * .35, r * 1.7, r * .95))
        pygame.draw.circle(surf, c, (int(cx + r * .75), int(cy - r * .3)), int(r * .4))
        pygame.draw.polygon(surf, dark, [(cx + r * .5, cy - r * .6), (cx + r * .6, cy - r),
                                         (cx + r * .8, cy - r * .62)])
        pygame.draw.circle(surf, BLACK, (int(cx + r * .95), int(cy - r * .35)), 5)
        for dx in (-.8, -.2, .35):
            pygame.draw.rect(surf, dark, rect(cx + r * dx, cy + r * .45, r * .18, r * .5))
        pygame.draw.line(surf, dark, (cx - r, cy - r * .1), (cx - r * 1.5, cy - r * .6), 7)
    else:  # dragon
        for s in (-1, 1):
            pygame.draw.polygon(surf, dark, [(cx, cy - r * .1),
                                             (cx + s * r * 1.5, cy - r * 1.0),
                                             (cx + s * r * 1.2, cy + r * .4)])
        pygame.draw.ellipse(surf, c, rect(cx - r * .8, cy - r * .3, r * 1.6, r * 1.2))
        pygame.draw.polygon(surf, c, [(cx - r * .2, cy - r * .2), (cx + r * .35, cy - r),
                                      (cx + r * .1, cy - r * .1)])
        pygame.draw.ellipse(surf, c, rect(cx + r * .1, cy - r * 1.35, r * .85, r * .5))
        pygame.draw.polygon(surf, dark, [(cx + r * .25, cy - r * 1.25), (cx + r * .2, cy - r * 1.6),
                                         (cx + r * .45, cy - r * 1.3)])
        pygame.draw.circle(surf, BLACK, (int(cx + r * .65), int(cy - r * 1.15)), 5)
        for dx in (-.5, .1):
            pygame.draw.rect(surf, dark, rect(cx + r * dx, cy + r * .7, r * .22, r * .4))


# ------------------------------------------------------------------ battle state

class BattleState:
    """One encounter as a stack state: pops itself once the fight is settled and
    reports the outcome ('win' | 'lose' | 'fled' | 'gone') to `on_end`."""

    def __init__(self, app, hero, foe, endless=False, on_end=None):
        self.app, self.hero = app, hero
        self.endless, self.on_end = endless, on_end
        self.done = False
        self.index = 0
        self.start(foe)

    # -- flow ----------------------------------------------------------
    def start(self, foe):
        self.battle = Battle(self.hero, foe)
        self.hero.asleep, self.hero.stopped = 0, False
        self.app.log.clear()
        self.menu = None
        self.prompted = False
        self.pose_t = 0.0                             # the monster's own animation clock
        self.foe_h = min(190, 62 + 8 * foe.tier)
        sprites.ensure(foe.art, "idle", self.foe_h)   # pay the load on "draws near"

    def finish(self):
        if self.endless:
            if self.battle.over == "lose":
                revive(self.hero)
            self.start(replace(random.choice(encounter_pool(self.hero.level))))
            return
        if self.on_end:
            self.on_end(self.battle.over)
        self.done = True

    def update(self, dt):
        sounds.music("battle")                   # the field's track resumes on pop
        self.battle.shake = max(0.0, self.battle.shake - dt)
        self.battle.flash = max(0.0, self.battle.flash - dt)
        self.pose_t += dt
        self.pump()

    def pump(self):
        log, b = self.app.log, self.battle
        if not log.idle:
            return
        if b.script:
            b.sfx = None
            try:
                log.push(next(b.script))
            except StopIteration:
                b.script = None
            sounds.play(b.sfx)                   # the line and its sound
            return
        if b.over:
            if not self.prompted:
                log.push("(Press any key.)")
                self.prompted = True
            return
        if self.menu is None:
            if self.hero.asleep:
                b.command("FIGHT")               # asleep: no menu, the turn is lost
            else:
                self.open_menu(ROOT_MENU)

    def open_menu(self, items):
        self.menu, self.index = items, 0

    def choose(self):
        pick = self.menu[self.index]
        if pick == "SPELL":
            if self.hero.spells:
                self.open_menu(self.hero.spells)
            else:
                self.app.log.push(f"{self.hero.name} cannot yet use spells.")
            return
        self.menu = None
        if pick in SPELL_COST:
            self.battle.command("SPELL", pick)
        else:
            self.battle.command(pick)

    def on_key(self, key):
        if not self.app.log.idle:
            self.app.log.skip()
            return
        if self.battle.over:
            self.finish()
            return
        if not self.menu:
            return
        if key in (pygame.K_UP, pygame.K_LEFT):
            self.index = (self.index - 1) % len(self.menu)
            sounds.play("cursor")
        elif key in (pygame.K_DOWN, pygame.K_RIGHT):
            self.index = (self.index + 1) % len(self.menu)
            sounds.play("cursor")
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
            sounds.play("confirm")
            self.choose()
        elif key in (pygame.K_x, pygame.K_ESCAPE) and self.menu is not ROOT_MENU:
            sounds.play("cancel")
            self.open_menu(ROOT_MENU)

    # -- render --------------------------------------------------------
    def draw(self):
        app, b = self.app, self.battle
        sc = app.screen
        sc.fill(BLACK)                           # the battle hides the field beneath

        if b.foe.hp > 0 and b.over != "gone":
            ox = rnd(-5, 5) if b.shake > 0 else 0
            if not sprites.draw(sc, b.foe.art, "idle", self.foe_h, self.pose_t,
                                452 + ox, 330):
                r = min(90, 34 + 5 * b.foe.tier)     # procedural foes stand on the
                draw_monster(sc, b.foe, 452 + ox, 330 - r, r)   # same ground line

        # ponytail: no hero on screen, as DQ1 had it -- the battle is seen through his
        # own eyes, so only the monster, his numbers and the log are drawn
        app.draw_status(self.hero)

        if self.menu and app.log.idle and not b.over:
            m = pygame.Rect(*MENU_AT, 180, 16 + 22 * len(self.menu))
            window(sc, m)
            for i, item in enumerate(self.menu):
                y = m.y + 8 + i * 22
                if i == self.index:
                    app.text(">", m.x + 10, y)
                cost = f" {SPELL_COST[item]}" if item in SPELL_COST else ""
                app.text(item.capitalize() + cost, m.x + 28, y)

        app.draw_log()

        if b.flash > 0:
            pygame.draw.rect(sc, RED, sc.get_rect(), 8)


# ------------------------------------------------------------------ self-check

def selftest():
    random.seed(7)
    hero = Hero()
    slime = replace(MONSTERS[0])

    # glancing-blow branch: hopeless attacker still scratches for at most (atk+4)/6
    assert all(melee_damage(4, 100) <= 1 for _ in range(300))
    # normal branch stays inside (base/4 .. base/2)
    assert all(13 <= melee_damage(92, 75) <= 27 for _ in range(300))
    # a level 1 hero never one-shots nor whiffs forever on a Slime
    rolls = [hero_attack_damage(hero, slime)[0] for _ in range(400)]
    assert min(rolls) == 0 and 1 <= max(rolls) <= hero.attack and sum(rolls) > 0

    # sleep: first turn is always lost, and sleep always ends eventually
    victim = replace(slime, asleep=1)
    assert try_wake(victim, 3) is False
    assert any(try_wake(victim, 3) for _ in range(200))

    # stopspelled monsters fall back to plain attacks
    dl = replace(MONSTERS[-1], stopped=True)
    fight = Battle(Hero(level=20, hp=138, mp=128), dl)
    assert all(fight.pick_move() == "attack" for _ in range(50))

    # a full battle terminates and pays out
    hero = Hero(level=5, hp=35, mp=20)
    b = Battle(hero, replace(slime))
    for _ in range(400):
        if b.script:
            try:
                next(b.script)
                continue
            except StopIteration:
                b.script = None
        if b.over:
            break
        b.command("FIGHT")
    assert b.over == "win" and hero.exp == 1 * XP_MULT and hero.gold == 2

    # level ups chain through the table and top out
    grinder = Hero(exp=26000)
    assert list(Battle(grinder, replace(slime)).level_up())
    assert grinder.level == 20 and grinder.hp == 15 + 138 - 15

    # every effect a turn names must exist in the sound bank
    bank, named = set(sounds.voices()), set()
    for proto in MONSTERS:
        champion = Hero(level=20, exp=26000, hp=138, mp=128, herbs=3)
        fight = Battle(champion, replace(proto))
        for _ in range(300):
            while fight.script:
                fight.sfx = None
                try:
                    next(fight.script)
                except StopIteration:
                    fight.script = None
                    break
                named.add(fight.sfx)
            if fight.over:
                break
            fight.command(random.choice(["FIGHT", "SPELL", "ITEM", "RUN"]),
                          random.choice(champion.spells))
    assert named - {None} <= bank, f"no such sound: {named - bank - {None}}"
    assert {"encounter", "attack", "hit_foe", "hurt", "victory"} <= named

    # log wraps, scrolls to TOTAL_LINES, and finishes typing
    log = MessageLog(20)
    log.push("Thou hast done well in defeating the Green Dragon.")   # 3 lines
    log.push("Thy experience increases by 900.")                     # 2 more, so it scrolls
    for _ in range(2000):
        log.update(1 / 60)
    assert log.idle and len(log.lines) == MessageLog.TOTAL_LINES
    assert log.lines[-1] and int(log.revealed) == len(log.lines[-1])

    print("ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
    else:                                        # arena mode: nothing but battles
        app = App(f"{NAME} - Battle   [arrows  Z confirm  X back]")
        hero = Hero()
        app.push(BattleState(app, hero, replace(MONSTERS[0]), endless=True))
        app.run()
