# Dragon Quest I data

NES/Dragon Warrior names (the GBC remake renames Erdrick→Loto, Lorik→Lars,
Gwaelin→Lora, Dragonlord→DracoLord — pick one set and stay in it).

Values marked **(?)** are from memory and should be checked against a DQ1
mechanics FAQ before they ship. Everything already implemented in `dq_battle.py`
is not repeated here — that file is the source of truth for combat math.

## Spells

| Spell | Lv | MP | Effect |
|---|---|---|---|
| HEAL | 3 | 4 | restore 10–17 HP |
| HURT | 4 | 2 | 5–12 damage |
| SLEEP | 7 | 2 | enemy loses turns until it wakes (1/3 per turn) |
| RADIANT | 9 | 3 | light radius 3 in caves, decays over ~100 steps |
| STOPSPELL | 10 | 2 | blocks enemy spells for the fight |
| OUTSIDE | 12 | 6 | exit a dungeon to the overworld |
| RETURN | 13 | 8 | warp to Tantegel Castle |
| REPEL | 15 | 2 | weak monsters stop appearing for ~64 steps (?) |
| HEALMORE | 17 | 8 | restore 85–100 HP |
| HURTMORE | 19 | 5 | 58–65 damage |

Outside battle: HEAL, HEALMORE, RADIANT, OUTSIDE, RETURN, REPEL.
In battle: HEAL, HURT, SLEEP, STOPSPELL, HEALMORE, HURTMORE.

## Equipment

Attack = strength + weapon. Defense = agility/2 + armour + shield.

| Weapon | Atk | Gold | | Armour | Def | Gold | | Shield | Def | Gold |
|---|---|---|---|---|---|---|---|---|---|---|
| Bamboo Pole | 2 | 10 | | Clothes | 2 | 20 | | Small Shield | 4 | 90 |
| Club | 4 | 60 | | Leather Armor | 4 | 70 | | Large Shield | 10 | 800 |
| Copper Sword | 10 | 180 | | Chain Mail | 10 | 300 | | Silver Shield | 20 | 14800 |
| Hand Axe | 15 | 560 | | Half Plate | 16 | 1000 | | | | |
| Broad Sword | 20 | 1500 | | Full Plate | 24 | 3000 | | | | |
| Flame Sword | 28 | 9800 | | Magic Armor | 24 | 7700 | | | | |
| Erdrick's Sword | 40 | — | | Erdrick's Armor | 28 | — | | | | |

Magic Armor halves HURT damage and heals 1 HP per step. Erdrick's Armor also
negates swamp and Charlock barrier damage. Neither is sold; Erdrick's Sword is
found in Charlock, Erdrick's Armor buried in Hauksness.

## Items

| Item | Gold | Effect |
|---|---|---|
| Herb | 24 | restore 23–30 HP (max 6 carried in the original) |
| Torch | 8 | light radius 1 in caves until you leave |
| Magic Key | 53 (?) | opens one locked door, consumed. Rimuldar only |
| Wings | 70 | warp to Tantegel from the overworld |
| Dragon's Scale | 20 | +2 defense while worn |
| Fairy Water | 38 | weak monsters avoid you for a while |
| Fairy Flute | — | puts the Golem outside Cantlin to sleep |
| Gwaelin's Love | — | reports position and exp to next level |
| Cursed Belt / Death Necklace | — | cursed; needs the old man in Rimuldar to remove |

Shops buy back at half price. Bag holds 10 items.

## World of Alefgard

Rough layout, not a tile map — author the real grid as ASCII in `data/alefgard.txt`.

- **Tantegel Castle** — start. King Lorik, the Adventure Log (save), throne room
  treasure, and a basement holding the **Stones of Sunlight**. Charlock is visible
  across the water to the south.
- **Brecconary** — beside Tantegel. First shops, inn, the healer.
- **Garinham** — north-west. Below it the **Grave of Garinham**, a multi-floor cave
  holding the **Silver Harp**.
- **Kol** — north. Fairy Flute buried under a tile; searchable spots.
- **Rimuldar** — east, across a bridge. Sells **Magic Keys**; the old man who lifts
  curses lives here.
- **Cantlin** — far south-west, the largest town, best shops. A **Golem** blocks the
  entrance until the Fairy Flute plays.
- **Hauksness** — ruined town in the south. An **Axe Knight** guards **Erdrick's Armor**,
  buried under a specific tile.
