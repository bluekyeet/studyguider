# Rewards: points, gacha, collectables, a dressable character and leaderboards

Purpose: make correct study feel good. Points are earned only from work the app has already recorded as correct, and are spent on
cosmetic collectables. Nothing here changes marking, teaching, grades or what the app tells you about your learning.

## Principles

- **Earn by learning, correctly.** No points for opening the app, for wrong answers, for skipped questions, or for attempts the
  marker called uncertain.
- **Derived, not granted.** Earnings are computed from the account's own records (review answers, marked exam questions,
  completed lessons, marked papers) every time they are read. There is no "award points" call to forge or double-fire, and
  re-marking the same question never pays twice. Spending is the only thing stored.
- **Cosmetic only.** Items never affect marking, schedules, difficulty or the grade estimate.
- **Honest numbers.** Estimated grade and GPA are the existing rough estimates (review mastery, and marked-paper marks against the
  app's A/M/E bands). They are labelled unofficial everywhere; AI practice counts for points but is never shown as a real paper.
- **Private by default for data, social by choice.** Leaderboards show username, picture, the character and counts. An account can
  hide itself from them in the Rewards page. Nothing else about a learner (answers, topics, resources) is ever shown.

## Earning (per account)

| Source | Points | Counted once per |
| --- | --- | --- |
| Review question answered correctly | 5 | question per day (re-answering on a later day pays again; spaced repetition is real practice) |
| Exam or rapid question marked Achieved / Merit / Excellence | 4 / 6 / 8 | question in an exam |
| Lesson completed | 25 | lesson |
| Full paper marked, grade Achieved / Merit / Excellence | 60 / 100 / 160 | paper (rapid sessions excluded) |
| Day with at least one correct answer | 10 | day |
| Welcome gift | 200 | account |

A "paper" counts when it has at least three questions, every one answered and marked, then graded with the app's own bands (50% Achieved, 70% Merit,
85% Excellence of marks available). Not achieved earns nothing for the paper (the question points still count).

`balance = earned + sum(ledger)` where the ledger holds spending (negative) and refunds from recycling (positive).

## Spending

- **Gacha** — 100 points per pull, 10 pulls for 900. Odds: common 55%, uncommon 25%, rare 12%, epic 5%, legendary 2.5%,
  mythic 0.5%. Pity: a rare or better at least every 10 pulls, an epic or better at least every 30. Duplicates stack (`x2`, `x3`)
  and can be recycled for 40% of their value.
- **Item shop** — fixed prices (common to rare items; epic and above are gacha-only). Price is 1.5 x the item value.
- **Recycle** — turn spare duplicates back into points; the last copy is never sold by recycling.

## Collection

More than 3,200 items across 12 slots, with statement pieces (kimono, ball gown, royal robe, pirate coat, space suit, hakama, tutu, glass slippers, tiara, viking helmet, dragon wings and more) cut to fit both bodies, built from styles x colours so the catalogue is large and consistent.

| Slot | Worn on the character | Examples |
| --- | --- | --- |
| background | yes | graph paper, sunset, starfield, library |
| aura | yes | glow, sparkles, flames |
| back | yes | cape, angel wings, bat wings, backpack, jetpack |
| hair | yes | bob, spikes, afro, ponytail, mohawk |
| face | yes | round glasses, sunglasses, monocle, moustache, eyepatch |
| hat | yes | wizard hat, crown, grad cap, halo, headphones |
| top | yes | hoodie, lab coat, armour, jumper, dress |
| bottom | yes | jeans, shorts, skirt, track pants |
| shoes | yes | sneakers, boots, sandals, skates |
| held | yes | book, trophy, flask, telescope, wand |
| pet | yes | cat, owl, slime, robot, dragon, ghost |
| trinket | no — collectable | atom, DNA, pi, microscope, planet cards and medals, shown on a shelf |

The character is a chibi (a large head on a small body) and every item is drawn to one style: an outline in a deep shade of the
item's own colour, one soft shadow and one highlight. Small pictures (leaderboard rows) show head and shoulders
(`/game/art/avatar.svg?crop=bust`). How the art was arrived at, with contact sheets of each round, is in
`docs/design/avatar-iterations/`.

Colours include plain, metallic (silver, gold, bronze) and special finishes (rainbow, galaxy, holo, neon). A colour can lift an item
one or more rarities. Rarity sets value: 10 / 25 / 60 / 150 / 400 / 1000.

## Flexing

- A **showcase** shelf of up to six pieces shown on your profile card.
- Anyone can open another player's card: character, showcase, collection size, rarest item, completion %.
- Net worth counts what you own, so a rare pull is a flex whether you wear it or not.

## Leaderboards

All use only counts from correct, recorded work.

| Board | Measure |
| --- | --- |
| Net worth | points balance + value of every item owned |
| Questions | correct review answers + marked-correct exam and rapid questions |
| Lessons | lessons completed |
| Papers | complete papers marked at Achieved or better |
| Estimated grade | mean of per-topic estimates (needs a topic with 5+ review answers) |
| Estimated GPA | the same estimate on a 0-9 scale |
| Collection | distinct items owned |

GPA scale from topic mastery: 0 -> 0, 0.4 -> 3, 0.6 -> 5, 0.8 -> 7, 1.0 -> 9 (linear between). Unofficial.

## Where it lives

- Per-account schema (`u<id>`): `game_ledger`, `game_items` (owned + count), `game_outfit` (worn), `game_showcase`, `game_state`
  (skin tone, pity counters, visibility).
- Shared `public.game_profiles`: a snapshot of each account's totals, refreshed when the account uses Rewards and by the server's
  periodic tick, so leaderboards need no cross-schema queries and never reach into another account's study data.
- `game_items.py` (catalogue), `game_art.py` (SVG for items and the character), `game.py` (economy, API).
- API: `/game/me`, `/game/catalog`, `/game/pull`, `/game/shop/buy`, `/game/recycle`, `/game/outfit`, `/game/showcase`,
  `/game/settings`, `/game/leaderboard/{board}`, `/game/players/{id}`, and public deterministic art at `/game/art/...`.
- UI: a Rewards page on the website and a native Rewards screen on Android (opened from Home) with the same four sections. The
  server draws all art; the website uses `/game/art/...svg`, the app `/game/art/...png?w=` (rendered with cairosvg, widths 32-768).
- Check: `server/tests/game_check.py` runs the whole API against a throwaway PostgreSQL; `tests/test_game.py` covers the rules.

## Not doing

No real money, no timers that punish a missed day, no trading between accounts, no effect on marking, no items that hide or
change what a question says.
