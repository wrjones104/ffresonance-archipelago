# Roadmap

What to build next, in order, and what goes together. The ideas themselves, with what is known, are in [IDEAS.md](../IDEAS.md); numbers below are its idea numbers (done ones are in [ideas_archive.md](ideas_archive.md)). This file says only the order and the reasons. Written 2026-11-22, after v0.31.0.

## Where we are

A tester (2026-11-22, v0.31.0, Normal scaling, progression balancing 65) finished a full seed. Their `UE4SS.log`:

| | |
|---|---|
| Time | about 7.5 hours, start to `Goal complete!` |
| Party level at the last battle | 30 |
| Battles won | 107; median 36 s off the field, 90% under 3 minutes |
| Checks sent | 286: 121 chests, 120 shinies, 14 bosses with their 14 fragments, 12 crystals, 3 gifts, 2 radar |
| Side quests | off (the default) |
| Errors or crashes | none |

What they said: fun and well-rounded; early and mid game fast, late game fine; status effects hard with no Ribbon and few cures; magicite tight but fair; they thought level scaling was a gate at first; their partner's items felt back-loaded (likely the seed). They asked for a separate save location per seed, and a PopTracker pack.

So the core loop works. The next work is less about making a seed finishable and more about making it a good seed: a fair item pool, logic that covers what the open start skips, and a game that tells the player what is going on.

**Rounds 109 to 111:** the new start (idea 52) went ahead of the order, because with autosave off the prologue skip never runs and the seed breaks at the start. It passed round 110 and is on by default; round 111 is a full run on it.

## The order

Each milestone is about one release. The first three are in the order I would do them. After that the order is looser.

### 1. Item pool pass (next release)

**Built in round 104** (world 0.32.0 build 94562703): the gear, `extra_magicite` and `early_healing_vision` (archived idea 48), passed in game. **Round 105** (world build e38986f1, mod build 395095c2): Lid's airship line, and Aileen's weapons moved up from milestone 4, as they shape the pool too (`include_aileens_forge`, docs/side_quests.md section 7). Both wait for round 105's test.

Straight from the feedback, and mostly apworld work.

- Add items the pool has never had because they are drops or steals, not chest or quest rewards: Ribbon first, then the status-resist accessories. Each one takes a filler slot.
- More Magicite in the pool, in place of low filler (Potions, small gil).
- An option to put one support vision (healing or status cure) early: `early_support_vision`. Archipelago's `local_early_items` does the placing. Until then, a player can put the vision in `early_items` in their yaml.
- Check the filler-to-useful ratio after the changes, so the pool does not tip into all useful items.
- Lid's "We already found Mysidia..." line on the airship (scratchpad). Small, and it can ride along.

Why first: it is the cheapest change with the most effect on how a seed plays, and it needs no new in-game probes. The numbers and the design are in idea 48, now in ideas_archive.md.

### 2. Tell the player what is going on (UX)

Ideas 54, 11, 22, 49 and 38. Most are the same problem: the player cannot see the seed's state in the game. 49 is on the same page and uses the same row code.

- **Save-slot cards (11).** Mark an Archipelago save on its card: seed and slot name. This answers the "which save is which" problem. A separate save folder per seed is a much bigger change (the engine picks the path) and the cards may be enough. Look at the folder only if testers still mix saves up after the cards.
- **Explain scaling.** One line on the Seed tab ("Enemies scale to your party level, so no area is out of reach") and a short paragraph in the README and the playtester guide. Cheap. The tester thought they were gated.
- **Standard or custom scaling (49).** A switch on the Settings page: Standard shows the three strengths, Custom shows the round 102 sliders. The sliders are in git (`891e70d`), so most of the work is showing and hiding rows. Do it after the scaling line, so the line can say how to change it.
- **A start that cannot go wrong (54).** No second move for a walking player, move input held during the move, and the client's heartbeat so the Archipelago entry needs a live client. Do it first in this group: a frozen start makes a player start over.
- **Welcome window (22).** On a new Archipelago game: the scaling line, how continents open, where the page is. The game's dialog rows look like the way (idea 54), and the window can cover the start's move.
- **Page layout (38).** Headings and framed rows. Nice, not needed. Leave it last in this group.

