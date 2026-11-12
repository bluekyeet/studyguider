"""The rewards catalogue and its art.

Every item is a style (a shape such as "wizard hat") in a colour (such as "Galaxy"), so the catalogue is large but regular. Item ids are
`slot.style.colour`. Art is plain SVG drawn on a 200 x 300 canvas; the same drawing code makes item icons and the whole character, so
the website and the Android app show exactly the same thing. Colour placeholders in a drawing: @c main, @d dark, @l light, @s skin,
@k the outline ink (a deep shade of the item's own colour).

The character is a chibi: a large head on a small body. Head pieces (hair, hats, face) are drawn in head space and body pieces
(clothes, shoes, wings, things held) in body space; `SPACE` maps each onto the canvas, so a drawing never repeats the proportions.
Everything shares one look: an outline in the item's own dark ink, one soft shadow on the right and one highlight on the upper left.
"""
import itertools
import math
import re

ART_VERSION = 7          # bump when drawings change, so cached pictures are fetched again

RARITIES = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]
VALUE = [10, 25, 60, 150, 400, 1000]
ODDS = [55, 25, 12, 5, 2.5, 0.5]
SHOP_MAX_RARITY = 2
SHOP_MARKUP = 1.5
RECYCLE_SHARE = 0.4

# name, main, dark, light, tier (how much the colour lifts rarity)
COLOURS = {
    "red": ("Red", "#e5484d", "#a52a2e", "#ff9a9d", 0), "blue": ("Blue", "#3b82f6", "#1e4fb0", "#9cc1ff", 0),
    "green": ("Green", "#30a46c", "#1d6b45", "#86d9ae", 0), "yellow": ("Yellow", "#f5c518", "#b58f00", "#ffe680", 0),
    "purple": ("Purple", "#8e4ec6", "#5b2d8a", "#cba6ee", 0), "pink": ("Pink", "#ec6aa7", "#b53a78", "#ffb3d5", 0),
    "orange": ("Orange", "#f76808", "#b34700", "#ffb27a", 0), "teal": ("Teal", "#12a594", "#0b6b60", "#7ddfd1", 0),
    "grey": ("Grey", "#8b8d98", "#5a5c66", "#c9cad1", 0), "white": ("White", "#f4f4f6", "#b8b9c2", "#ffffff", 0),
    "black": ("Black", "#2b2b33", "#101014", "#5c5c68", 0), "brown": ("Brown", "#8b5a2b", "#573616", "#c79a68", 0),
    "silver": ("Silver", "#c0c5ce", "#7d838f", "#eef0f4", 1), "bronze": ("Bronze", "#cd7f32", "#8a5220", "#f0b27a", 1),
    "gold": ("Gold", "#f2c230", "#a67c00", "#fff0a8", 2), "neon-pink": ("Neon pink", "#ff2ea6", "#b0006b", "#ff9ad5", 2),
    "neon-green": ("Neon green", "#39ff14", "#0b9a00", "#b6ffa6", 2), "obsidian": ("Obsidian", "#1b1530", "#07040f", "#5b4a8a", 2),
    "rainbow": ("Rainbow", "url(#rainbow)", "url(#rainbow)", "#ffffff", 3), "galaxy": ("Galaxy", "url(#galaxy)", "#1a1040", "#b7a6ff", 3),
    "holo": ("Holo", "url(#holo)", "#6aa8d8", "#ffffff", 3),
}

LIGHT_COLOURS = {"white", "silver", "yellow", "gold", "neon-green", "neon-pink", "holo", "grey"}   # drawn on a dark card

DEFS = ('<defs><linearGradient id="rainbow" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff4d4d"/><stop offset=".25" stop-color="#ffd24d"/>'
        '<stop offset=".5" stop-color="#4dff88"/><stop offset=".75" stop-color="#4da6ff"/><stop offset="1" stop-color="#c04dff"/></linearGradient>'
        '<linearGradient id="galaxy" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1a1040"/><stop offset=".5" stop-color="#5b2d8a"/><stop offset="1" stop-color="#2b6cd8"/></linearGradient>'
        '<linearGradient id="holo" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#9ad0ff"/><stop offset=".35" stop-color="#ffb3f0"/><stop offset=".7" stop-color="#b3ffd9"/><stop offset="1" stop-color="#fff3a8"/></linearGradient>'
        '<radialGradient id="glow"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="vignette" cx=".5" cy=".42" r=".78"><stop offset=".55" stop-color="#1d1140" stop-opacity="0"/><stop offset="1" stop-color="#1d1140" stop-opacity=".3"/></radialGradient></defs>')

SKINS = {"porcelain": ("Porcelain", "#fbe3d0"), "sand": ("Sand", "#f3c9a0"), "honey": ("Honey", "#e0a878"), "tan": ("Tan", "#c68a5a"),
         "umber": ("Umber", "#9a6240"), "cocoa": ("Cocoa", "#6b3f28"), "mint": ("Mint", "#a9e0c4"), "lilac": ("Lilac", "#d1b8ee")}
DEFAULT_SKIN = "sand"

SLOTS = ["background", "aura", "back", "bottom", "shoes", "top", "face", "hair", "hat", "held", "pet", "trinket"]
WORN = [s for s in SLOTS if s != "trinket"]
SLOT_NAMES = {"background": "Backgrounds", "aura": "Auras", "back": "Back", "bottom": "Bottoms", "shoes": "Shoes", "top": "Tops", "face": "Face",
              "hair": "Hair", "hat": "Hats", "held": "Held", "pet": "Pets", "trinket": "Trinkets"}

INK = "#2a2338"          # eyes, mouths and the outline of anything without a plain colour of its own
SHADOW = "#1d1140"       # laid over a shape at low opacity, so the shadow works on every colour and gradient
GOLD, STEEL, CREAM, FLAME = "#f2c230", "#c0c5ce", "#fbfbfd", "#ffb020"
NS = 'stroke="none"'

POLY = lambda pts, fill="@c", extra="": f'<polygon points="{pts}" fill="{fill}" {extra}/>'
P = lambda d, fill="@c", extra="": f'<path d="{d}" fill="{fill}" {extra}/>'
R = lambda x, y, w, h, fill="@c", rx=0, extra="": f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" {extra}/>'
C = lambda x, y, r, fill="@c", extra="": f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" {extra}/>'
E = lambda x, y, rx, ry, fill="@c", extra="": f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{fill}" {extra}/>'
L = lambda x1, y1, x2, y2, stroke="@d", w=3: f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{w}" stroke-linecap="round"/>'
T = lambda x, y, s, size=40, fill="@c", extra="": f'<text x="{x}" y="{y}" font-size="{size}" font-family="Georgia,serif" font-weight="700" text-anchor="middle" fill="{fill}" stroke="none" {extra}>{s}</text>'
STAR = lambda x, y, r, fill="@l", extra="": f'<path d="M{x} {y-r} L{x+r*.28} {y-r*.28} L{x+r} {y} L{x+r*.28} {y+r*.28} L{x} {y+r} L{x-r*.28} {y+r*.28} L{x-r} {y} L{x-r*.28} {y-r*.28}Z" fill="{fill}" {extra}/>'
HEART = lambda x, y, s=1, fill="@c", extra="": (f'<path d="M{x} {y+7*s} C{x-15*s} {y-3*s} {x-7*s} {y-13*s} {x} {y-4*s} C{x+7*s} {y-13*s} {x+15*s} {y-3*s} {x} {y+7*s}Z" '
                                                f'fill="{fill}" {extra}/>')
G = lambda *parts: "".join(parts)
LN = lambda d, extra="": P(d, "none", extra)                                              # a line in the outline ink
DL = lambda d, w=1.4, colour="@d": P(d, "none", f'stroke="{colour}" stroke-width="{w}"')    # a detail line: seams, folds, stitches
SH = lambda d, o=.18: P(d, SHADOW, f'opacity="{o}" {NS}')                                  # shadow
HI = lambda d, o=.4: P(d, "#fff", f'opacity="{o}" {NS}')                                   # highlight
FLIP = lambda markup: f'<g transform="matrix(-1 0 0 1 200 0)">{markup}</g>'                # mirrored left to right
PAIR = lambda markup: markup + FLIP(markup)
AT = lambda x, y, markup, s=1: f'<g transform="translate({x} {y}) scale({s})">{markup}</g>'

# Clothes follow the body: a drawing names body parts (@TORSO, @ARML, @ARMR, @LEGL, @LEGR) and each build supplies its own outline, so
# one T-shirt fits both bodies. Sleeves and trouser legs are the limb outline cut off at a height (the clip paths in `defs`).
CUTS = {"cap": 144, "sleeve": 158, "wrist": 181, "knee": 242, "short": 226, "ankle": 255, "long": 260}
TORSO_CLIP = lambda inner: f'<g clip-path="url(#k-torso)">{inner}</g>'


def _limbs(part, cut, fill, cuff):
    """Both arms or both legs cut off at `cut`, the far one a little darker, with an optional band and a hem line at the cut."""
    y = CUTS[cut]
    out = ""
    for side in "LR":
        limb, clip = f"@{part}{side}", f'clip-path="url(#k-{part.lower()}{side.lower()})"'
        out += f'<path d="{limb}" fill="{fill}" clip-path="url(#k-{cut})"/>'
        if part == "ARM" and side == "R":
            out += f'<path d="{limb}" fill="{SHADOW}" opacity=".14" {NS} clip-path="url(#k-{cut})"/>'
        if part == "LEG":                                                   # the inside of each leg is in shadow
            out += R(92, 196, 16, y - 196, SHADOW, 0, f'opacity=".16" {NS} {clip}')
        if cuff:
            out += R(40, y - 8, 120, 8, cuff, 0, f'{NS} {clip}') + P(f"M40 {y - 8} H160", "none", clip)
        out += P(f"M40 {y} H160", "none", clip)
    return out


ARMS = lambda cut, fill="@c", cuff="": _limbs("ARM", cut, fill, cuff)
LEGS = lambda cut, fill="@c", cuff="": _limbs("LEG", cut, fill, cuff)
TORSO_SHADE = TORSO_CLIP(SH("M117 100 C125 140 123 180 115 215 H150 V100Z") + HI("M60 112 H94 C84 118 77 128 74 142 H60Z", .2))
TORSO = lambda fill="@c": P("@TORSO", fill) + TORSO_SHADE
NECK = P("M88 116 Q100 128 112 116 L108 115.5 Q100 122 92 115.5Z", "@d")
VNECK = lambda fill=CREAM: P("M89 116 L100 150 L111 116Z", fill)
HIPS = P("M72 192 H128 L130 212 H70Z") + SH("M112 192 H128 L130 212 H110Z") + P("M72 192 H128 V199 H72Z", "@d")
SKIRT = lambda d: P(d) + P("M72 192 H128 V199 H72Z", "@d")
BUTTONS = lambda x, ys, fill="@d", r=2: G(*[C(x, y, r, fill, NS) for y in ys])

# Hair is "behind the head ||| the crest ||| in front of the face". The crest is whatever stands above the crown (a bun, spikes, the
# top of an afro); it is left out under a hat that covers the head, so hats sit properly on every haircut.
HAIR = lambda back="", front="", crest="": f"{back}|||{crest}|||{front}"
DOME = "M58 90 C51 46 78 31 100 31 C122 31 149 46 142 90 L136 94 L64 94Z"
BACK = P(DOME) + SH(DOME, .22)
SHINE = HI("M70 53 Q84 42 100 41 Q116 42 130 53 Q116 47 100 46.5 Q84 47 70 53Z", .38)
CROWN = "M58 90 C51 46 78 31 100 31 C122 31 149 46 142 90 "        # the top of every fringe: over the head from ear to ear
FRONT_SHORT = P(CROWN + "C141 82 138 74 134 68 C132 73 129 76 125 77 C125 70 121 64 115 60 C113 64 109 67 104 68 C102 64 97 60 91 58 "
                "C90 64 86 70 79 76 C77 71 74 67 70 65 C65 72 61 82 58 90Z") + SHINE
FRONT_PART = P(CROWN + "C140 84 138 76 134 70 C131 76 127 80 122 82 C120 70 112 60 101 55 C92 62 84 72 78 82 C73 80 69 76 66 70 "
               "C62 76 60 84 59 92Z") + SHINE
FRONT_SWEPT = P(CROWN + "C140 82 137 72 133 66 C128 74 120 79 110 81 C114 74 115 66 113 59 C104 70 90 78 74 80 C71 75 68 70 66 66 "
                "C62 74 60 84 59 92Z") + SHINE
FRONT_BLUNT = P(CROWN + "C140 86 138 80 136 76 Q118 70 100 71 Q82 70 64 76 C62 80 60 86 59 92Z") + DL("M76 60 V73 M88 58 V71.5 M100 57 V71 M112 58 V71.5 M124 60 V73", 1.2) + SHINE
LOCKS = PAIR(P("M61 80 C57 102 58 126 60 152 C66 142 69 130 70 118 C71 104 71 94 71 84Z"))      # long strands in front of the ears

# Hats: a dome that sits on the crown, with the same shadow and highlight on every one.
CAP = "M60 60 C57 32 78 21 100 21 C122 21 143 32 140 60Z"
CAP_SHADE = SH("M118 23 C133 28 142 40 140 60 H123 C127 46 125 33 118 23Z") + HI("M67 51 C67 37 79 28 93 25.5 C84 31 77 39 75 51Z")
# A cape fastens in front of the collar: the part of a "back" drawing after "|||" is drawn over the clothes.
CLASP = P("M76 118 Q100 132 124 118 L127 125 Q100 141 73 125Z") + C(100, 131, 4.6, GOLD) + C(98.8, 129.8, 1.4, "#fff", NS)
# Shoes are drawn for the left foot and mirrored.
SHOE = "M72 266 C71 258 77 254 86 254 C95 254 100 258 99.5 266 L99.5 273 C99.5 276 97 277.5 94 277.5 L77 277.5 C73 277.5 72 276 72 273Z"
SOLE = "M72 271 H99.5 V274 C99.5 276.5 97 277.5 94 277.5 H77 C73.5 277.5 72 276.5 72 274Z"
SHOE_SHADE = SH("M90 254.5 C96 255 100 259 99.5 266 V271 H91Z") + HI("M76 262 C76 258 80 256.5 84 256.5 C80 258 78.5 260 78.5 263Z")
BOOT = lambda top: f"M75 {top} H97 L97.5 256 C99.5 259 100 262 99.5 266 L99.5 273 C99.5 276 97 277.5 94 277.5 L77 277.5 C73 277.5 72 276 72 273 L72 266 C72 262 73 259 75 256Z"
BOOT_SHADE = lambda top: SH(f"M90 {top} H97 L97.5 256 C99.5 259 100 262 99.5 266 V271 H90Z")
# Backgrounds end with the same soft light, floor and vignette, so the character always stands in a lit room.
SCENE = lambda inner: (inner + E(100, 128, 120, 140, "url(#glow)", 'opacity=".3"') + P("M0 256 Q100 244 200 256 V300 H0Z", SHADOW, 'opacity=".2"')
                       + R(0, 0, 200, 300, "url(#vignette)"))