- **Erdrick's Cave** — south of Tantegel. **Erdrick's Tablet** on the lowest floor sets
  the quest: find the Token, then the three relics.
- **Swamp Cave** — the tunnel between Kol and Rimuldar. **Princess Gwaelin** is held at
  the far end, guarded by a Green Dragon. Carry her back to Tantegel for her Love.
- **Rocky Mountain Cave** — north-east mountains, brutal for its level band.
- **Rain Shrine** — south-west across the bridge. The old man trades the **Staff of Rain**
  for the Silver Harp.
- **Rainbow Shrine** — east coast. The old man gives the **Rainbow Drop** once you hold
  the Stones of Sunlight, the Staff of Rain and **Erdrick's Token**.
- **Charlock Castle** — the Dragonlord's island. Reached only by using the Rainbow Drop
  on the tile facing it, which raises a bridge. Barrier floor tiles damage you.

## Quest chain

1. King Lorik briefs you; a guard mentions the captured princess.
2. Erdrick's Tablet (Erdrick's Cave) — "find the Token".
3. **Erdrick's Token** — buried in the southern desert; the tablet gives it as a step
   count from a landmark. Gwaelin's Love makes it findable by coordinates.
4. **Silver Harp** — Grave of Garinham. Attracts monsters while carried.
5. **Staff of Rain** — Rain Shrine, in exchange for the Silver Harp.
6. **Stones of Sunlight** — Tantegel basement.
7. **Rainbow Drop** — Rainbow Shrine, needs items 3, 5, 6.
8. Rescue **Gwaelin** from the Swamp Cave (any time; optional but she gives her Love).
9. Bridge to **Charlock**, fight through, take **Erdrick's Sword**.
10. Dragonlord offers half the world. Accept → the game genuinely ends (screen goes
    dark, no continue). Refuse → two-form battle; form two is a dragon.
11. Win → **Ball of Light**, monsters vanish, walk back to Tantegel, refuse the
    kingdom, leave with Gwaelin.

## Monsters

`dq_battle.py::MONSTERS` carries 15 with real stats, ordered by tier: Slime, Red
Slime, Drakee, Ghost, Magician, Scorpion, Skeleton, Wolf, Werewolf, Metal Slime,
Green Dragon, Axe Knight, Golem, Stoneman, Dragonlord. Nine have sprite art; the
rest draw procedurally via `draw_monster`.

Art mapping, since the packs and the bestiary don't line up one-to-one:

| monster | sprite | note |
|---|---|---|
| Slime / Red Slime / Metal Slime | slime_1 / slime_3 / slime_2 | green, fiery, blue-sparkle |
| Wolf / Werewolf / Axe Knight | minotaur_1 / _2 / _3 | horned brutes |
| Golem / Stoneman | golem_2 / golem_1 | mossy stone, ice |
| Dragonlord | golem_3 | obsidian with lit eyes — stands in for his robed first form, not the dragon |

The full DQ1 roster is ~40. When adding the rest (Magidrakee, Druin, Poltergeist,
Droll, Drakeema, Warlock, Metal Scorpion, Wolflord, Goldman, Wyvern, Rogue
Scorpion, Wraith Knight, Blue Dragon, Armored Knight, Red Dragon, Starwyvern,
Wizard, Demon Knight, Knight, Magiwyvern, the Dragonlord's true form …) take
HP/Strength/Agility/exp/gold and the resistance bytes from a mechanics FAQ — do
not estimate them.

`MONSTERS` must stay sorted by tier: `field.zone_pool()` slices it by distance
from Tantegel. Adding entries changes that arithmetic — `field.py --test` asserts
every wild monster can still turn up somewhere reachable.

Spawn zones are defined by the map, not by the monster: each region of Alefgard
has a table of ~5 monsters, and regions get harder with distance from Tantegel.
Model it as a `zone` id per map tile region → list of monster names.

## Terrain

| Tile | Passable | Encounter rate | Notes |
|---|---|---|---|
| Field | yes | low | |
| Forest | yes | high | |
| Hill | yes | high | |
| Mountain | no | — | |
| Water | no | — | |
| Swamp | yes | medium | 2 HP per step (0 with Erdrick's Armor) |
| Desert | yes | medium | |
| Bridge | yes | none | marks a difficulty step |
| Town / Castle / Cave | enter | none | |
| Barrier (Charlock) | yes | high | 15 HP per step (0 with Erdrick's Armor) |
| Stairs / Door / Chest | — | — | interactive |