### 3. Finish the logic: story abilities (40) and side quests on

Boss logic itself is built (world 0.25.0 and 0.28.0: `boss_logic.py`, archived idea 29). The first version of this roadmap had it as the next big job; that was wrong. What is left:

- Idea 40: the abilities the open start skips. The capability matrix (`data/game/capabilities.tsv`) counts what each member learns, so an ability the story would have given and our start does not may make logic think the party can do something it cannot.
- Sephiroth (scratchpad): check that his rule keeps him late enough.
- Turn `include_side_quests` on by default. Its logic (side_quests.md, section 5) is done.
- The first full tester run finished at party level 30 with no complaints about bosses, so this is checking and tuning, not a redesign.

### 4. More locations

Add the locations that wait on the logic. Most valuable first:

1. The rest of the bosses: tier 3 story bosses still missing, then tier 2 (espers, Chamber of Arms, Arena). This also closes the "not done yet" known issue. ([bosses.md](bosses.md), section 5.)
2. Mechabo quests as locations (33). A quest chain the mod already runs. (Aileen's weapons were built in round 105, with milestone 1.)
3. Stat bonuses as items (45), once it is known what writes them.
4. Shopsanity (31), with the merchant ships and hints for gil (idea 25, item 5). Gil has little use now, and this gives it one.
5. Librasanity and enemysanity (30), and abilities as checks (28). Hundreds of locations, so they need lots of filler. Do them after the pool pass has settled what good filler is.

### 5. Multiworld features: DeathLink and traps

Ideas 41 and 20, together. Both need the same piece: something to bank until the next battle starts, then act on the party. Build the battle-start hook and the bank once, then DeathLink and each trap are small on top of it. DeathLink is the one the Archipelago community expects; traps follow.

### 6. PopTracker pack (47)

After milestones 3 and 4, not before. A pack copies the logic and the location list, so each logic change or location rename means a pack update. Universal Tracker already works from the apworld and covers players until then. Do the Tablet Shard names (34) before this, so the pack's names are the final ones.

### 7. Randomizer extras

Ideas 7 (enemy randomization), 8 (stats, weaknesses), 9 (music), 46 (custom visions) and 50 (the field character follows the party leader), and boss order (25, item 3). Fun, but none of them make a seed fairer.

- 50 is cosmetic but touches the field pawn, which the airship position and gate crossings read (round 69). Cutscenes may look for Rain. Its first step is cheap and goes under Polish: test the Nexus "Change field Leader" mod (Party Members Only) with ours.

- 8 and boss logic touch the same thing: boss logic reads each boss's weaknesses from fixed tables. Weakness randomization must hand its rolls to the logic too, or the logic asks for the wrong elements.
- 7 and 8 clash with FFR Randomizer (10). Settle the compatibility story first.

### Long shot

The in-game client (12). Option B (start the client from the game) is a quality-of-life change with some risk; option A (a C++ client) is a project of its own. Only if players keep tripping on the separate client.

## Polish, any time

Small items to pick up when a round has room:

- Two checks at once: the second pop-up shows the game's item (15, known issue).
- The palace safes after a shard comes in (37): leave unless cheap (the user).
- The Seed tab cannot scroll with a gamepad (39).
- The two missing gifts, 1407 and 1409 (43).
- A compatibility list in the README (10).
- Test the Nexus "Change field Leader" mod, Party Members Only version, with ours, and list it if it works (50, way 1). Its permissions do not let us take its code.
- Artifacts: parked (scratchpad).

## What goes together

| Group | Ideas | Shared piece |
|---|---|---|
| Item pool | pool pass (built), 45, Aileen's weapons (built) | the pool's filler budget |
| In-game state | 11, 22, 38, 49, scaling line | showing seed state in the game's UI; the page's rows |
| Logic | 40, side quests on by default, Sephiroth | the capability matrix |
| Battle start | 20, 41 | the banked-effect hook |
| Gil | 31, hints (25.5) | a reason to spend gil |
| Big location counts | 28, 30 | lots of filler |
| Enemy data | 7, 8, boss logic | the logic must read the rolled weaknesses |
| Names | 34, 47 | final location names before a pack |
| Other mods | 10, 50 | the compatibility list |