FLAMES = lambda x, h, fill="@c", o=".85": P(f"M{x - 16} 304 C{x - 24} {304 - h * .45} {x - 5} {304 - h * .55} {x - 3} {304 - h} C{x + 3} {304 - h * .7} {x + 21} {304 - h * .5} {x + 16} 304Z", fill, f'opacity="{o}"')
FIRE = ((16, 132), (46, 96), (74, 66), (100, 80), (126, 66), (154, 96), (184, 132))      # a ring of flames: where and how tall
PET = lambda inner: inner                                                     # drawn in a 48 x 55 box with the ground at 55; `SPACE` puts it beside the feet
FACE = lambda x1, x2, y, r=2.4: C(x1, y, r, INK, NS) + C(x2, y, r, INK, NS) + C(x1 - r * .35, y - r * .4, r * .38, "#fff", NS) + C(x2 - r * .35, y - r * .4, r * .38, "#fff", NS)
CHEEKS = lambda x1, x2, y, r=3: E(x1, y, r, r * .62, "#ff7a8a", f'opacity=".5" {NS}') + E(x2, y, r, r * .62, "#ff7a8a", f'opacity=".5" {NS}')
GLYPH = lambda x, y, s, size: T(x + 3, y + 4, s, size, "@d", 'opacity=".55"') + T(x, y, s, size)

