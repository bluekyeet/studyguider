# Rewards character and item art: how the redesign went

The art is drawn by `server/game_items.py` (SVG for the website, the same SVG rendered to PNG for the Android app). Item ids,
names, rarities, prices and the shop/gacha rules did not change in any round: only the drawings did.

Each folder holds contact sheets photographed from the real drawing code at that point:
`base` (both bodies, every skin, the small sizes), `zoom`, `combos` (twelve whole outfits), `worn-<slot>` (every style of a slot
on the character), `icons` and `icons-light` (every style as the shop and wardrobe show it, dark and light theme).

Redraw them with `CHROME=<a Chromium browser> sh docs/design/avatar-iterations/shoot.sh <folder>`. Nothing needs a server or a database.

## 0-before: the starting point

- A tall, stiff mannequin (about four heads high) with big anime eyes: two styles in one figure.
- Three different outlines: skin in a darker skin tone, clothes in a faint 38% ink, eyes in solid ink.
- Items were flat single-colour shapes with no shading, so a hat, a top and a pet did not look like they came from one set.
- Things "held" floated beside the hand; pets were small blobs; wings and capes were hidden behind the body.
- Hats sat on top of big hair (afro, spikes, bun) instead of on the head.
- At the 32 px leaderboard size the whole figure was a few pixels of colour.

## 1-round: one style for everything

- **Chibi proportions.** The head is 1.2x and the body 0.82x of the old sizes (about 2.6 heads high). Head pieces and body pieces
  are drawn in their own spaces and placed by one transform each, so every drawing keeps one coordinate system.
- **One outline rule.** Every shape is outlined at the same weight in a deep shade of its own colour (skin, cloth, metal alike).
- **One shading rule.** A soft shadow on the right and a highlight on the upper left, laid over the fill so it works on
  gradients (rainbow, galaxy, holo) too.
- Every one of the 156 styles redrawn to those rules: shoes with soles and laces, clothes with hems, cuffs, collars and folds,
  hats with bands and brims, hair with a shine band, pets with faces.
- Held things are gripped: they are drawn at the hand and the hand is drawn again over them.
- Hair has a "crest" (bun, spikes, top of an afro) that is left out under hats that cover the head.
- Backgrounds share a floor, a soft light and a vignette so the character stands in a room, not on a flat colour.

Weaknesses seen in the round 1 sheets, to fix next:

1. The shadow under the fringe is too heavy and a pale cheek patch reads as a stain on darker skins.
2. Hair has a double outline along the crown (back and fringe do not share an edge) and lumps beside the ears.
3. The masculine brows slope inward: the default face looks stern.
4. Pets are too small and overlap what is held (the owl covers the flask).
5. Backpack, shell and short cape are almost entirely hidden behind the body.
6. Auras are thin: flames only at the edges, small hearts, a hairline orbit.
7. Glasses rims are so heavy they hide the eyes; the tank top and swim top straps are square brackets.
8. The graph-paper curve runs behind the head like antennae.
9. Icons: the mannequin's forehead shadow looks like a skull cap on face items.
10. The 32 px leaderboard picture is still unreadable (it shows the whole figure).
11. Dark items (black, obsidian) disappear into the dark stage behind the character.

## 2-round: fixing what round 1 showed

- Face: lighter fringe shadow, no cheek patch; the fringe and the hair behind it now share one crown edge (no double line, no
  lumps by the ears); the short fringe no longer points a lock down between the eyes.
- Pets are 18% larger and stand on the other side of the character, so they never cover what the hand holds. Held things are 12% larger.
- "Back" items can have a part in front of the body: capes fasten with a collar and a gold clasp, the backpack has straps. The
  shell and short cape are wider so they show past the arms.
- Auras are bolder: a ring of flames, larger hearts and petals, a thick orbit.
- Thinner glasses rims, proper straps on the tank top and swim top, the graph-paper curve is gone.
- The mannequin on item icons has no forehead shadow.
- **Small pictures.** `/game/art/avatar.svg|png?crop=bust` gives head and shoulders; leaderboard rows use it at 40 px (web and Android).
- **Stage.** One `--stage` backdrop for every place the character stands (stage, banner portrait, podium, rows): a lighter indigo
  spotlight in the dark theme so black and obsidian items stay visible, a pale one in the light theme.

Weaknesses seen in the round 2 sheets, to fix next:

1. A large render of the face shows why the default still looks stern: the upper lash line is heavy and flat, both eyes use the
   same (unmirrored) lash, and the brows are hidden under the fringe.
2. The long front locks are slabs with square ends.
3. The flame aura is a wall with a flat bottom edge.
4. Bat wings are dark-on-dark in most colours.
5. Held and pet icons are mostly mannequin: the thing itself is small in the corner.
6. The torso is a box; the body has less character than the head.
7. Trinkets and the Rewards page itself have not been looked at with the new art yet.