# slot -> style key -> (name, tier, drawing)
STYLES = {
    "background": {
        "plain": ("Plain", 0, SCENE(R(0, 0, 200, 300))),
        "fade": ("Fade", 0, SCENE(R(0, 0, 200, 300) + G(*[R(0, y, 200, 300 - y, "@l", 0, 'opacity=".24"') for y in (90, 130, 170, 210)]))),
        "stripes": ("Stripes", 0, SCENE(R(0, 0, 200, 300, "@l") + G(*[R(x, 0, 20, 300, "@c", 0, 'opacity=".7"') for x in range(0, 200, 40)]))),
        "dots": ("Polka", 0, SCENE(R(0, 0, 200, 300, "@l") + G(*[C(x + (20 if (y // 36) % 2 else 0), y, 7, "@c") for x in range(0, 220, 40) for y in range(14, 300, 36)]))),
        "graph": ("Graph paper", 1, SCENE(R(0, 0, 200, 300, "@l") + G(*[L(x, 0, x, 300, "@c", 1 if x % 40 else 1.8) for x in range(0, 201, 20)], *[L(0, y, 200, y, "@c", 1 if y % 40 else 1.8) for y in range(0, 301, 20)])
                                          )),
        "stars": ("Starfield", 1, SCENE(R(0, 0, 200, 300, "@d") + R(0, 150, 200, 150, "@c", 0, 'opacity=".35"') + C(158, 44, 17, "@l") + C(166, 38, 15, "@d")
                                        + G(*[STAR(x, y, 4 + (x * y) % 6) for x, y in [(30, 30), (118, 58), (88, 18), (40, 120), (170, 150), (20, 220), (150, 250), (64, 76), (58, 262), (182, 216), (14, 78), (176, 96)]])
                                        + G(*[C(x, y, 1.3, "@l") for x, y in [(52, 48), (140, 110), (24, 160), (184, 60), (120, 24), (76, 200), (160, 196), (10, 262)]]))),
        "sunset": ("Sunset", 2, SCENE(R(0, 0, 200, 300, "@c") + R(0, 0, 200, 90, "@d", 0, 'opacity=".4"') + R(0, 130, 200, 170, "@l", 0, 'opacity=".5"') + C(100, 178, 50, "#fff3b0", 'opacity=".9"')
                                      + C(100, 178, 64, "#fff3b0", 'opacity=".25"') + P("M0 236 Q50 204 100 226 T200 214 V300 H0Z", "@d", 'opacity=".75"') + P("M0 262 Q60 238 120 258 T200 250 V300 H0Z", "@d"))),
        "waves": ("Waves", 1, SCENE(R(0, 0, 200, 300, "@l") + C(160, 46, 20, "#fff", 'opacity=".7"')
                                    + G(*[P(f"M0 {y} Q25 {y - 14} 50 {y} T100 {y} T150 {y} T200 {y} V300 H0Z", "@c", 'opacity=".55"') for y in (176, 204, 232, 260)])
                                    + G(*[P(f"M{x} {y} q8 -7 16 0", "none", 'stroke="#fff" stroke-width="2" stroke-linecap="round" opacity=".7"') for x, y in [(20, 196), (130, 190), (70, 224), (160, 248), (30, 254)]]))),
        "checker": ("Checker", 0, SCENE(R(0, 0, 200, 300, "@l") + G(*[R(x, y, 25, 25, "@c") for x in range(0, 200, 25) for y in range(0, 300, 25) if (x // 25 + y // 25) % 2 == 0]))),
        "spotlight": ("Spotlight", 2, SCENE(R(0, 0, 200, 300, "@d") + POLY("74,0 126,0 196,262 4,262", "@l", 'opacity=".22"') + POLY("88,0 112,0 150,262 50,262", "@l", 'opacity=".2"')
                                            + E(100, 262, 96, 26, "@l", 'opacity=".5"') + E(100, 262, 60, 15, "#fff", 'opacity=".35"'))),
    },
    "aura": {
        "glow": ("Glow", 1, E(100, 166, 98, 138, "url(#glow)", 'opacity=".9"') + E(100, 166, 88, 128, "@c", 'opacity=".3"') + E(100, 166, 66, 104, "@l", 'opacity=".3"')),
        "sparkles": ("Sparkles", 1, G(STAR(34, 62, 11, "@c"), STAR(170, 92, 8, "@l"), STAR(26, 192, 7, "@l"), STAR(174, 204, 12, "@c"), STAR(46, 254, 8, "@c"), STAR(156, 30, 7, "@l"),
                                      STAR(22, 124, 5, "@c"), STAR(180, 150, 5, "@l"), STAR(150, 262, 6, "@l"), STAR(60, 24, 5, "@l"))),
        "ring": ("Halo ring", 1, E(100, 166, 84, 126, "none", 'stroke="@c" stroke-width="5" stroke-dasharray="2 11" stroke-linecap="round"')
                 + E(100, 166, 94, 136, "none", 'stroke="@l" stroke-width="2.5" stroke-dasharray="1 15" stroke-linecap="round" opacity=".8"')),
        "flames": ("Flames", 2, G(*[FLAMES(x, h) for x, h in FIRE], *[FLAMES(x, h * .55, "@l", ".9") for x, h in FIRE])),
        "hearts": ("Hearts", 1, G(*[HEART(x, y, s, "@c") + HI(f"M{x - 7 * s} {y - 4 * s} q{2 * s} -{4 * s} {5 * s} -{3 * s} q-{3 * s} {s} -{3 * s} {4 * s}Z", .6)
                                    for x, y, s in [(30, 92, 1.5), (170, 124, 1.2), (24, 204, 1.1), (174, 226, 1.6), (50, 34, 1.1), (154, 46, .8)]])),
        "orbit": ("Orbit", 2, E(100, 170, 94, 32, "none", 'stroke="@c" stroke-width="7" transform="rotate(-18 100 170)"') + E(100, 170, 94, 32, "none", 'stroke="@l" stroke-width="2.4" transform="rotate(-18 100 170)" opacity=".85"')
                  + C(184, 136, 9, "@l") + C(181, 133, 3, "#fff", 'opacity=".8"') + C(16, 200, 7, "@c") + STAR(150, 60, 6, "@l") + STAR(40, 110, 5, "@c")),
        "storm": ("Storm cloud", 2, G(P("M36 40 C22 40 20 22 36 20 C38 6 62 2 70 14 C80 2 108 2 114 16 C126 6 148 10 148 24 C166 22 172 42 156 44Z", "@d"),
                                      HI("M40 24 C42 14 56 10 64 16 C54 16 46 20 44 28Z", .3),
                                      P("M44 50 L56 50 L50 72 L60 72 L42 104 L47 80 L38 80Z", "@c"), P("M148 50 L160 50 L154 68 L164 68 L146 98 L151 76 L142 76Z", "@c"),
                                      *[L(x, 52, x - 3, 62, "@l", 2) for x in (76, 92, 108, 124)])),
        "petals": ("Petals", 1, G(*[P(f"M{x - 11} {y} Q{x} {y - 10} {x + 11} {y} Q{x} {y + 7} {x - 11} {y}Z", "@c" if i % 2 else "@l", f'transform="rotate({a} {x} {y})"')
                                    for i, (x, y, a) in enumerate([(36, 70, 30), (166, 100, -20), (26, 180, 60), (174, 190, 10), (54, 252, -40), (146, 38, 50), (20, 122, -30), (160, 250, 40), (62, 28, 10)])])),
    },
    "back": {
        "cape": ("Cape", 0, P("M70 120 Q100 112 130 120 C152 160 164 220 170 262 Q152 274 134 264 Q117 276 100 266 Q83 276 66 264 Q48 274 30 262 C36 220 48 160 70 120Z", "@d")
                 + P("M74 126 Q100 119 126 126 C144 162 154 214 158 252 Q100 262 42 252 C46 214 56 162 74 126Z") + SH("M126 126 C144 162 154 214 158 252 Q140 256 128 257 C132 214 132 170 126 126Z") + "|||" + CLASP),
        "short-cape": ("Short cape", 0, P("M70 120 Q100 112 130 120 C150 142 164 176 170 212 Q156 222 142 212 Q128 222 114 214 L86 214 Q72 222 58 212 Q44 222 30 212 C36 176 50 142 70 120Z")
                       + SH("M130 120 C150 142 164 176 170 212 Q156 222 144 213 C146 180 142 148 130 120Z") + "|||" + CLASP),
        "angel": ("Angel wings", 2, PAIR(P("M72 132 C50 96 14 84 -6 96 C-2 110 2 118 8 124 C0 128 -2 138 2 148 C8 150 12 152 16 152 C12 160 14 170 20 178 C28 176 34 174 38 170 C38 180 44 190 52 196 C60 184 70 164 74 150Z", "@l")
                                         + DL("M62 128 C44 108 22 100 6 104 M60 140 C44 128 24 126 10 134 M62 152 C48 146 32 150 22 160 M66 162 C56 160 46 168 42 176", 1.6, "@c")
                                         + SH("M74 150 C70 164 60 184 52 196 C46 192 42 186 40 178 C52 172 64 162 74 150Z", .12))),
        "bat": ("Bat wings", 2, PAIR(P("M72 132 C54 104 28 88 0 86 C8 100 10 112 8 124 C16 120 24 122 28 130 C26 142 26 152 30 162 C36 156 44 154 50 158 C50 170 54 182 60 190 C66 176 72 160 74 150Z")
                                     + DL("M72 132 C50 116 28 112 8 124 M72 134 C54 128 38 138 30 162 M73 138 C64 146 60 166 60 190", 1.8) + HI("M66 124 C50 104 28 94 8 90 C24 96 44 106 60 126Z", .22))),
        "butterfly": ("Butterfly wings", 2, PAIR(P("M74 142 C58 100 16 84 2 108 C-8 130 22 160 72 156Z") + P("M72 154 C42 152 18 170 26 194 C34 212 64 198 75 166Z", "@l")
                                                 + C(28, 116, 8, "@l") + C(48, 132, 5, "@l") + C(40, 182, 6, "@c") + SH("M74 142 C70 132 64 122 56 114 C62 128 64 142 62 156 L72 156Z", .14))),
        "backpack": ("Backpack", 0, R(40, 120, 120, 92, "@c", 24) + SH("M136 120 Q160 120 160 144 V188 Q160 212 136 212Z") + PAIR(R(30, 152, 18, 44, "@d", 8)) + HI("M46 136 Q48 126 58 126 Q52 130 51 144Z", .3)
                     + "|||" + PAIR(P("M80 117 C77 140 77 172 81 204 L88 204 C84 172 84 140 87 117Z", "@d")) + R(84, 150, 32, 6, "@d", 2) + R(96, 148.5, 8, 9, "@l", 2)),
        "jetpack": ("Jetpack", 3, PAIR(P("M34 196 Q44 240 54 196Z", FLAME) + P("M39 196 Q44 222 49 196Z", "#fff3b0", NS) + P("M32 132 C32 112 56 112 56 132 V190 Q44 198 32 190Z", "@d") + R(32, 144, 24, 9, "@c") + R(32, 172, 24, 6, "@c")
                                       + HI("M36 132 C36 122 42 118 46 118 C42 122 40 128 40 134 V184 H36Z", .3)) + R(52, 140, 96, 30, "@d", 6)),
        "shell": ("Shell", 1, E(100, 166, 72, 64, "@d") + E(100, 166, 60, 53, "@c") + DL("M100 114 V218 M44 146 L100 166 L156 146 M54 204 L100 166 L146 204", 2)
                  + SH("M100 113 C140 113 160 140 160 166 C160 192 140 219 100 219 C132 198 136 138 100 113Z")),
        "dragonwings": ("Dragon wings", 3, PAIR(P("M72 132 C48 92 20 78 -8 84 C4 96 6 110 2 124 C12 120 20 124 22 134 C20 146 22 156 28 166 C34 158 42 158 48 164 C48 174 52 186 60 194 C66 178 72 162 74 150Z")
                                                + P("M72 132 C48 92 20 78 -8 84 C16 86 42 102 64 134Z", "@d") + DL("M70 134 C48 118 24 114 2 124 M71 138 C54 134 36 144 28 166 M73 142 C64 150 60 170 60 194", 2)
                                                + P("M-8 84 l-6 -9 l11 3Z", CREAM))),
    },
    "bottom": {
        "jeans": ("Jeans", 0, HIPS + LEGS("long") + DL("M80 201 Q86 210 96 208 M120 201 Q114 210 104 208 M100 200 V212", 1.3) + DL("M77 252 H97 M103 252 H123", 1.2, "@l") + C(100, 195.5, 1.6, "@l", NS)),
        "shorts": ("Shorts", 0, HIPS + LEGS("short") + DL("M100 200 V212 M80 201 Q86 208 94 207 M120 201 Q114 208 106 207", 1.3)),
        "skirt": ("Skirt", 0, SKIRT("M72 192 H128 L141 236 Q100 248 59 236Z") + SH("M114 199 H128 L141 236 Q128 241 116 243Z") + DL("M84 200 L79 240 M100 200 V245 M116 200 L121 240", 1.2)),
        "track": ("Track pants", 0, HIPS + LEGS("long", cuff="@d") + R(74, 196, 6, 70, "@l", 0, f'{NS} clip-path="url(#k-legl)"') + R(120, 196, 6, 70, "@l", 0, f'{NS} clip-path="url(#k-legr)"')
                  + DL("M96 196 L94 204 M104 196 L106 204", 1.6, "@l")),
        "cargo": ("Cargo pants", 1, HIPS + LEGS("long") + R(74, 222, 16, 17, "@c", 3) + R(110, 222, 16, 17, "@c", 3) + P("M74 222 H90 V228 H74Z", "@d") + P("M110 222 H126 V228 H110Z", "@d")
                  + C(82, 225, 1.3, "@l", NS) + C(118, 225, 1.3, "@l", NS)),
        "leggings": ("Leggings", 0, HIPS + LEGS("ankle") + DL("M79 204 Q80 230 82 254 M121 204 Q120 230 118 254", 1.4, "@l")),
        "kilt": ("Kilt", 1, SKIRT("M72 192 H128 L136 234 Q100 242 64 234Z") + G(*[DL(f"M{x} 200 L{100 + (x - 100) * 1.22:.1f} 239", 1.4) for x in (80, 90, 100, 110, 120)]) + DL("M68 214 Q100 220 132 214 M66 226 Q100 233 134 226", 1.6, "@l")
                 + SH("M116 199 H128 L136 234 Q126 237 118 238Z") + P("M118 206 l5 2 l-1 12 l-5 -1Z", GOLD)),
        "bermuda": ("Bermudas", 0, HIPS + LEGS("knee", cuff="@d") + DL("M100 200 V212", 1.3)),
        "hakama": ("Hakama", 2, P("M72 192 H128 L144 264 H103 L100 222 L97 264 H56Z") + G(*[DL(f"M{x} 200 L{100 + (x - 100) * 1.6:.1f} 262", 1.4) for x in (80, 89, 111, 120)])
                   + SH("M116 199 H128 L144 264 H124Z") + P("M72 192 H128 V200 H72Z", "@d") + P("M93 196 h14 l-3 9 h-8Z", "@l")),
        "tutu": ("Tutu", 2, HIPS + P("M56 220 C52 208 72 200 100 200 C128 200 148 208 144 220 Q137 229 130 222 Q122 232 115 224 Q108 233 100 225 Q92 233 85 224 Q78 232 70 222 Q63 229 56 220Z", "@l")
                 + P("M62 212 C62 203 80 198 100 198 C120 198 138 203 138 212 Q131 219 124 213 Q116 221 108 214 Q100 221 92 214 Q84 221 76 213 Q69 219 62 212Z") + P("M72 192 H128 V199 H72Z", "@d")),
        "flares": ("Flares", 1, HIPS + LEGS("knee") + P("M76 240 L68 264 H99 L98 240Z") + P("M124 240 L132 264 H101 L102 240Z") + SH("M92 240 H98 L99 264 H90Z") + SH("M118 240 H124 L132 264 H120Z")
                   + DL("M100 200 V212", 1.3)),
        "greaves": ("Knight greaves", 2, HIPS + LEGS("long") + PAIR(P("M77 236 Q87 230 97 236 L96 258 H78Z", "@l") + C(87, 232, 6.5, "@l") + DL("M87 240 V257", 1.4) + SH("M91 234 Q95 235 97 236 L96 258 H91Z"))
                    + P("M72 192 H128 V199 H72Z", "@d") + C(100, 195.5, 2.4, "@l")),
    },
    "shoes": {
        "sneakers": ("Sneakers", 0, PAIR(P(SHOE) + SHOE_SHADE + P(SOLE, "@l") + P("M72 266 C73 261 78 259 86 259 C94 259 99 261 99.5 266", "none") + DL("M81 256.5 H91 M80 260 H92", 1.5, "@l"))),
        "boots": ("Boots", 0, PAIR(P(BOOT(240)) + BOOT_SHADE(240) + P(SOLE, "@d") + P("M75 240 H97 V246 H75Z", "@d") + HI("M77 250 V264 C77 260 78 252 80 250Z", .3))),
        "sandals": ("Sandals", 0, PAIR(P(SOLE, "@d") + P("M74 271 C74 264 79 262 86 262 C93 262 98 264 98 271", "none", 'stroke="@k" stroke-width="6.4"') + P("M74 271 C74 264 79 262 86 262 C93 262 98 264 98 271", "none", 'stroke="@c" stroke-width="3.6"')
                                       + C(86, 262, 2.6, "@l"))),
        "skates": ("Roller skates", 1, PAIR(P(BOOT(246)) + BOOT_SHADE(246) + P("M71 270 H100.5 V276 H71Z", "@d") + C(78, 280, 4.6, "@l") + C(93, 280, 4.6, "@l") + C(78, 280, 1.4, "@d", NS) + C(93, 280, 1.4, "@d", NS)
                                            + DL("M80 250 H92 M80 255 H92 M80 260 H92", 1.5, "@l"))),
        "slippers": ("Slippers", 0, PAIR(P(SHOE) + SHOE_SHADE + P("M75 262 C75 255 81 253 86 253 C91 253 97 255 97 262 C94 266 78 266 75 262Z", "@l") + C(86, 259.5, 3.4, "@d"))),
        "hightops": ("High-tops", 1, PAIR(P(BOOT(246)) + BOOT_SHADE(246) + P(SOLE, "@l") + C(81, 255, 4.2, "@l") + STAR(81, 255, 3, "@d", NS) + DL("M86 249 H95 M87 254 H95", 1.5, "@l")
                                          + P("M72 266 C74 262 80 262 86 265", "none"))),
        "loafers": ("Loafers", 0, PAIR(P(SHOE) + SHOE_SHADE + P(SOLE, "@d") + P("M77 263 C77 258 82 257 86 257 C90 257 95 258 95 263 C92 266 80 266 77 263Z", "@d") + R(82, 261, 8, 3, GOLD, 1, NS))),
        "rocket": ("Rocket boots", 3, PAIR(P("M78 277 Q86 302 94 277Z", FLAME) + P("M82 277 Q86 292 90 277Z", "#fff3b0", NS) + P(BOOT(240)) + BOOT_SHADE(240) + P("M75 240 H97 V247 H75Z", "@d")
                                           + P("M70 270 H101 V277 H70Z", "@d") + C(86, 258, 3.6, "@l") + P("M72 266 l-6 8 h7Z", "@d"))),
        "glass": ("Glass slippers", 3, PAIR(P(SHOE, "#d8f0ff", 'fill-opacity=".8"') + P(SOLE, "@c", 'fill-opacity=".8"') + HI("M76 263 C76 258 80 256.5 85 256.5 C81 258 79 260 79 264Z", .9)
                                            + STAR(92, 259, 4.5, "#ffffff", NS) + STAR(78, 268, 2.4, "#ffffff", NS))),
        "cowboy": ("Cowboy boots", 1, PAIR(P(BOOT(234)) + BOOT_SHADE(234) + P(SOLE, "@d") + P("M75 234 Q86 242 97 234 V240 Q86 248 75 240Z", "@d") + DL("M79 250 Q86 258 93 250 M81 256 Q86 261 91 256", 1.4, "@l")
                                           + STAR(70.5, 271, 3.6, GOLD))),
        "platform": ("Platforms", 2, PAIR(P("M73 262 C73 256 78 253 86 253 C94 253 99 256 99 262 V268 H73Z") + SH("M91 254 C96 255 99 258 99 262 V268 H91Z") + P("M71 266 H101 V275 C101 277 99.5 278.5 97 278.5 H75 C72.5 278.5 71 277 71 275Z", "@d")
                                          + DL("M71 271.5 H101", 1.4, "@l") + R(81, 257, 10, 4, "@l", 2))),
    },
    "top": {
        "tee": ("T-shirt", 0, ARMS("sleeve") + TORSO() + NECK),
        "longsleeve": ("Long sleeve", 0, ARMS("wrist", cuff="@d") + TORSO() + NECK),
        "hoodie": ("Hoodie", 1, ARMS("wrist", cuff="@d") + TORSO() + P("M78 119 C82 108 118 108 122 119 C114 130 86 130 78 119Z", "@d") + DL("M94 126 L93 148 M106 126 L107 148", 1.8, "@l") + C(93, 149, 1.6, "@l", NS) + C(107, 149, 1.6, "@l", NS)
                   + P("M83 172 H117 L114 194 H86Z", "@c") + SH("M83 172 H117 L114 194 H86Z", .14) + TORSO_CLIP(R(60, 198, 80, 9, "@d", 0, NS))),
        "jumper": ("Striped jumper", 0, ARMS("wrist", cuff="@d") + P("@TORSO") + TORSO_CLIP(G(*[R(60, y, 80, 8, "@l", 0, NS) for y in (134, 152, 170, 188)])) + TORSO_SHADE + P("@TORSO", "none") + NECK),
        "labcoat": ("Lab coat", 1, P("M70 160 L64 236 Q100 244 136 236 L130 160Z") + SH("M116 160 H130 L136 236 Q126 239 118 240Z") + ARMS("wrist") + TORSO() + P("M88 116 L100 146 L112 116 L106 115 L100 128 L94 115Z", "#9cc1ff", NS)
                    + P("M88 116 L84 136 L100 148Z") + P("M112 116 L116 136 L100 148Z") + DL("M100 148 V240", 1.6) + BUTTONS(105, (164, 182, 200)) + R(108, 206, 15, 14, "@c", 2) + R(76, 150, 12, 3, "@d", 1, NS)
                    + L(79, 146, 79, 153, "#e5484d", 2)),
        "suit": ("Suit", 1, ARMS("wrist") + TORSO() + VNECK() + P("M97.5 122 H102.5 L105 148 L100 156 L95 148Z", "@l") + P("M97 118 H103 L102 124 H98Z", "@l") + P("M89 116 L100 152 L82 140Z", "@d") + P("M111 116 L100 152 L118 140Z", "@d")
                 + BUTTONS(100, (166, 180)) + DL("M100 152 V206", 1.4) + P("M78 148 h10 v3 h-10Z", CREAM, NS) + ARMS("wrist", "none", cuff=CREAM)),
        "armour": ("Armour", 2, ARMS("wrist", cuff="@d") + TORSO() + TORSO_CLIP(R(60, 184, 80, 10, "@d") + DL("M60 172 H140", 1.6)) + DL("M100 124 V184", 2) + P("M100 138 l9 6 v10 q0 8 -9 12 q-9 -4 -9 -12 v-10Z", "@l") + P("M88 116 Q100 128 112 116 L110 124 Q100 132 90 124Z", "@d")
                   + PAIR(P("M56 136 C54 122 64 114 78 118 C84 122 84 134 78 140 C70 144 60 142 56 136Z", "@l") + SH("M70 140 C78 138 84 130 80 120 C84 124 84 134 78 140Z"))),
        "dress": ("Dress", 1, ARMS("cap") + P("M78 164 H122 L146 244 Q100 256 54 244Z") + SH("M112 164 H122 L146 244 Q132 249 120 250Z") + DL("M84 200 L76 248 M100 200 V252 M116 200 L124 248", 1.2) + TORSO() + TORSO_CLIP(R(60, 160, 80, 9, "@d")) + NECK
                  + P("M94 160 q6 -5 12 0 q-6 6 -12 0Z", "@l")),
        "tank": ("Tank top", 0, TORSO_CLIP(R(60, 128, 80, 90) + SH("M117 100 C125 140 123 180 115 215 H150 V100Z")) + PAIR(P("M85 116.5 C83 121 82 126 82 131 H90 C90 126 91 121 92.5 116.5Z")) + TORSO_CLIP(P("M60 128 H90 Q100 138 110 128 H140", "none"))
                 + P("@TORSO", "none", 'clip-path="url(#k-below)"')),
        "hooped": ("Hooped tee", 0, ARMS("sleeve") + P("@TORSO") + TORSO_CLIP(G(*[R(60, y, 80, 9, "@d", 0, NS) for y in (132, 151, 170, 189)])) + TORSO_SHADE + P("@TORSO", "none") + NECK),
        "puffer": ("Puffer jacket", 1, ARMS("wrist", cuff="@d") + '<path d="@ARML" fill="none" stroke="@c" stroke-width="5" clip-path="url(#k-wrist)"/><path d="@ARMR" fill="none" stroke="@c" stroke-width="5" clip-path="url(#k-wrist)"/>'
                   + P("@TORSO", "@c", 'stroke-width="6"') + TORSO() + TORSO_CLIP(DL("M60 142 Q100 148 140 142 M60 162 Q100 168 140 162 M60 182 Q100 188 140 182", 2.2)) + DL("M100 122 V206", 2, "@l")
                   + P("M82 118 C86 110 114 110 118 118 C112 126 88 126 82 118Z", "@d")),
        "poncho": ("Poncho", 2, P("M100 112 C120 112 156 178 160 208 Q100 220 40 208 C44 178 80 112 100 112Z") + SH("M118 122 C138 146 156 186 160 208 Q140 212 124 214 C128 180 126 150 118 122Z")
                   + DL("M52 186 Q100 198 148 186", 5, "@l") + DL("M58 172 Q100 182 142 172", 2, "@d") + G(*[L(x, 211 - abs(x - 100) * .04, x, 220 - abs(x - 100) * .04, "@d", 2.4) for x in range(48, 156, 9)]) + NECK),
        # Statement pieces: costumes and couture, cut from the same body outlines so they fit both builds.
        "kimono": ("Kimono", 2, P("M72 196 L66 256 Q100 264 134 256 L128 196Z") + SH("M116 196 H128 L134 256 Q126 259 118 260Z")
                   + PAIR(P("M68 128 C54 134 46 162 42 200 L70 205 C72 182 72 160 77 140Z") + SH("M56 196 L70 205 C72 182 72 160 77 140 C68 156 60 176 56 196Z", .14))
                   + TORSO() + P("M86 116 L106 172 L98 172 L82 124Z", "@l") + P("M114 116 L94 160 L102 160 L118 124Z", "@l") + TORSO_CLIP(R(60, 160, 80, 18, "@d")) + R(94, 157, 12, 24, "@l", 3)),
        "royalrobe": ("Royal robe", 3, P("M70 156 L54 256 Q100 270 146 256 L130 156Z", "@d") + ARMS("wrist", cuff=CREAM) + TORSO() + P("M93 124 H107 V262 Q100 264 93 262Z", CREAM)
                      + G(*[C(100, y, 1.7, "#1b1830", NS) for y in range(140, 258, 14)]) + P("M76 119 C86 137 114 137 124 119 C116 111 84 111 76 119Z", CREAM) + G(*[C(x, y, 1.5, "#1b1830", NS) for x, y in ((86, 124), (100, 128), (114, 124))])
                      + P("M70 250 Q100 262 130 250", "none", f'stroke="{GOLD}" stroke-width="3"')),
        "pirate": ("Pirate coat", 2, P("M70 168 L60 240 L93 240 L100 198 L107 240 L140 240 L130 168Z") + SH("M116 168 H130 L140 240 H122Z") + ARMS("wrist", cuff="@l") + TORSO() + VNECK()
                   + P("M89 116 L100 150 L80 142Z", "@d") + P("M111 116 L100 150 L120 142Z", "@d") + TORSO_CLIP(R(60, 180, 80, 9, "#c0392b")) + R(95, 178.5, 10, 12, GOLD, 2)
                   + G(*[C(x, y, 2.2, GOLD) for x in (88, 112) for y in (156, 170)])),
        "astronaut": ("Space suit", 3, ARMS("wrist", cuff="@d") + '<path d="@ARML" fill="none" stroke="@c" stroke-width="4" clip-path="url(#k-wrist)"/><path d="@ARMR" fill="none" stroke="@c" stroke-width="4" clip-path="url(#k-wrist)"/>'
                      + P("@TORSO", "@c", 'stroke-width="5"') + TORSO() + R(84, 140, 32, 22, "@d", 5) + C(92, 151, 3, "#ff5f5f") + C(100, 151, 3, "#ffd24d") + C(108, 151, 3, "#3ddc97")
                      + P("M76 120 C84 110 116 110 124 120 C116 130 84 130 76 120Z", STEEL) + TORSO_CLIP(R(60, 186, 80, 9, "@d")) + P("M120 170 h10 v8 h-10Z", "#e5484d")),
        "hero": ("Hero suit", 2, ARMS("wrist", cuff="@d") + TORSO() + P("M100 132 L118 147 L100 170 L82 147Z", "@l") + P("M100 140 L108 147 L100 160 L92 147Z", "@d") + TORSO_CLIP(R(60, 184, 80, 9, GOLD)) + R(95, 183, 10, 11, "@l", 2) + NECK),
        "sequin": ("Sequin jacket", 2, ARMS("wrist") + TORSO() + TORSO_CLIP(G(*[C(x + (6 if (y // 10) % 2 else 0), y, 1.9, "@l", f'opacity=".9" {NS}') for x in range(64, 140, 12) for y in range(124, 206, 10)]))
                   + G(*[STAR(x, y, 4, "#fff", NS) for x, y in [(80, 138), (118, 160), (88, 186)]]) + VNECK("@d") + ARMS("wrist", "none", cuff="@l")),
        "leather": ("Leather jacket", 1, ARMS("wrist", cuff="@d") + TORSO() + P("M88 116 L100 136 L112 116 L109 115 L100 126 L91 115Z", CREAM, NS) + P("M88 116 L80 138 L99 146Z", "@d") + P("M112 116 L120 138 L103 150Z", "@d")
                    + L(100, 146, 106, 204, STEEL, 2) + TORSO_CLIP(R(60, 194, 80, 12, "@d")) + R(84, 172, 12, 2.5, STEEL, 1, NS) + C(82, 150, 1.8, STEEL, NS) + C(118, 152, 1.8, STEEL, NS) + HI("M70 126 C74 122 80 120 84 120 C78 124 74 130 73 138Z", .5)),
        "tuxedo": ("Tailcoat", 2, P("M76 186 L68 250 L98 206Z") + P("M124 186 L132 250 L102 206Z") + SH("M124 186 L132 250 L114 224Z") + ARMS("wrist", cuff=CREAM) + TORSO() + P("M87 116 L100 168 L113 116Z", CREAM)
                   + P("M100 128 L91 122 V134Z", "#15131c") + P("M100 128 L109 122 V134Z", "#15131c") + C(100, 128, 2.2, "#15131c", NS) + BUTTONS(100, (144, 155), "#15131c", 1.7)
                   + P("M87 116 L100 168 L80 146Z", "@d") + P("M113 116 L100 168 L120 146Z", "@d")),
        "ballgown": ("Ball gown", 3, P("M78 162 C58 190 42 232 34 266 Q100 286 166 266 C158 232 142 190 122 162Z") + SH("M112 162 H122 C142 190 158 232 166 266 Q146 273 128 276 C130 236 124 196 112 162Z")
                     + DL("M52 240 Q100 258 148 240", 3, "@l") + DL("M40 262 Q100 280 160 262", 3, "@l") + P("M60 214 Q72 222 78 214 Q86 224 92 216", "none", 'stroke="@l" stroke-width="2"') + TORSO()
                     + PAIR(P("M58 134 C58 122 70 116 80 120 C84 126 82 136 76 140 C68 142 60 140 58 134Z", "@l")) + TORSO_CLIP(R(60, 157, 80, 9, "@d")) + G(*[C(x, 161.5, 1.7, "#fff", NS) for x in (84, 92, 100, 108, 116)]) + NECK),
        "ninja": ("Ninja gi", 2, ARMS("wrist", cuff="@d") + TORSO() + P("M86 116 L108 172 L100 172 L82 124Z", "@d") + P("M114 116 L94 156 L101 158 L118 124Z", "@d") + TORSO_CLIP(R(60, 166, 80, 11, "@l")) + P("M106 168 h8 l3 24 l-6 -4 l-5 5Z", "@l")
                  + P("M88 116 Q100 126 112 116 L110 115 Q100 121 90 115Z", "@d")),
    },
    "face": {
        "round": ("Round glasses", 0, PAIR(C(86, 85, 11.5, "#fff", 'fill-opacity=".2" stroke="@k" stroke-width="3.8"') + C(86, 85, 11.5, "none", 'stroke="@c" stroke-width="2"') + HI("M79 80 q3 -5 8 -5 q-4 2 -5 6Z", .8))
                  + P("M97 83 Q100 80 103 83", "none", 'stroke="@c" stroke-width="2.6"')),
        "square": ("Square glasses", 0, PAIR(R(74, 75, 24, 20, "#fff", 5, 'fill-opacity=".2" stroke="@k" stroke-width="3.8"') + R(74, 75, 24, 20, "none", 5, 'stroke="@c" stroke-width="2"') + HI("M78 80 l5 -2 l-3 6Z", .8))
                   + P("M98 83 Q100 81 102 83", "none", 'stroke="@c" stroke-width="2.6"')),
        "shades": ("Sunglasses", 1, P("M72 76 H99 Q100 78 101 76 H128 L127 86 C125 96 108 97 104 88 L102 83 H98 L96 88 C92 97 75 96 73 86Z") + PAIR(HI("M77 79 H88 L80 88 C78 86 77 82 77 79Z", .3))),
        "monocle": ("Monocle", 1, C(114, 85, 12, "#fff", 'fill-opacity=".2" stroke="@k" stroke-width="4.8"') + C(114, 85, 12, "none", 'stroke="@c" stroke-width="2.8"') + HI("M107 80 q3 -5 8 -5 q-4 2 -5 6Z", .8)
                    + P("M124 92 C132 100 132 112 126 122", "none", 'stroke="@c" stroke-width="1.6" stroke-dasharray="1 3"')),
        "moustache": ("Moustache", 0, P("M100 97 C94 92 86 93 82 99 C80 102 78 102 76 100 C78 106 86 107 92 104 C96 103 99 101 100 99 C101 101 104 103 108 104 C114 107 122 106 124 100 C122 102 120 102 118 99 C114 93 106 92 100 97Z")),
        "eyepatch": ("Eyepatch", 1, P("M62 66 L138 78", "none", 'stroke="@k" stroke-width="4.4"') + P("M62 66 L138 78", "none", 'stroke="@c" stroke-width="2.4"') + P("M74 78 C74 70 98 70 98 78 C100 92 92 98 86 98 C80 98 72 92 74 78Z") + HI("M78 78 q2 -4 8 -4 q-4 2 -5 6Z", .25)),
        "mask": ("Face mask", 0, P("M64 88 L72 92 M136 88 L128 92", "none", 'stroke="@d" stroke-width="2"') + P("M70 91 Q100 82 130 91 L129 101 C125 111 112 116 100 116 C88 116 75 111 71 101Z") + DL("M76 98 Q100 92 124 98 M80 106 Q100 101 120 106", 1.3)
                 + SH("M112 87 Q122 88 130 91 L129 101 C126 108 120 112 112 114Z")),
        "freckles": ("Freckles", 0, G(*[C(x, y, 1.5, "@d", f'{NS} opacity=".8"') for x, y in [(72, 94), (78, 97), (74, 100), (81, 93), (128, 94), (122, 97), (126, 100), (119, 93), (97, 92), (103, 92)]])),
        "blush": ("Blush", 0, PAIR(E(76, 97, 9, 5.5, "@c", f'opacity=".6" {NS}') + DL("M71 99 l3 -5 M75.5 99.5 l3 -5 M80 99 l3 -5", 1.3, "@d"))),
        "glasses3d": ("3D glasses", 2, P("M70 74 H130 V90 Q130 97 122 97 H108 Q102 97 101 90 H99 Q98 97 92 97 H78 Q70 97 70 90Z", CREAM) + R(75, 78, 20, 14, "#ff4d5e", 3) + R(105, 78, 20, 14, "#35c8f0", 3)
                      + HI("M77 80 h6 l-5 8Z", .5) + HI("M107 80 h6 l-5 8Z", .5) + P("M70 80 l-6 -2 M130 80 l6 -2", "none") + P("M70 74 H130 V77 H70Z", "@c")),
        "paint": ("Face paint", 1, PAIR(P("M68 96 l12 -3 l1 3.4 l-12 3Z") + P("M70 102.5 l10 -2.5 l1 3.4 l-10 2.5Z", "@l")) + P("M96 66 L100 60 L104 66 L100 72Z", "@c")),
        "bandage": ("Bandage", 0, AT(0, 0, R(90, 89, 20, 8, "#f1d4a8", 3, 'transform="rotate(-14 100 93)"') + R(96, 89.5, 8, 7, "@c", 1, f'transform="rotate(-14 100 93)" {NS}') + G(*[C(x, 93 - (x - 100) * .25, .8, "#b98d5a", NS) for x in (92.5, 107.5)]))),
    },
    "hair": {
        "short": ("Short hair", 0, HAIR(BACK, FRONT_SHORT)),
        "long": ("Long hair", 0, HAIR(P("M58 90 C51 46 78 31 100 31 C122 31 149 46 142 90 C145 112 151 140 145 160 Q128 168 112 162 Q100 170 88 162 Q72 168 55 160 C49 140 55 112 57 88Z")
                                      + SH("M58 90 C51 46 78 31 100 31 C122 31 149 46 142 90 C145 112 151 140 145 160 Q128 168 112 162 Q100 170 88 162 Q72 168 55 160 C49 140 55 112 57 88Z", .22), FRONT_PART + LOCKS)),
        "bun": ("Bun", 0, HAIR(BACK, FRONT_PART, C(100, 25, 15) + P("M90 22 Q100 14 110 22", "none", 'stroke="@d" stroke-width="1.6"') + HI("M90 17 q5 -5 11 -4 q-6 2 -8 6Z", .35) + P("M88 36 Q100 42 112 36 L112 40 Q100 46 88 40Z", "@l"))),
        "spiky": ("Spiky hair", 1, HAIR(BACK, P(CROWN + "C140 82 138 74 135 68 L129 79 L124 62 L116 71 L109 57 L101 67 L93 57 L86 71 L78 62 L73 79 L66 68 C62 74 60 84 59 92Z") + SHINE,
                                     P("M60 64 L38 50 L62 46 L52 22 L78 34 L82 6 L99 28 L114 4 L120 32 L146 18 L140 46 L164 48 L141 66Z") + SH("M120 32 L146 18 L140 46 L164 48 L141 66 L120 60Z", .16))),
        "mohawk": ("Mohawk", 1, HAIR("", P("M65 80 C63 58 76 46 100 46 C124 46 137 58 135 80 C128 62 116 54 100 54 C84 54 72 62 65 80Z", "@c", f'opacity=".35" {NS}') + P("M91 43 C93 52 96 58 100 62 C104 58 107 52 109 43Z"),
                                      P("M89 46 C84 30 88 14 98 4 C100 10 104 12 108 8 C114 20 116 34 111 46Z") + SH("M104 10 C106 10 107 9 108 8 C114 20 116 34 111 46 H102 C106 34 106 22 104 10Z") + HI("M92 40 C89 28 92 18 97 11 C95 20 95 30 97 40Z", .3))),
        "afro": ("Afro", 1, HAIR(G(*[C(x, y, 17) for x, y in [(56, 74), (144, 74), (58, 94), (142, 94)]]),
                                  P("M67 84 C64 62 76 48 100 48 C124 48 136 62 133 84 C127 68 116 60 100 60 C84 60 73 68 67 84Z"),
                                  G(*[C(100 + 44 * math.cos(a / 10), 62 + 36 * math.sin(a / 10), 18) for a in range(-31, 1, 4)]) + C(100, 56, 38, "@c", NS)
                                  + HI("M70 44 C76 30 90 22 104 22 C90 26 80 34 76 46Z", .22))),
        "bob": ("Bob", 0, HAIR(P("M58 90 C51 46 78 31 100 31 C122 31 149 46 142 90 L146 114 Q138 124 128 120 L72 120 Q62 124 54 114Z") + SH("M58 90 C51 46 78 31 100 31 C122 31 149 46 142 90 L146 114 Q138 124 128 120 L72 120 Q62 124 54 114Z", .22),
                                FRONT_BLUNT + PAIR(P("M61 78 C58 92 57 106 56 118 C62 120 68 118 71 112 C72 100 71 90 71 84Z")))),
        "ponytail": ("Ponytail", 0, HAIR(P("M126 48 C164 44 176 96 156 150 C150 138 148 122 150 108 C146 88 138 72 128 66Z") + SH("M150 60 C168 84 170 118 156 150 C150 138 148 122 150 108 C154 92 154 76 150 60Z") + BACK + R(122, 50, 12, 9, "@l", 4, 'transform="rotate(30 128 54)"'),
                                         FRONT_SWEPT)),
        "pigtails": ("Pigtails", 0, HAIR(PAIR(P("M56 78 C36 82 30 112 42 140 C46 132 52 130 56 134 C62 118 64 96 62 82Z") + SH("M48 84 C40 100 40 122 42 140 C46 132 52 130 56 134 C50 118 48 100 48 84Z", .14) + C(59, 80, 5.5, "@l")) + BACK, FRONT_PART)),
        "curly": ("Curly hair", 0, HAIR(G(*[C(x, y, 13) for x, y in [(60, 78), (140, 78), (58, 98), (142, 98), (62, 116), (138, 116)]]),
                                        G(*[C(x, y, 10) for x, y in [(70, 62), (84, 54), (100, 51), (116, 54), (130, 62)]]) + G(*[HI(f"M{x - 5} {y - 3} q3 -5 8 -4 q-4 1 -5 5Z", .3) for x, y in [(84, 54), (100, 51), (116, 54)]]),
                                        G(*[C(x, y, 14) for x, y in [(66, 58), (80, 44), (100, 38), (120, 44), (134, 58)]]) + C(100, 60, 30, "@c", NS))),
        "buzz": ("Buzz cut", 0, HAIR("", P("M63 82 C60 56 76 42 100 42 C124 42 140 56 137 82 C131 64 118 56 100 56 C82 56 69 64 63 82Z", "@c", 'opacity=".75"'))),
        "fringe": ("Fringe", 0, HAIR(BACK, FRONT_BLUNT + PAIR(P("M61 78 C59 88 59 98 61 106 C66 104 70 98 71 92 V84Z")))),
    },
    "hat": {
        "cap": ("Cap", 0, P(CAP) + CAP_SHADE + DL("M100 21 V54 M80 25 Q76 40 77 56 M120 25 Q124 40 123 56", 1.2) + C(100, 21, 3.2, "@d") + P("M62 56 Q100 48 138 56 C147 61 145 71 135 71 Q100 61 65 71 C55 71 53 61 62 56Z", "@d")
                + HI("M68 60 Q84 55 100 54.5 Q84 57 70 63Z", .3)),
        "beanie": ("Beanie", 0, P(CAP) + CAP_SHADE + DL("M84 25 Q80 38 81 48 M100 22 V46 M116 25 Q120 38 119 48", 1.3) + P("M57 50 Q100 42 143 50 L143 63 Q100 55 57 63Z", "@d") + DL("M70 49 V60 M85 47 V58 M100 46 V57 M115 47 V58 M130 49 V60", 1.3, "@c")
                   + C(100, 16, 10, "@l") + SH("M104 7 C112 10 112 22 104 25 C108 20 108 12 104 7Z", .2)),
        "wizard": ("Wizard hat", 2, E(100, 58, 54, 10, "@d") + P("M70 57 Q100 64 130 57 L109 14 C107 7 112 3 119 2 C110 -2 99 1 96 10Z") + SH("M109 14 L130 57 Q120 60 110 61 C113 44 111 26 104 12Z")
                   + P("M74 49 Q100 56 126 49 L130 57 Q100 64 70 57Z", "@l") + R(95, 49.5, 10, 10, GOLD, 2) + STAR(101, 30, 6, "@l", NS) + STAR(91, 40, 3, "@l", NS)),
        "crown": ("Crown", 2, P("M66 58 L61 30 L80 44 L100 20 L120 44 L139 30 L134 58 Q100 51 66 58Z") + SH("M120 44 L139 30 L134 58 Q124 55 114 54Z") + P("M65 50 Q100 43 135 50 L134 58 Q100 51 66 58Z", "@d")
                  + C(61, 29, 4.2, "@l") + C(100, 19, 4.8, "@l") + C(139, 29, 4.2, "@l") + P("M100 46 l4 4.5 l-4 4.5 l-4 -4.5Z", "#e5484d") + C(82, 52, 2.2, "#35c8f0") + C(118, 52, 2.2, "#35c8f0")
                  + HI("M68 40 L66 34 L76 42 L74 48Z", .4)),
        "tophat": ("Top hat", 1, E(100, 57, 55, 9.5) + P("M74 55 L71 12 Q100 5 129 12 L126 55 Q100 61 74 55Z") + SH("M112 8 Q122 9 129 12 L126 55 Q118 57 110 58Z") + P("M73 41 Q100 47 127 41 L126 55 Q100 61 74 55Z", "@d")
                   + HI("M77 16 Q81 14 85 13.5 L86 38 Q82 38 79 37Z", .3)),
        "halo": ("Halo", 2, E(100, 21, 31, 8.5, "none", 'stroke="@k" stroke-width="9"') + E(100, 21, 31, 8.5, "none", 'stroke="@c" stroke-width="5.6"') + P("M72 18 Q100 8 128 18", "none", 'stroke="@l" stroke-width="2"')
                 + STAR(138, 8, 5, "@l", NS)),
        "party": ("Party hat", 0, P("M79 54 L100 5 L121 54 Q100 60 79 54Z") + SH("M100 5 L121 54 Q112 57 104 57 C106 40 104 22 100 5Z") + DL("M90 30 L107 22 M84 44 L114 36", 3, "@l") + C(100, 5, 6.5, "@l")
                  + P("M77 52 Q100 59 123 52 L124 57 Q100 64 76 57Z", "@d")),
        "gradcap": ("Graduation cap", 1, P("M75 44 L75 60 Q100 70 125 60 L125 44 L100 55Z", "@d") + POLY("100,19 155,37 100,55 45,37") + SH("M100 55 L155 37 L100 46Z") + C(100, 37, 3, "@l")
                    + P("M100 37 Q130 38 147 42 V62", "none", 'stroke="@l" stroke-width="2"') + P("M143 60 h8 l2 13 h-12Z", "@l")),
        "chef": ("Chef hat", 0, P("M77 52 L75 40 C60 38 58 18 76 16 C80 2 104 0 110 12 C126 4 144 18 134 36 C132 40 128 41 125 41 L123 52 Q100 47 77 52Z") + SH("M110 12 C126 4 144 18 134 36 C132 40 128 41 125 41 L123 52 Q116 50 110 49 C118 38 118 24 110 12Z", .12)
                 + DL("M88 26 V42 M100 22 V42 M112 26 V42", 1.3) + P("M74 49 Q100 43 126 49 L126 61 Q100 55 74 61Z", "@d")),
        "cowboy": ("Cowboy hat", 1, P("M38 54 C50 70 150 70 162 54 C152 47 134 50 128 53 L72 53 C66 50 48 47 38 54Z", "@d") + P("M72 56 C69 34 78 23 90 28 Q100 35 110 28 C122 23 131 34 128 56 Q100 62 72 56Z")
                   + SH("M110 28 C122 23 131 34 128 56 Q120 58 112 59 C116 48 116 36 110 28Z") + P("M72 47 Q100 53 128 47 L128 56 Q100 62 72 56Z", "@l") + STAR(100, 54, 4, GOLD)),
        "helmet": ("Helmet", 1, P("M58 66 C54 34 76 20 100 20 C124 20 146 34 142 66Z") + SH("M120 23 C136 30 145 44 142 66 H124 C128 50 127 34 120 23Z") + P("M93 20.5 Q100 19.5 107 20.5 L109 66 H91Z", "@l")
                   + P("M56 60 H144 V67 Q144 70 141 70 H59 Q56 70 56 67Z", "@d") + HI("M66 54 C66 40 76 30 88 26 C80 32 74 42 74 54Z")),
        "headphones": ("Headphones", 1, P("M60 78 C54 16 146 16 140 78", "none", 'stroke="@k" stroke-width="8.6"') + P("M60 78 C54 16 146 16 140 78", "none", 'stroke="@d" stroke-width="5.2"')
                       + PAIR(R(50, 68, 16, 32, "@c", 7) + R(47, 74, 6, 20, "@d", 3) + HI("M55 72 q3 -2 6 -1 v10 h-6Z", .3))),
        "bow": ("Hair bow", 0, PAIR(P("M100 40 C88 26 70 24 68 36 C66 50 84 54 100 44Z") + SH("M100 44 C90 50 78 52 72 46 C82 48 92 46 100 42Z") + P("M97 46 L88 62 L98 56Z", "@d")) + R(94, 35, 12, 13, "@d", 4)),
        "flowers": ("Flower crown", 1, P("M62 60 Q100 40 138 60", "none", 'stroke="#3e8e5a" stroke-width="3"') + G(*[P(f"M{x} {y} q-4 -9 -11 -6 q4 7 11 6Z", "#5db075") for x, y in [(77, 56), (123, 50)]])
                    + G(*[G(*[C(x + 5.5 * math.cos(a), y + 5.5 * math.sin(a), 4.2, "@c" if i % 2 else "@l") for a in (0.3, 1.56, 2.8, 4.1, 5.3)]) + C(x, y, 3.2, "#ffd24d")
                          for i, (x, y) in enumerate([(66, 60), (82, 48), (100, 44), (118, 48), (134, 60)])])),
        "catears": ("Cat ears", 1, PAIR(P("M64 54 C62 40 64 26 70 18 C80 24 90 34 94 44Z") + P("M70 46 C69 38 70 31 73 27 C79 32 84 37 87 43Z", "@l") + SH("M82 30 C86 34 91 39 94 44 L86 47 C86 41 85 35 82 30Z", .14))),
        "tiara": ("Tiara", 2, P("M74 54 L80 40 L89 47 L100 28 L111 47 L120 40 L126 54 Q100 46 74 54Z") + P("M100 34 l4.5 5 l-4.5 6 l-4.5 -6Z", "@l") + C(84, 47, 2.4, "@l") + C(116, 47, 2.4, "@l") + STAR(100, 26, 3.6, "#fff", NS)
                  + P("M74 54 Q100 46 126 54", "none")),
        "tricorn": ("Tricorn", 2, P("M70 48 C72 24 128 24 130 48Z", "@d") + P("M42 54 C58 30 80 24 100 32 C120 24 142 30 158 54 C138 45 118 45 100 50 C82 45 62 45 42 54Z") + SH("M100 32 C120 24 142 30 158 54 C140 46 122 45 106 48Z", .16)
                    + P("M46 51 C62 36 82 31 100 37 C118 31 138 36 154 51", "none", f'stroke="{GOLD}" stroke-width="2.4"') + P("M118 30 C124 12 138 6 150 10 C140 14 134 22 132 34Z", CREAM)),
        "viking": ("Viking helmet", 2, PAIR(P("M66 50 C46 44 40 26 46 8 C52 26 60 36 74 40Z", "#f4e8d4") + SH("M66 50 C56 46 50 40 46 30 C54 40 62 42 70 44Z", .16)) + P("M62 62 C60 30 78 24 100 24 C122 24 140 30 138 62Z")
                   + SH("M118 26 C132 30 140 40 138 62 H122 C126 48 125 36 118 26Z") + P("M60 55 H140 V65 H60Z", "@d") + G(*[C(x, 60, 2, "@l") for x in (70, 85, 100, 115, 130)]) + P("M96 65 H104 V76 Q100 80 96 76Z", "@d")
                   + HI("M68 52 C68 40 76 32 88 29 C80 34 76 42 75 52Z")),
        "jester": ("Jester hat", 2, P("M66 60 C62 40 52 30 36 30 C60 12 84 16 100 30 C116 16 140 12 164 30 C148 30 138 40 134 60Z") + P("M100 30 C116 16 140 12 164 30 C148 30 138 40 134 60 H100Z", "@d")
                   + P("M100 60 V30 C96 20 96 12 100 6 C104 12 104 20 100 30", "@l") + P("M62 53 H138 V63 H62Z", "@l") + DL("M76 53 V63 M88 53 V63 M100 53 V63 M112 53 V63 M124 53 V63", 1.4)
                   + C(36, 31, 5.5, GOLD) + C(164, 31, 5.5, GOLD) + C(100, 6, 5.5, GOLD)),
        "astro": ("Space helmet", 3, C(100, 76, 50, "#d8f0ff", 'fill-opacity=".3" stroke="@k" stroke-width="7"') + C(100, 76, 50, "none", 'stroke="@c" stroke-width="4"')
                  + P("M66 50 Q80 34 102 32", "none", 'stroke="#ffffff" stroke-width="5" opacity=".75"') + C(60, 62, 2.6, "#fff", f'opacity=".75" {NS}') + P("M74 118 Q100 130 126 118 L128 124 Q100 138 72 124Z", "@c")),
    },
    "held": {
        "book": ("Book", 0, P("M134 182 H168 Q171 182 171 185 V226 H134Z", CREAM) + P("M131 180 H165 Q168 180 168 183 V222 H131Z") + P("M131 180 H138 V222 H131Z", "@d") + R(144, 188, 18, 7, "@l", 1.5) + SH("M156 180 H165 Q168 180 168 183 V222 H156Z", .12)
                 + DL("M144 204 H162 M144 210 H158", 1.4, "@l")),
        "pencil": ("Pencil", 0, AT(0, 0, '<g transform="rotate(14 141.5 191)">' + P("M135 122 H148 V226 H135Z") + SH("M143.5 122 H148 V226 H143.5Z") + P("M135 226 H148 L141.5 244Z", "#f1d4a8") + P("M139.3 238 H143.7 L141.5 244Z", INK)
                                + P("M135 110 H148 V122 H135Z", STEEL) + P("M135 100 Q141.5 94 148 100 V110 H135Z", "#f08aa0") + DL("M139.5 124 V224", 1.2, "@l") + '</g>')),
        "trophy": ("Trophy", 1, P("M136 216 H168 V224 H136Z", "@d") + P("M146 200 H158 L160 216 H144Z", "@d") + P("M134 150 C120 150 122 176 140 178", "none", 'stroke="@k" stroke-width="7"') + P("M134 150 C120 150 122 176 140 178", "none", 'stroke="@c" stroke-width="3.6"')
                   + P("M170 150 C184 150 182 176 164 178", "none", 'stroke="@k" stroke-width="7"') + P("M170 150 C184 150 182 176 164 178", "none", 'stroke="@c" stroke-width="3.6"')
                   + P("M132 144 H172 V166 C172 186 160 196 152 200 C144 196 132 186 132 166Z") + SH("M158 144 H172 V166 C172 186 160 196 152 200 C160 186 160 164 158 144Z") + HI("M137 148 H143 V168 C143 176 145 182 148 188 C140 180 137 172 137 164Z")
                   + STAR(153, 166, 8, "@l", NS)),
        "flask": ("Flask", 1, P("M144 172 H160 V176 H157 V196 L174 226 Q177 234 168 234 H136 Q127 234 130 226 L147 196 V176 H144Z", "#eaf6ff", 'fill-opacity=".85"') + P("M139.5 212 H164.5 L174 226 Q177 234 168 234 H136 Q127 234 130 226Z", "@c")
                  + C(148, 222, 2.6, "@l", NS) + C(158, 226, 1.8, "@l", NS) + C(154, 204, 2, "@c", NS) + C(150, 160, 3, "@l", 'opacity=".8"') + C(157, 150, 2, "@l", 'opacity=".8"') + HI("M149 180 V196 L138 216 H134 L147 194 V180Z", .8)),
        "telescope": ("Telescope", 1, AT(0, 0, '<g transform="rotate(-32 141.5 191)">' + R(122, 184, 34, 14, "@d", 3) + R(152, 181, 34, 20, "@c", 3) + R(182, 177, 12, 28, "@d", 3) + R(116, 186, 8, 10, "@l", 2) + HI("M154 183 H184 V187 H154Z", .35)
                                      + SH("M152 195 H186 V201 H152Z") + '</g>')),
        "wand": ("Wand", 2, P("M138 198 L166 142", "none", 'stroke="@k" stroke-width="7.4"') + P("M138 198 L166 142", "none", 'stroke="@d" stroke-width="4.4"') + P("M162 150 L166 142", "none", 'stroke="#fff" stroke-width="4.4"')
                 + STAR(170, 132, 15, "@c") + STAR(170, 132, 6, "#fff", NS) + STAR(150, 122, 4, "@l", NS) + STAR(186, 152, 5, "@l", NS) + STAR(184, 112, 3.4, "@l", NS)),
        "balloon": ("Balloon", 0, P("M141 190 C146 170 160 160 160 132", "none", 'stroke="#8a8d9c" stroke-width="1.6"') + P("M160 128 l-5 8 h10Z", "@d") + P("M160 128 C142 122 136 104 138 92 C140 76 150 68 160 68 C170 68 180 76 182 92 C184 104 178 122 160 128Z")
                    + SH("M166 69 C174 72 181 80 182 92 C184 104 178 122 160 128 C172 114 174 90 166 69Z") + HI("M146 90 C146 80 152 74 158 73 C152 78 150 84 150 92Z", .6)),
        "magnifier": ("Magnifier", 1, P("M141 192 L152 174", "none", 'stroke="@k" stroke-width="9.4"') + P("M141 192 L152 174", "none", 'stroke="@d" stroke-width="6.4"') + C(162, 156, 19, "#eaf6ff", 'fill-opacity=".55" stroke="@k" stroke-width="8"')
                      + C(162, 156, 19, "none", 'stroke="@c" stroke-width="5"') + HI("M150 152 C151 145 157 141 163 141 C157 144 154 148 153 154Z", .9)),
        "coffee": ("Coffee", 0, P("M170 186 C186 186 186 208 168 208", "none", 'stroke="@k" stroke-width="7.4"') + P("M170 186 C186 186 186 208 168 208", "none", 'stroke="@c" stroke-width="4.4"') + P("M144 178 H172 L169 216 Q158 220 147 216Z")
                   + SH("M162 178 H172 L169 216 Q164 218 160 218Z") + E(158, 178, 14, 3.6, "#6b4226") + P("M150 168 Q146 160 150 152 M160 170 Q156 160 160 150", "none", 'stroke="#fff" stroke-width="2.4" opacity=".7"') + HEART(158, 197, .5, "@l", NS)),
        "calculator": ("Calculator", 0, R(136, 168, 34, 50, "@c", 5) + SH("M160 168 H165 Q170 168 170 173 V213 Q170 218 165 218 H160Z") + R(141, 173, 24, 11, "#d7f5dc", 2) + T(160, 182.5, "42", 9, INK)
                       + G(*[R(141 + 8.4 * i, 189 + 7.4 * j, 6.4, 5.2, "@l" if (i, j) != (2, 3) else "#ff8a3d", 1.4, NS) for i in range(3) for j in range(4)])),
        "sword": ("Sword", 2, AT(0, 0, '<g transform="rotate(24 141.5 191)">' + P("M136 178 L138 106 L141.5 96 L145 106 L147 178Z", "#e6eaf2") + SH("M141.5 96 L145 106 L147 178 H141.5Z", .2) + P("M126 176 H157 Q160 181 157 185 H126 Q123 181 126 176Z")
                              + R(138, 185, 7, 20, "@d", 2) + C(141.5, 208, 5, "@c") + C(141.5, 180.5, 2.6, "@l") + '</g>')),
        "lollipop": ("Lollipop", 0, P("M141 194 L154 164", "none", 'stroke="@k" stroke-width="6"') + P("M141 194 L154 164", "none", 'stroke="#fff" stroke-width="3.2"') + C(160, 148, 19) + P("M160 148 m-11 0 a11 11 0 1 1 11 11 a6 6 0 1 1 -5 -9", "none", 'stroke="@l" stroke-width="3.4"')
                     + SH("M168 131 C176 136 181 146 178 156 C174 164 168 167 160 167 C170 160 174 144 168 131Z") + HI("M146 144 C147 138 152 133 158 132 C153 136 151 140 150 146Z", .6)),
    },
    "pet": {
        "cat": ("Cat", 0, PET(P("M40 44 C54 44 56 26 50 20", "none", 'stroke="@k" stroke-width="8"') + P("M40 44 C54 44 56 26 50 20", "none", 'stroke="@c" stroke-width="5"') + E(24, 42, 17, 13) + P("M9 12 L10 -4 L22 6Z") + P("M39 12 L38 -4 L26 6Z")
                              + P("M12 6 L12.5 0 L18 5Z", "@l", NS) + P("M36 6 L35.5 0 L30 5Z", "@l", NS) + E(24, 20, 17, 15) + E(24, 46, 9, 7, "@l", NS) + FACE(17, 31, 20) + CHEEKS(12, 36, 25) + P("M22 25 h4 l-2 2.5Z", "#f08aa0", NS)
                              + DL("M24 27.5 Q21 31 18.5 28.5 M24 27.5 Q27 31 29.5 28.5", 1.3, INK) + DL("M18 9 L20 13 M24 8 V13 M30 9 L28 13", 1.6))),
        "dog": ("Dog", 0, PET(P("M40 40 C48 36 50 30 48 24", "none", 'stroke="@k" stroke-width="8"') + P("M40 40 C48 36 50 30 48 24", "none", 'stroke="@c" stroke-width="5"') + E(24, 42, 17, 13) + E(24, 46, 9, 7, "@l", NS) + E(24, 20, 17, 15)
                              + P("M9 10 C2 12 0 26 6 34 C12 32 14 20 13 12Z", "@d") + P("M39 10 C46 12 48 26 42 34 C36 32 34 20 35 12Z", "@d") + E(24, 27, 8, 6, "@l", NS) + FACE(17, 31, 19) + E(24, 24, 3.4, 2.4, INK, NS)
                              + DL("M24 26 V29 Q21 32 19 30 M24 29 Q27 32 29 30", 1.3, INK) + P("M22 30.5 q2 5 4 0Z", "#f08aa0", NS) + C(34, 13, 5, "@d", f'opacity=".5" {NS}'))),
        "bunny": ("Bunny", 0, PET(P("M12 12 C6 -4 8 -20 14 -22 C20 -20 22 -4 20 10Z") + P("M36 12 C42 -4 40 -20 34 -22 C28 -20 26 -4 28 10Z") + P("M14 8 C11 -4 12 -14 14 -16 C17 -14 18 -4 17 8Z", "#f8b4c4", NS) + P("M34 8 C37 -4 36 -14 34 -16 C31 -14 30 -4 31 8Z", "#f8b4c4", NS)
                                  + E(24, 43, 16, 12) + C(40, 46, 5, "@l") + E(24, 22, 16, 14) + FACE(17.5, 30.5, 21) + CHEEKS(12.5, 35.5, 26) + P("M22.5 25.5 h3 l-1.5 2Z", "#f08aa0", NS) + DL("M24 27.5 V30 M21.5 31 Q24 33 26.5 31", 1.2, INK))),
        "slime": ("Slime", 0, PET(P("M2 54 C-2 30 6 12 24 12 C42 12 50 30 46 54 Q24 58 2 54Z", "@c", 'fill-opacity=".88"') + SH("M34 15 C46 22 50 38 46 54 Q38 56 30 56 C40 44 42 28 34 15Z") + HI("M9 34 C9 24 15 18 22 17 C16 22 14 28 14 36Z", .7)
                                  + FACE(16, 32, 36, 3) + CHEEKS(10, 38, 42, 3.4) + DL("M21 42 Q24 45 27 42", 1.5, INK) + C(30, 2, 3.4, "@c", 'fill-opacity=".88"'))),
        "owl": ("Owl", 1, PET(P("M8 16 L6 2 L18 10Z", "@d") + P("M40 16 L42 2 L30 10Z", "@d") + P("M6 32 C4 14 14 8 24 8 C34 8 44 14 42 32 C42 48 34 54 24 54 C14 54 6 48 6 32Z") + E(24, 40, 11, 12, "@l", NS)
                              + DL("M19 38 q2.5 2.5 5 0 q2.5 2.5 5 0 M19 44 q2.5 2.5 5 0 q2.5 2.5 5 0", 1.3) + C(16, 22, 8.6, "#fff") + C(32, 22, 8.6, "#fff") + C(16.5, 22.5, 4.2, INK, NS) + C(31.5, 22.5, 4.2, INK, NS) + C(15, 21, 1.5, "#fff", NS) + C(30, 21, 1.5, "#fff", NS)
                              + P("M21 27 H27 L24 33Z", "#f0a030") + P("M4 34 C0 40 2 48 8 50 C7 44 7 38 6 34Z", "@d") + P("M44 34 C48 40 46 48 40 50 C41 44 41 38 42 34Z", "@d") + P("M16 54 h6 M26 54 h6", "none", 'stroke="#f0a030" stroke-width="3"'))),
        "robot": ("Robot", 2, PET(L(24, 8, 24, 0, "@k", 2.4) + C(24, -2, 3.4, "#ff5f5f") + R(8, 6, 32, 24, "@l", 7) + R(12, 11, 24, 13, "#1b2440", 4) + C(19, 17.5, 3, "#7df9ff", NS) + C(29, 17.5, 3, "#7df9ff", NS)
                                  + R(10, 32, 28, 17, "@c", 5) + SH("M30 32 H33 Q38 32 38 37 V44 Q38 49 33 49 H30Z") + R(1, 34, 7, 12, "@d", 3) + R(40, 34, 7, 12, "@d", 3) + R(13, 49, 8, 6, "@d", 2) + R(27, 49, 8, 6, "@d", 2)
                                  + HEART(24, 40, .42, "#ff5f5f", NS) + R(3, 12, 5, 9, "@d", 2) + R(40, 12, 5, 9, "@d", 2))),
        "ghost": ("Ghost", 1, PET(P("M4 52 V24 C4 8 14 2 24 2 C34 2 44 8 44 24 V52 L37 46 L30.5 52 L24 46 L17.5 52 L11 46Z", "@c", 'fill-opacity=".9"') + SH("M34 5 C40 9 44 16 44 24 V52 L37 46 L33 50 C36 36 38 18 34 5Z", .14)
                                  + FACE(17, 31, 22, 3) + CHEEKS(11, 37, 29, 3.4) + E(24, 31, 3, 4, INK, NS) + P("M4 32 C-2 30 -4 36 0 40 M44 32 C50 30 52 36 48 40", "@c", 'fill-opacity=".9"') + HI("M9 22 C9 13 14 8 20 7 C15 11 13 16 13 24Z", .7))),
        "dragon": ("Dragon", 3, PET(P("M8 46 C-6 48 -8 36 -2 30 L-6 26 L2 26 C0 34 4 40 12 40Z") + P("M30 22 C34 8 46 4 52 12 C46 14 44 20 44 28Z", "@d") + E(24, 42, 16, 12) + E(24, 46, 9, 7, "@l", NS) + DL("M18 43 h12 M19 48 h10", 1.2)
                                    + P("M10 8 L8 -4 L18 4Z", "@l") + P("M38 8 L40 -4 L30 4Z", "@l") + P("M8 22 C6 10 14 4 24 4 C34 4 42 10 40 22 C40 32 32 36 24 36 C16 36 8 32 8 22Z") + E(24, 28, 9, 5.5, "@l", NS) + FACE(17, 31, 18)
                                    + C(21, 27, 1, INK, NS) + C(27, 27, 1, INK, NS) + CHEEKS(12, 36, 23) + P("M20 5 L24 -2 L28 5Z", "@d") + P("M44 24 q8 -2 8 -10 q-6 2 -8 10Z", FLAME, NS))),
        "chick": ("Chick", 0, PET(P("M20 16 C22 8 28 8 28 14", "none") + C(24, 36, 17) + SH("M32 21 C40 26 43 36 39 45 C36 50 30 53 24 53 C34 46 37 32 32 21Z", .12) + P("M8 34 C2 36 2 44 8 46Z", "@d") + P("M40 34 C46 36 46 44 40 46Z", "@d")
                                  + FACE(18, 30, 32) + CHEEKS(13, 35, 37) + P("M20.5 35 H27.5 L24 40.5Z", "#f0a030") + P("M17 53 v4 M31 53 v4", "none", 'stroke="#f0a030" stroke-width="2.6"'))),
        "fishbowl": ("Fish bowl", 1, PET(P("M14 12 H34 C46 18 50 30 46 42 C42 52 34 55 24 55 C14 55 6 52 2 42 C-2 30 2 18 14 12Z", "#d8f0ff", 'fill-opacity=".6"') + P("M3 30 Q14 26 24 30 T45 30 C48 36 47 40 46 42 C42 52 34 55 24 55 C14 55 6 52 2 42 C0 38 1 34 3 30Z", "#7cc8f4", f'fill-opacity=".7" {NS}')
                                     + P("M16 40 C20 34 30 34 33 40 C30 46 20 46 16 40Z") + P("M33 40 L41 34 V46Z") + C(21, 39, 1.4, INK, NS) + C(38, 30, 1.6, "#fff", f'opacity=".8" {NS}') + C(34, 24, 1.1, "#fff", f'opacity=".8" {NS}')
                                     + R(12, 9, 24, 5, "#d8f0ff", 2.5) + HI("M7 30 C7 22 12 17 17 15 C12 20 11 26 11 32Z", .8))),
        "mushroom": ("Mushroom", 0, PET(P("M15 30 H33 L36 50 Q24 56 12 50Z", "#f4e8d4") + SH("M27 30 H33 L36 50 Q32 52 28 53Z", .12) + FACE(19, 29, 42, 2) + CHEEKS(15, 33, 46, 2.6) + DL("M22 46 Q24 48 26 46", 1.2, INK)
                                    + P("M0 32 C-2 12 10 2 24 2 C38 2 50 12 48 32 Q24 38 0 32Z") + SH("M34 5 C44 10 50 20 48 32 Q40 34 32 35 C38 26 39 14 34 5Z") + C(12, 18, 5, "#fff", NS) + C(27, 11, 4.4, "#fff", NS) + C(38, 23, 4, "#fff", NS) + C(22, 27, 2.6, "#fff", NS))),
        "penguin": ("Penguin", 1, PET(P("M6 30 C0 34 0 44 6 46Z", "@d") + P("M42 30 C48 34 48 44 42 46Z", "@d") + P("M6 30 C4 12 12 4 24 4 C36 4 44 12 42 30 C44 46 36 54 24 54 C12 54 4 46 6 30Z", "@d")
                                    + P("M12 32 C10 20 14 14 19 14 C22 14 23 16 24 18 C25 16 26 14 29 14 C34 14 38 20 36 32 C37 44 32 51 24 51 C16 51 11 44 12 32Z", "#fff", NS) + FACE(18, 30, 23) + CHEEKS(13.5, 34.5, 28)
                                    + P("M20.5 26 H27.5 L24 31Z", "#f0a030") + E(16, 54.5, 6, 2.8, "#f0a030") + E(32, 54.5, 6, 2.8, "#f0a030") + P("M14 36 Q24 42 34 36 L34 40 Q24 46 14 40Z", "@c"))),
    },
    "trinket": {
        "pi": ("Pi", 0, GLYPH(100, 188, "π", 130)),
        "sigma": ("Sigma", 0, GLYPH(100, 188, "Σ", 130)),
        "infinity": ("Infinity", 0, GLYPH(100, 184, "∞", 140)),
        "emc2": ("E = mc²", 1, GLYPH(100, 168, "E=mc²", 52)),
        "h2o": ("H₂O", 0, GLYPH(100, 168, "H₂O", 64) + C(60, 216, 9, "@l") + C(140, 216, 9, "@l") + C(100, 226, 14, "@c") + HI("M92 222 q2 -6 8 -7 q-4 3 -4 8Z", .6)),
        "atom": ("Atom", 1, G(*[E(100, 150, 64, 23, "none", f'stroke="@k" stroke-width="7.5" transform="rotate({a} 100 150)"') for a in (0, 60, 120)], *[E(100, 150, 64, 23, "none", f'stroke="@c" stroke-width="4.5" transform="rotate({a} 100 150)"') for a in (0, 60, 120)],
                              C(100, 150, 12, "@d"), HI("M93 146 q2 -6 8 -7 q-4 3 -4 8Z", .5), C(164, 150, 5.5, "@l"), C(68, 95, 5.5, "@l"), C(68, 205, 5.5, "@l"))),
        "dna": ("DNA", 1, G(*[L(100 - w, y, 100 + w, y, "@l", 4) for y, w in [(92, 20), (108, 26), (124, 14), (146, 14), (162, 26), (178, 20), (194, 8), (216, 20), (232, 26)]])
                + P("M70 76 C130 106 70 150 130 180 S70 220 130 250", "none", 'stroke="@k" stroke-width="10"') + P("M70 76 C130 106 70 150 130 180 S70 220 130 250", "none", 'stroke="@c" stroke-width="7"')
                + P("M130 76 C70 106 130 150 70 180 S130 220 70 250", "none", 'stroke="@k" stroke-width="10"') + P("M130 76 C70 106 130 150 70 180 S130 220 70 250", "none", 'stroke="@d" stroke-width="7"')),
        "planet": ("Planet", 1, P("M34 170 C20 150 60 132 100 128 C140 124 178 126 166 146", "none", 'stroke="@k" stroke-width="10"') + P("M34 170 C20 150 60 132 100 128 C140 124 178 126 166 146", "none", 'stroke="@l" stroke-width="7"')
                   + C(100, 150, 44) + SH("M118 110 C138 120 148 142 142 164 C136 182 120 194 100 194 C126 178 134 140 118 110Z") + DL("M60 138 Q100 150 140 132 M58 160 Q100 172 142 156", 3) + HI("M68 136 C70 122 82 112 96 110 C84 116 78 126 76 138Z", .5)
                   + P("M34 170 C52 186 120 180 166 146", "none", 'stroke="@k" stroke-width="10"') + P("M34 170 C52 186 120 180 166 146", "none", 'stroke="@l" stroke-width="7"') + STAR(156, 88, 8, "@l") + STAR(48, 216, 6, "@l")),
        "star": ("Star", 0, P("M100 76 L121 124 L173 129 L134 164 L145 215 L100 189 L55 215 L66 164 L27 129 L79 124Z") + SH("M100 76 L121 124 L173 129 L134 164 L145 215 L100 189Z", .14) + FACE(86, 114, 148, 4.4) + CHEEKS(76, 124, 160, 6)
                 + DL("M94 162 Q100 168 106 162", 2.4, INK)),
        "bulb": ("Light bulb", 0, G(*[L(100 + 62 * math.cos(a), 132 + 62 * math.sin(a), 100 + 74 * math.cos(a), 132 + 74 * math.sin(a), "@l", 5) for a in (3.5, 4.1, 4.71, 5.3, 5.9)])
                 + P("M100 88 C126 88 144 108 144 132 C144 150 132 160 126 172 L124 184 H76 L74 172 C68 160 56 150 56 132 C56 108 74 88 100 88Z") + SH("M118 92 C134 100 144 114 144 132 C144 150 132 160 126 172 L124 184 H108 C122 160 130 124 118 92Z", .14)
                 + DL("M90 182 L86 150 L100 160 L114 150 L110 182", 2.6, "@l") + HI("M68 128 C68 112 78 100 92 96 C82 104 77 116 77 130Z", .6) + R(78, 184, 44, 26, STEEL, 5) + DL("M78 193 H122 M78 201 H122", 2, "#8a8d9c") + R(88, 210, 24, 9, "#5a5c66", 4)),
        "rocket": ("Rocket", 2, P("M86 196 Q100 246 114 196Z", FLAME) + P("M93 196 Q100 226 107 196Z", "#fff3b0", NS) + P("M76 156 L50 200 L80 190Z", "@d") + P("M124 156 L150 200 L120 190Z", "@d")
                   + P("M100 64 Q136 108 124 192 L76 192 Q64 108 100 64Z", CREAM) + SH("M100 64 Q136 108 124 192 H106 Q120 120 100 64Z", .14) + P("M100 64 Q114 80 120 100 Q100 106 80 100 Q86 80 100 64Z") + P("M76 180 H124 L124 192 H76Z")
                   + C(100, 132, 14, "#7cc8f4", 'stroke="@k" stroke-width="5"') + HI("M92 128 q2 -6 8 -7 q-4 3 -4 8Z", .7)),
        "book": ("Book", 0, P("M62 96 H136 Q142 96 142 102 V214 H62Z", CREAM) + P("M56 90 H130 Q136 90 136 96 V206 H56Z") + P("M56 90 H70 V206 H56Z", "@d") + SH("M112 90 H130 Q136 90 136 96 V206 H112Z", .12) + R(80, 106, 46, 22, "@l", 4)
                 + DL("M80 144 H126 M80 158 H116", 3, "@l") + P("M112 206 V226 L119 219 L126 226 V206Z", "#e5484d")),
        "magnet": ("Magnet", 1, P("M62 90 V150 A38 38 0 0 0 138 150 V90 H112 V150 A12 12 0 0 1 88 150 V90Z") + P("M62 90 H88 V112 H62Z", "#eef0f4") + P("M112 90 H138 V112 H112Z", "#eef0f4") + SH("M126 90 H138 V150 A38 38 0 0 1 100 188 A26 26 0 0 0 126 150Z", .14)
                   + G(*[P(d, "none", 'stroke="@l" stroke-width="4"') for d in ("M50 70 l8 10 l-10 2 l8 10", "M150 70 l-8 10 l10 2 l-8 10")])),
        "medal": ("Medal", 2, P("M74 66 H100 L100 120 L86 120Z", "@d") + P("M126 66 H100 L100 120 L114 120Z", "@l") + C(100, 152, 38) + C(100, 152, 29, "@l") + SH("M116 118 C134 126 142 144 138 162 C134 178 120 190 100 190 C124 174 130 144 116 118Z", .14)
                  + STAR(100, 152, 20, "@c") + HI("M70 142 C72 130 80 121 90 117 C82 124 78 133 77 144Z", .5)),
    },
}
STYLE_SLOT_COUNTS = {slot: len(styles) for slot, styles in STYLES.items()}


def _title(name):
    """Capitalise each plain word; words with symbols (T-shirt, H₂O, E = mc²) keep their spelling."""
    return " ".join(w if not w.isalpha() else w.capitalize() for w in name.split())


def _rarity(style_tier, colour_tier):
    return max(0, min(5, style_tier + colour_tier))


def _build():
    catalog = {}
    for slot, styles in STYLES.items():
        for style_key, (style_name, style_tier, _) in styles.items():
            for colour_key, (colour_name, _c, _d, _l, colour_tier) in COLOURS.items():
                rarity = _rarity(style_tier, colour_tier)
                item_id = f"{slot}.{style_key}.{colour_key}"
                catalog[item_id] = {"id": item_id, "slot": slot, "name": _title(f"{colour_name} {style_name}"),
                                    "style": style_key, "colour": colour_key, "rarity": rarity, "value": VALUE[rarity],
                                    "shop": rarity <= SHOP_MAX_RARITY, "price": round(VALUE[rarity] * SHOP_MARKUP)}
    return catalog


CATALOG = _build()
BY_RARITY = {r: [i for i, item in CATALOG.items() if item["rarity"] == r] for r in range(len(RARITIES))}


def public(item):
    return {**item, "rarity_name": RARITIES[item["rarity"]]}


def shade(colour, factor):
    """`colour` (#rrggbb) moved towards black (factor < 1) or white (factor > 1)."""
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    if factor < 1:
        r, g, b = (round(v * factor) for v in (r, g, b))
    else:
        r, g, b = (round(v + (255 - v) * (factor - 1)) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def tone(skin):
    """A skin as a colour: a SKINS key, or a #rrggbb colour as it is."""
    return skin if str(skin).startswith("#") else SKINS.get(skin, SKINS[DEFAULT_SKIN])[1]


def ink(colour):
    """The outline for a shape of this colour: a deep shade of it, or the neutral ink for gradients."""
    return shade(colour, 0.5) if colour.startswith("#") else INK


BUILDS = {"masculine": "Masculine", "feminine": "Feminine"}
DEFAULT_BUILD = "masculine"
# What a character has in a slot with nothing equipped: (style, colour) per build. Under everything both builds wear swimwear
# (`swimwear`), so an undressed character is in board shorts or a sporty two-piece.
STARTER = {
    "masculine": {"hair": ("short", "brown"), "shoes": ("sneakers", "white")},
    "feminine": {"hair": ("long", "brown"), "shoes": ("sneakers", "white")},
}
# Each build's outline of the parts clothes follow, and where its hands are. Right-hand parts mirror the left.
def _mirror(d):
    """A path of absolute points flipped left to right on the 200-wide canvas."""
    numbers = itertools.count()
    return re.sub(r"-?\d+(?:\.\d+)?", lambda m: f"{200 - float(m.group()):g}" if next(numbers) % 2 == 0 else m.group(), d)


GEOMETRY = {
    "masculine": {
        "@TORSO": "M87 116 C76 117 67 122 65 132 C65 150 68 170 71 188 C72 197 73 202 74 206 L126 206 C127 202 128 197 129 188 C132 170 135 150 135 132 C133 122 124 117 113 116Z",
        "@ARML": "M68 127 C58 133 53 157 51 184 C50.5 194 65 195 66 186 C68 168 72 152 78 141Z",
        "@LEGL": "M74 198 C73 222 74 244 76 263 C81 266 93 266 97 263 C98 244 99 222 99.5 204Z",
        "hand": (58.5, 191, 8.5),
    },
    "feminine": {
        "@TORSO": "M88 116 C79 117 72 122 71 132 C71 148 77 158 80 168 C75 180 70 192 70 206 L130 206 C130 192 125 180 120 168 C123 158 129 148 129 132 C128 122 121 117 112 116Z",
        "@ARML": "M72 127 C63 133 58 157 56 184 C55.5 193 68.5 194 69.5 186 C71 168 75 152 80 141Z",
        "@LEGL": "M75 198 C74 222 76 244 78 263 C82 266 93 266 96 263 C97 244 98.5 222 99.5 204Z",
        "hand": (62.5, 191, 7.8),
    },
}
for _shapes in GEOMETRY.values():
    _shapes["@ARMR"], _shapes["@LEGR"] = _mirror(_shapes["@ARML"]), _mirror(_shapes["@LEGL"])
PARTS = ("@TORSO", "@ARML", "@ARMR", "@LEGL", "@LEGR")
# Where each kind of drawing sits on the canvas: (transform, scale). The scale keeps the outline the same weight everywhere.
BODY_SPACE, HEAD_SPACE, CANVAS = ("matrix(.82 0 0 .82 18 49)", .82), ("matrix(1.2 0 0 1.2 -20 4.2)", 1.2), ("", 1)
PET_SPACE = ("matrix(1.18 0 0 1.18 3 215)", 1.18)
SPACE = {"pet": PET_SPACE, "back": BODY_SPACE, "bottom": BODY_SPACE, "shoes": BODY_SPACE, "top": BODY_SPACE, "held": BODY_SPACE, "face": HEAD_SPACE, "hair": HEAD_SPACE, "hat": HEAD_SPACE}
LINE = 2.1               # outline weight, in canvas units
IRIS, IRIS_DEEP = "#5a3e2b", "#3b2314"
EYE_Y = 85
# The chibi face: a wide round head with full cheeks and a small chin (top 42, sides 63-137, chin 114, in head space).
HEAD = "M63 79 C63 53 79 42 100 42 C121 42 137 53 137 79 C137 99 122 113 100 114 C78 113 63 99 63 79Z"


def geometry(markup, build):
    shapes = GEOMETRY.get(build, GEOMETRY[DEFAULT_BUILD])
    for token in PARTS:
        markup = markup.replace(token, shapes[token])
    return markup


def placed(markup, space, stroke):
    """A drawing put in its place on the canvas, with every shape outlined in `stroke`; shapes that set their own stroke keep it."""
    if not markup:
        return ""
    transform, scale = space
    move = f' transform="{transform}"' if transform else ""
    return f'<g{move} stroke="{stroke}" stroke-width="{LINE / scale:.2f}" stroke-linejoin="round" stroke-linecap="round">{markup}</g>'


def fill(markup, item_id=None, skin=None, build=None):
    """Fill the body-part and colour placeholders of one drawing for the build, the item's colour and the skin."""
    markup = geometry(markup, build)
    _, c, d, l, _ = COLOURS[CATALOG[item_id]["colour"]] if item_id else COLOURS["grey"]
    return markup.replace("@c", c).replace("@d", d).replace("@l", l).replace("@k", ink(d)).replace("@s", tone(skin))


def hand(skin, build, side=1):
    """One hand (side 1 is the character's left, drawn on the right), so it can be drawn again over whatever it holds."""
    x, y, r = GEOMETRY[build if build in BUILDS else DEFAULT_BUILD]["hand"]
    s = tone(skin)
    return C(200 - x if side > 0 else x, y, r, s, f'stroke="{ink(s)}"')


def drawing(item_id, skin=None, build=None, part=None):
    """One item as it sits on the character. Backgrounds and auras are flat scenery with no outline. A drawing in several parts
    ("behind ||| in front") is drawn whole, or only `part` of it."""
    item = CATALOG[item_id]
    slot = item["slot"]
    parts = fill(STYLES[slot][item["style"]][2], item_id, skin, build).split("|||")
    markup = "".join(parts) if part is None else (parts[part] if part < len(parts) else "")
    if slot in ("background", "aura"):
        return markup
    if slot == "held":      # things are held where this build's hand is, with the hand closed over them
        x = GEOMETRY[build if build in BUILDS else DEFAULT_BUILD]["hand"][0]
        markup = f'<g transform="translate({200 - x:g} 191) scale(1.12) translate(-141.5 -191)">{markup}</g>' + hand(skin, build)
    return placed(markup, SPACE.get(slot, CANVAS), "@k").replace("@k", ink(COLOURS[item["colour"]][2]))


def defs(build):
    """Gradients every picture uses, and the clip paths that cut sleeves and legs for this build."""
    shapes = GEOMETRY.get(build, GEOMETRY[DEFAULT_BUILD])
    clips = "".join(f'<clipPath id="k-{name}"><rect x="-50" y="-50" width="300" height="{y + 50}"/></clipPath>' for name, y in CUTS.items())
    clips += '<clipPath id="k-below"><rect x="-50" y="128" width="300" height="200"/></clipPath>'
    clips += "".join(f'<clipPath id="k-{token[1:].lower()}"><path d="{shapes[token]}"/></clipPath>' for token in PARTS)
    clips += f'<clipPath id="k-head"><path d="{HEAD}"/></clipPath>'
    return DEFS.replace("</defs>", clips + "</defs>")


def eye(x, feminine):
    """One big eye: white, a tall two-tone iris, pupil, a large and a small highlight, an arched upper lash line and a light lower lid;
    the feminine build adds a lash flick at the outer corner."""
    y, side = EYE_Y, (-1 if x < 100 else 1)
    lash = f'stroke="{INK}" stroke-width="{2.9 if feminine else 2.6}"'
    flick = P(f"M{x + side * 8.4} {y - 3.5} Q{x + side * 12} {y - 6} {x + side * 13} {y - 10.5}", "none", lash) if feminine else ""
    return G(E(x, y, 7.8, 9.6, "#fff", NS),
             E(x, y + 1, 6.3, 8.3, IRIS, NS), P(f"M{x - 6.3} {y + 0.5} A6.3 8.3 0 0 1 {x + 6.3} {y + 0.5} Z", IRIS_DEEP, f'opacity=".75" {NS}'),
             E(x, y + 1.5, 3, 4.5, INK, NS), E(x - 2.4, y - 3, 2.6, 3.2, "#fff", NS), C(x + 2.8, y + 5, 1.3, "#fff", f'opacity=".9" {NS}'),
             P(f"M{x + side * 8.8} {y - 2.5} Q{x - side * .5} {y - 14.5} {x - side * 8} {y - 6}", "none", lash),      # arched, a little lower at the outer corner
             P(f"M{x - 4} {y + 10.2} Q{x} {y + 11.2} {x + 4} {y + 10.2}", "none", f'stroke="{INK}" stroke-width="1" opacity=".4"'),
             flick)


def body(skin, build=None, line=None):
    """The character from the neck down in a skin tone: legs, arms, hands and torso, in body space."""
    build = build if build in BUILDS else DEFAULT_BUILD
    shapes = GEOMETRY[build]
    s = tone(skin)
    x, y, r = shapes["hand"]
    limbs = G(P(shapes["@LEGL"], s), P(shapes["@LEGR"], s), P(shapes["@ARML"], s), P(shapes["@ARMR"], s), C(x, y, r, s), C(200 - x, y, r, s),
              P(shapes["@TORSO"], s), R(92, 106, 16, 16, s, 6),
              f'<g clip-path="url(#k-torso)">{SH("M117 100 C125 140 123 180 115 215 H150 V100Z", .12)}{SH("M84 112 H116 V119 Q100 127 84 119Z", .16)}</g>')
    return placed(limbs, BODY_SPACE, line or ink(s))


def head(skin, build=None, face=True, line=None):
    """The head in head space; without a face it is the plain mannequin of item icons."""
    feminine = build == "feminine"
    s = tone(skin)
    o = shade(s, 0.72)
    mouth = (P("M95.5 101.5 Q100 105.5 104.5 101.5 Q100 103 95.5 101.5Z", "#d9566b", f'stroke="{shade("#d9566b", 0.7)}" stroke-width="1.4"') if feminine
             else P("M95 101.5 Q100 105.5 105 101.5", "none", f'stroke="{INK}" stroke-width="2.1"'))
    blush = .5 if feminine else .36
    features = G(
        eye(86, feminine), eye(114, feminine),
        P("M99.6 94 L100.8 96", "none", f'stroke="{o}" stroke-width="1.6"'),                                           # nose
        mouth, E(75.5, 98, 7, 4.2, "#ff7a8a", f'opacity="{blush}" {NS}'), E(124.5, 98, 7, 4.2, "#ff7a8a", f'opacity="{blush}" {NS}'),
    ) if face else ""
    return placed(G(
        E(63.5, 86, 5.5, 8, s), E(136.5, 86, 5.5, 8, s), P("M62 84 Q64.5 86 63 90 M138 84 Q135.5 86 137 90", "none", f'stroke="{o}" stroke-width="1.3"'),   # ears
        P(HEAD, s),
        ('<g clip-path="url(#k-head)">' + E(100, 45, 44, 17, o, f'opacity=".34" {NS}') + "</g>") if face else "",                                      # the shadow hair and hats cast
    ) + features, HEAD_SPACE, line or ink(s))


def brows(skin, build=None):
    """The eyebrows, drawn over the fringe so the expression is never hidden: soft arches, a touch lower at the outer ends."""
    stroke = f'stroke="{shade(tone(skin), 0.38)}" stroke-width="{1.8 if build == "feminine" else 2.3}"'
    return placed(P("M77.5 69.5 Q85.5 63.5 93 67 M122.5 69.5 Q114.5 63.5 107 67", "none", stroke), HEAD_SPACE, "none")


def swimwear(build):
    """The base layer every character wears under their clothes: board shorts, or a sporty two-piece (crop top and swim shorts)."""
    if build == "feminine":
        suit, trim = "#e0607e", "#b3405c"
        top = TORSO_CLIP(R(60, 128, 80, 34, suit) + SH("M117 100 V170 H150 V100Z") + R(60, 156, 80, 6, trim, 0, NS)) + PAIR(P("M85 116.5 C83 121 82 126 82 130 H90 C90 126 91 121 92.5 116.5Z", suit))
        bottoms = P("M70 193 H130 L131 212 H69Z", suit) + LEGS("short", suit) + P("M70 193 H130 V199 H70Z", trim)
        return placed(geometry(top + bottoms, build), BODY_SPACE, ink(trim))
    shorts, stripe = "#2b5aa8", "#f2c230"
    return placed(geometry(P("M72 192 H128 L130 212 H70Z", shorts) + LEGS("short", shorts) + R(74, 199, 5, 30, stripe, 0, f'{NS} clip-path="url(#k-legl)"')
                           + R(121, 199, 5, 30, stripe, 0, f'{NS} clip-path="url(#k-legr)"') + P("M72 192 H128 V199 H72Z", "#1e3f78") + DL("M96 196 L94 205 M104 196 L106 205", 1.6, "#fff"), build),
                  BODY_SPACE, ink("#1e3f78"))


def hair_layers(item_id, skin=None, build=None, crest=True):
    """(behind the head, in front of it) for a hair item; `crest` is false under a hat that covers the crown."""
    back, top, front = fill(STYLES["hair"][CATALOG[item_id]["style"]][2], item_id, skin, build).split("|||")
    stroke = ink(COLOURS[CATALOG[item_id]["colour"]][2])
    return placed((top if crest else "") + back, HEAD_SPACE, stroke), placed(front, HEAD_SPACE, stroke)


GROUND = E(100, 279, 50, 7, "#000", 'opacity=".2"')
CROPS = {"hat": "34 -8 132 132", "hair": "18 26 164 164", "face": "50 62 100 84", "top": "36 126 128 150", "bottom": "44 190 112 96",
         "shoes": "58 236 84 54", "held": "106 142 84 112", "pet": "-8 184 78 102", "back": "0 110 200 190"}
BUST = "28 22 144 144"
TALL_HELD, TALL_CROP = ("pencil", "balloon", "wand", "sword"), "98 86 100 170"       # things held that reach above the head
FULL_COVER_HATS = ("helmet", "beanie", "tophat", "chef", "viking")       # no starter hair shows under these
COVERING_HATS = FULL_COVER_HATS + ("cap", "wizard", "gradcap", "cowboy", "tricorn", "jester")     # these flatten whatever stands above the crown
MANNEQUIN, MANNEQUIN_LINE = "#e2e5ee", "#aeb3c2"        # the plain stand item icons are shown on


def figure(worn, skin, build, face=True, line=None, dressed=True):
    """The character with `worn` (slot -> item id) on it, back to front. `dressed` adds the swimwear every character has underneath."""
    hat = CATALOG[worn["hat"]]["style"] if worn.get("hat") else None
    back, front = hair_layers(worn["hair"], skin, build, crest=hat not in COVERING_HATS) if worn.get("hair") else ("", "")
    piece = lambda slot, part=None: drawing(worn[slot], skin, build, part) if worn.get(slot) else ""
    return G(piece("background"), piece("aura"), piece("back", 0), back, GROUND, body(skin, build, line), swimwear(build) if dressed else "",
             piece("shoes"), piece("bottom"), piece("top"), piece("back", 1), head(skin, build, face, line), piece("face"), front, brows(skin, build) if face else "", piece("hat"), piece("held"), piece("pet"))


def avatar_svg(outfit, skin=None, size=None, crop=None, build=None):
    """The whole character, or with `crop="bust"` its head and shoulders. `outfit` maps a slot to an item id; unknown or non-wearable
    entries are ignored, and an empty hair or shoes slot shows the build's starter piece instead."""
    build = build if build in BUILDS else DEFAULT_BUILD
    worn = {slot: item_id for slot, item_id in outfit.items() if slot in WORN and item_id in CATALOG and CATALOG[item_id]["slot"] == slot}
    for slot, (style, colour) in STARTER[build].items():
        if slot not in worn and not (slot == "hair" and worn.get("hat") and CATALOG[worn["hat"]]["style"] in FULL_COVER_HATS):
            worn[slot] = f"{slot}.{style}.{colour}"
    return _wrap(figure(worn, skin, build), BUST if crop == "bust" else "0 0 200 300", size, build)


def _wrap(inner, view, size=None, build=None):
    w, h = [float(x) for x in view.split()[2:]]
    dims = f' width="{size}" height="{round(size * h / w)}"' if size else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}"{dims}>{defs(build)}{inner}</svg>'


def item_svg(item_id, skin=None):
    """An item on its own, on a transparent ground so the page can colour it by rarity: trinkets as a card, wearables on a plain
    mannequin cropped to where the item sits, pets and held things alone, backgrounds as a small scene."""
    item = CATALOG[item_id]
    slot = item["slot"]
    if slot == "trinket":
        pale = item["colour"] in LIGHT_COLOURS
        top, bottom = ("#3a3550", "#221f33") if pale else ("#fffdf6", "#efe9da")
        card = (f'<linearGradient id="card" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>'
                + R(10, 10, 180, 280, "url(#card)", 20, 'stroke="#000" stroke-opacity=".13" stroke-width="2"') + R(20, 20, 160, 260, "none", 14, 'stroke="#fff" stroke-opacity=".35" stroke-width="2"'))
        return _wrap(card + drawing(item_id, skin), "0 0 200 300")
    if slot == "background":
        starter = {s: "{}.{}.{}".format(s, *pick) for s, pick in STARTER[DEFAULT_BUILD].items()}
        return _wrap(drawing(item_id) + '<g opacity=".55">' + figure(starter, skin, None) + "</g>", "0 0 200 300")
    if slot in ("held", "pet"):       # shown alone (a held thing with the hand that holds it): beside the mannequin they would be a corner of the picture
        return _wrap(drawing(item_id, MANNEQUIN), TALL_CROP if slot == "held" and item["style"] in TALL_HELD else CROPS[slot])
    return _wrap(figure({slot: item_id}, MANNEQUIN, None, face=False, line=MANNEQUIN_LINE, dressed=False), CROPS.get(slot, "0 0 200 300"))


def png(svg, width):
    """The SVG drawn as a PNG `width` pixels wide (for the Android app, which has no SVG renderer)."""
    import cairosvg
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=width)
