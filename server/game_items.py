"""The rewards catalogue and its art.

Every item is a style (a shape such as "wizard hat") in a colour (such as "Galaxy"), so the catalogue is large but regular. Item ids are
`slot.style.colour`. Art is plain SVG drawn on a 200 x 300 canvas; the same drawing code makes item icons and the whole character, so
the website and the Android app show exactly the same thing. Colour placeholders in a drawing: @c main, @d dark, @l light, @s skin.
"""

ART_VERSION = 5          # bump when drawings change, so cached pictures are fetched again

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
        '<filter id="grey"><feColorMatrix type="saturate" values="0"/></filter><radialGradient id="glow"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>')

SKINS = {"porcelain": ("Porcelain", "#fbe3d0"), "sand": ("Sand", "#f3c9a0"), "honey": ("Honey", "#e0a878"), "tan": ("Tan", "#c68a5a"),
         "umber": ("Umber", "#9a6240"), "cocoa": ("Cocoa", "#6b3f28"), "mint": ("Mint", "#a9e0c4"), "lilac": ("Lilac", "#d1b8ee")}
DEFAULT_SKIN = "sand"

SLOTS = ["background", "aura", "back", "bottom", "shoes", "top", "face", "hair", "hat", "held", "pet", "trinket"]
WORN = [s for s in SLOTS if s != "trinket"]
LAYER_ORDER = ["background", "aura", "back", "pet", "BODY", "shoes", "bottom", "top", "face", "hair", "hat", "held"]
SLOT_NAMES = {"background": "Backgrounds", "aura": "Auras", "back": "Back", "bottom": "Bottoms", "shoes": "Shoes", "top": "Tops", "face": "Face",
              "hair": "Hair", "hat": "Hats", "held": "Held", "pet": "Pets", "trinket": "Trinkets"}

POLY = lambda pts, fill="@c", extra="": f'<polygon points="{pts}" fill="{fill}" {extra}/>'
P = lambda d, fill="@c", extra="": f'<path d="{d}" fill="{fill}" {extra}/>'
R = lambda x, y, w, h, fill="@c", rx=0, extra="": f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" {extra}/>'
C = lambda x, y, r, fill="@c", extra="": f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" {extra}/>'
E = lambda x, y, rx, ry, fill="@c", extra="": f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{fill}" {extra}/>'
L = lambda x1, y1, x2, y2, stroke="@d", w=3: f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{w}" stroke-linecap="round"/>'
T = lambda x, y, s, size=40, fill="@c", extra="": f'<text x="{x}" y="{y}" font-size="{size}" font-family="Georgia,serif" font-weight="700" text-anchor="middle" fill="{fill}" {extra}>{s}</text>'
STAR = lambda x, y, r, fill="@l": f'<path d="M{x} {y-r} L{x+r*.28} {y-r*.28} L{x+r} {y} L{x+r*.28} {y+r*.28} L{x} {y+r} L{x-r*.28} {y+r*.28} L{x-r} {y} L{x-r*.28} {y-r*.28}Z" fill="{fill}"/>'
G = lambda *parts: "".join(parts)
# Clothes follow the body: a drawing names body parts (@TORSO, @ARML, @ARMR, @LEGL, @LEGR) and each build supplies its own outline, so
# one T-shirt fits both bodies. Sleeves and trouser legs are the limb outline cut off at a height (the clip paths in `defs`).
CLIP = lambda part, cut, extra="": f'<path d="{part}" fill="@c" clip-path="url(#k-{cut})" {extra}/>'
TORSO_CLIP = lambda inner: f'<g clip-path="url(#k-torso)">{inner}</g>'
CUTS = {"cap": 142, "sleeve": 156, "wrist": 184, "knee": 242, "short": 228, "ankle": 256, "long": 259}
NECK = P("M90 119 Q100 129 110 119", "none", 'stroke="@d" stroke-width="2" stroke-linecap="round"')
CUFFS = '<path d="@ARML" fill="@d" clip-path="url(#k-cuff)"/><path d="@ARMR" fill="@d" clip-path="url(#k-cuff)"/>'
HIPS = P("M73 193 H127 L129 212 H71Z") + R(73, 193, 54, 6, "@d", 2)
# Hair has two layers split by "|||": what sits behind the head (volume, long lengths) and what frames the face.
BACK = P("M61 88 C56 46 80 35 100 35 C120 35 144 46 139 88Z") + "|||"
FRONT_SHORT = P("M63 84 C60 52 80 40 100 40 C122 40 140 52 137 84 C134 72 128 63 120 59 C108 66 90 67 78 61 C72 66 66 74 63 84Z")
FRONT_PART = P("M63 88 C59 52 80 40 100 40 C120 40 141 52 137 88 C134 74 126 62 104 56 C100 62 92 66 80 66 C72 70 66 78 63 88Z")
FRONT_SWEPT = P("M63 86 C60 52 80 40 100 40 C122 40 140 52 137 86 C132 70 120 58 98 60 C86 62 74 68 63 86Z")

# slot -> style key -> (name, tier, drawing)
STYLES = {
    "background": {
        "plain": ("Plain", 0, R(0, 0, 200, 300)),
        "fade": ("Fade", 0, '<rect width="200" height="300" fill="@c"/>' + R(0, 150, 200, 150, "@l", 0, 'opacity=".55"')),
        "stripes": ("Stripes", 0, R(0, 0, 200, 300, "@l") + G(*[R(x, 0, 20, 300, "@c", 0, 'opacity=".7"') for x in range(0, 200, 40)])),
        "dots": ("Polka", 0, R(0, 0, 200, 300, "@l") + G(*[C(x, y, 7, "@c") for x in range(20, 200, 40) for y in range(20, 300, 40)])),
        "graph": ("Graph paper", 1, R(0, 0, 200, 300, "@l") + G(*[L(x, 0, x, 300, "@c", 1) for x in range(0, 201, 20)], *[L(0, y, 200, y, "@c", 1) for y in range(0, 301, 20)])),
        "stars": ("Starfield", 1, R(0, 0, 200, 300, "@d") + G(*[STAR(x, y, 5 + (x * y) % 5) for x, y in [(30, 30), (160, 50), (90, 20), (40, 120), (170, 150), (20, 220), (150, 260), (110, 90), (60, 270), (180, 230)]])),
        "sunset": ("Sunset", 2, R(0, 0, 200, 300, "@c") + R(0, 120, 200, 180, "@l", 0, 'opacity=".5"') + C(100, 170, 46, "#fff3b0", 'opacity=".85"') + R(0, 210, 200, 90, "@d", 0, 'opacity=".5"')),
        "waves": ("Waves", 1, R(0, 0, 200, 300, "@l") + G(*[P(f"M0 {y} Q25 {y-14} 50 {y} T100 {y} T150 {y} T200 {y} V300 H0Z", "@c", 'opacity=".55"') for y in (190, 220, 250)])),
        "checker": ("Checker", 0, R(0, 0, 200, 300, "@l") + G(*[R(x, y, 25, 25, "@c") for x in range(0, 200, 25) for y in range(0, 300, 25) if (x // 25 + y // 25) % 2 == 0])),
        "spotlight": ("Spotlight", 2, R(0, 0, 200, 300, "@d") + E(100, 230, 90, 36, "@l", 'opacity=".45"') + POLY("70,0 130,0 190,240 10,240", "@l", 'opacity=".25"')),
    },
    "aura": {
        "glow": ("Glow", 1, E(100, 160, 90, 130, "url(#glow)", 'opacity=".9"') + E(100, 160, 80, 120, "@c", 'opacity=".28"')),
        "sparkles": ("Sparkles", 1, G(STAR(40, 60, 9, "@c"), STAR(165, 90, 7, "@l"), STAR(30, 190, 6, "@l"), STAR(172, 200, 10, "@c"), STAR(55, 250, 7, "@c"), STAR(150, 30, 6, "@l"))),
        "ring": ("Halo ring", 1, E(100, 160, 78, 122, "none", 'stroke="@c" stroke-width="5" stroke-dasharray="3 9" stroke-linecap="round"')),
        "flames": ("Flames", 2, G(*[P(f"M{x} 280 Q{x-14} 240 {x} 210 Q{x+4} 240 {x+12} 225 Q{x+22} 255 {x} 280Z", "@c", 'opacity=".8"') for x in (30, 60, 140, 172)])),
        "hearts": ("Hearts", 1, G(*[P(f"M{x} {y} c-6 -10 -18 -2 -10 8 l10 10 l10 -10 c8 -10 -4 -18 -10 -8Z", "@c") for x, y in [(36, 90), (160, 120), (28, 200), (168, 220), (60, 40)]])),
        "orbit": ("Orbit", 2, E(100, 160, 88, 28, "none", 'stroke="@c" stroke-width="4" transform="rotate(-18 100 160)"') + C(176, 134, 8, "@l") + C(24, 186, 6, "@c")),
        "storm": ("Storm cloud", 2, G(E(100, 28, 60, 20, "@d"), E(70, 36, 30, 16, "@d"), E(132, 36, 30, 16, "@d"), P("M94 52 L106 52 L98 78 L110 78 L90 110 L96 84 L86 84Z", "@c"))),
        "petals": ("Petals", 1, G(*[E(x, y, 6, 3, "@c", f'transform="rotate({a} {x} {y})"') for x, y, a in [(40, 70, 30), (160, 100, -20), (30, 180, 60), (170, 190, 10), (60, 250, -40), (140, 40, 50)]])),
    },
    "back": {
        "cape": ("Cape", 0, P("M70 122 Q100 112 130 122 L158 262 Q100 280 42 262Z", "@d") + P("M74 128 Q100 120 126 128 L146 250 Q100 266 54 250Z", "@c")),
        "short-cape": ("Short cape", 0, P("M70 122 Q100 112 130 122 L146 200 Q100 212 54 200Z", "@c")),
        "angel": ("Angel wings", 2, P("M70 130 Q10 90 18 170 Q40 160 50 190 Q60 160 72 170Z", "@l") + P("M130 130 Q190 90 182 170 Q160 160 150 190 Q140 160 128 170Z", "@l") + P("M70 130 Q26 108 30 150", "none", 'stroke="@c" stroke-width="3"') + P("M130 130 Q174 108 170 150", "none", 'stroke="@c" stroke-width="3"')),
        "bat": ("Bat wings", 2, P("M70 130 L8 96 L22 130 L10 158 L34 150 L40 180 L56 150 L72 170Z", "@d") + P("M130 130 L192 96 L178 130 L190 158 L166 150 L160 180 L144 150 L128 170Z", "@d")),
        "butterfly": ("Butterfly wings", 2, E(44, 130, 34, 24, "@c", 'transform="rotate(-20 44 130)"') + E(52, 176, 24, 18, "@l", 'transform="rotate(20 52 176)"') + E(156, 130, 34, 24, "@c", 'transform="rotate(20 156 130)"') + E(148, 176, 24, 18, "@l", 'transform="rotate(-20 148 176)"')),
        "backpack": ("Backpack", 0, R(58, 128, 84, 78, "@d", 14) + R(70, 176, 60, 24, "@c", 6)),
        "jetpack": ("Jetpack", 3, R(52, 124, 22, 70, "@d", 8) + R(126, 124, 22, 70, "@d", 8) + P("M54 196 Q63 236 72 196Z", "#ffb020") + P("M128 196 Q137 236 146 196Z", "#ffb020") + R(52, 140, 22, 8, "@c") + R(126, 140, 22, 8, "@c")),
        "shell": ("Shell", 1, E(100, 164, 52, 54, "@d") + P("M100 112 L124 140 L124 182 L100 214 L76 182 L76 140Z", "@c", 'opacity=".7"')),
        "dragonwings": ("Dragon wings", 3, P("M70 132 Q30 80 4 92 Q20 104 14 124 Q30 120 26 144 Q42 136 44 162 Q58 148 72 168Z") + P("M130 132 Q170 80 196 92 Q180 104 186 124 Q170 120 174 144 Q158 136 156 162 Q142 148 128 168Z")
                        + P("M70 132 Q40 104 14 124 M70 140 Q46 130 26 144 M72 150 Q56 148 44 162", "none", 'stroke="@d" stroke-width="2"') + P("M130 132 Q160 104 186 124 M130 140 Q154 130 174 144 M128 150 Q144 148 156 162", "none", 'stroke="@d" stroke-width="2"')),
    },
    "bottom": {
        "jeans": ("Jeans", 0, HIPS + CLIP("@LEGL", "long") + CLIP("@LEGR", "long") + L(88, 214, 88.5, 256, "@d", 1.2) + L(112, 214, 111.5, 256, "@d", 1.2)),
        "shorts": ("Shorts", 0, HIPS + CLIP("@LEGL", "short") + CLIP("@LEGR", "short")),
        "skirt": ("Skirt", 0, P("M73 194 H127 L139 236 Q100 246 61 236Z") + P("M73 194 H127 L128 203 H72Z", "@d")),
        "track": ("Track pants", 0, HIPS + CLIP("@LEGL", "long") + CLIP("@LEGR", "long") + L(80, 210, 80.5, 256, "@l", 3) + L(120, 210, 119.5, 256, "@l", 3)),
        "cargo": ("Cargo pants", 1, HIPS + CLIP("@LEGL", "long") + CLIP("@LEGR", "long") + R(77, 224, 15, 15, "@d", 3) + R(108, 224, 15, 15, "@d", 3)),
        "leggings": ("Leggings", 0, HIPS + CLIP("@LEGL", "ankle") + CLIP("@LEGR", "ankle")),
        "kilt": ("Kilt", 1, P("M73 194 H127 L134 232 Q100 238 66 232Z") + G(*[L(x, 204, x - 2, 232, "@d", 1.6) for x in (82, 92, 100, 108, 118)]) + L(69, 218, 131, 218, "@l", 2)),
        "bermuda": ("Bermudas", 0, HIPS + CLIP("@LEGL", "knee") + CLIP("@LEGR", "knee") + L(86, 238, 95, 238, "@d", 1.5) + L(105, 238, 114, 238, "@d", 1.5)),
        "hakama": ("Hakama", 2, P("M72 194 H128 L142 262 H104 L100 216 L96 262 H58Z") + G(*[L(x, 200, x + (x - 100) * 0.18, 260, "@d", 1.4) for x in (80, 90, 110, 120)]) + R(72, 194, 56, 7, "@d", 2)),
        "tutu": ("Tutu", 2, HIPS + E(100, 216, 42, 11, "@l") + E(100, 212, 38, 10) + G(*[E(x, 222, 6, 3, "@l") for x in range(64, 140, 12)])),
        "flares": ("Flares", 1, HIPS + CLIP("@LEGL", "long") + CLIP("@LEGR", "long") + P("M79 238 L71 263 H96 L96 238Z") + P("M121 238 L129 263 H104 L104 238Z")),
        "greaves": ("Knight greaves", 2, HIPS + CLIP("@LEGL", "long") + CLIP("@LEGR", "long") + C(88, 232, 6, "@l") + C(112, 232, 6, "@l") + L(88, 240, 88, 258, "@d", 2) + L(112, 240, 112, 258, "@d", 2)),
    },
    "shoes": {
        "sneakers": ("Sneakers", 0, E(87, 266, 16, 10, "@c") + E(113, 266, 16, 10, "@c") + R(71, 272, 33, 5, "@l", 2) + R(97, 272, 33, 5, "@l", 2)),
        "boots": ("Boots", 0, R(74, 244, 24, 30, "@c", 5) + R(102, 244, 24, 30, "@c", 5) + R(70, 270, 32, 8, "@d", 3) + R(98, 270, 32, 8, "@d", 3)),
        "sandals": ("Sandals", 0, R(72, 270, 30, 6, "@c", 3) + R(98, 270, 30, 6, "@c", 3) + L(78, 268, 96, 268, "@d", 3) + L(104, 268, 122, 268, "@d", 3)),
        "skates": ("Roller skates", 1, E(87, 262, 15, 9, "@c") + E(113, 262, 15, 9, "@c") + C(76, 278, 4, "@d") + C(98, 278, 4, "@d") + C(102, 278, 4, "@d") + C(124, 278, 4, "@d")),
        "slippers": ("Slippers", 0, E(87, 268, 17, 8, "@c") + E(113, 268, 17, 8, "@c") + E(87, 264, 12, 5, "@l") + E(113, 264, 12, 5, "@l")),
        "hightops": ("High-tops", 1, R(74, 250, 24, 24, "@c", 6) + R(102, 250, 24, 24, "@c", 6) + R(70, 272, 32, 6, "@l", 3) + R(98, 272, 32, 6, "@l", 3) + C(86, 258, 3, "@l") + C(114, 258, 3, "@l")),
        "loafers": ("Loafers", 0, E(86, 268, 17, 8, "@d") + E(114, 268, 17, 8, "@d") + E(80, 266, 4, 2, "@c") + E(120, 266, 4, 2, "@c")),
        "rocket": ("Rocket boots", 3, R(74, 244, 24, 26, "@c", 5) + R(102, 244, 24, 26, "@c", 5) + P("M76 272 Q86 296 96 272Z", "#ffb020") + P("M104 272 Q114 296 124 272Z", "#ffb020")),
        "glass": ("Glass slippers", 3, E(87, 268, 16, 8, "#bfe6ff", 'opacity=".75" stroke="@c" stroke-width="2"') + E(113, 268, 16, 8, "#bfe6ff", 'opacity=".75" stroke="@c" stroke-width="2"') + STAR(80, 262, 5, "#ffffff") + STAR(120, 262, 5, "#ffffff")),
        "cowboy": ("Cowboy boots", 1, R(76, 238, 22, 32, "@c", 5) + R(102, 238, 22, 32, "@c", 5) + R(70, 266, 32, 7, "@d", 3) + R(98, 266, 32, 7, "@d", 3)
                   + P("M80 246 Q87 254 94 246", "none", 'stroke="@l" stroke-width="1.6"') + P("M106 246 Q113 254 120 246", "none", 'stroke="@l" stroke-width="1.6"')),
        "platform": ("Platforms", 2, R(72, 258, 30, 10, "@c", 5) + R(98, 258, 30, 10, "@c", 5) + R(70, 266, 34, 12, "@d", 4) + R(96, 266, 34, 12, "@d", 4)),
    },
    "top": {
        "tee": ("T-shirt", 0, CLIP("@ARML", "sleeve") + CLIP("@ARMR", "sleeve") + P("@TORSO") + NECK),
        "longsleeve": ("Long sleeve", 0, CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + NECK + CUFFS),
        "hoodie": ("Hoodie", 1, CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + CUFFS + P("M80 121 C84 110 116 110 120 121 C112 128 88 128 80 121Z", "@d")
                   + L(94, 126, 93, 146, "@l", 1.6) + L(106, 126, 107, 146, "@l", 1.6) + P("M84 168 H116 L113 188 H87Z", "@d", 'opacity=".55"')),
        "jumper": ("Striped jumper", 0, CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + TORSO_CLIP(G(*[R(60, y, 80, 7, "@l") for y in (140, 158, 176, 194)])) + NECK + CUFFS),
        "labcoat": ("Lab coat", 1, CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("M70 160 L66 234 Q100 240 134 234 L130 160Z") + P("@TORSO") + CUFFS
                    + P("M90 119 L100 150 L110 119", "none", 'stroke="@d" stroke-width="1.6"') + L(100, 150, 100, 236, "@d", 1.6) + C(95, 168, 2.2, "@d") + C(95, 186, 2.2, "@d")
                    + R(108, 170, 14, 12, "@d", 2, 'opacity=".35"')),
        "suit": ("Suit", 1, CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + CUFFS + POLY("89,119 111,119 100,152", "#ffffff")
                 + POLY("98,124 102,124 104.5,150 100,158 95.5,150", "@d") + P("M89 119 L100 152 L84 140Z", "@d", 'opacity=".5"') + P("M111 119 L100 152 L116 140Z", "@d", 'opacity=".5"')),
        "armour": ("Armour", 2, CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + E(68, 132, 15, 11, "@l") + E(132, 132, 15, 11, "@l")
                   + TORSO_CLIP(R(60, 186, 80, 9, "@d")) + L(100, 124, 100, 186, "@d", 2.5) + C(100, 150, 7, "@l")),
        "dress": ("Dress", 1, CLIP("@ARML", "cap") + CLIP("@ARMR", "cap") + P("@TORSO") + P("M76 164 H124 L144 242 Q100 252 56 242Z") + R(76, 160, 48, 7, "@d", 3) + NECK),
        "tank": ("Tank top", 0, TORSO_CLIP(R(60, 128, 80, 90)) + L(86, 120, 82, 130, "@c", 6) + L(114, 120, 118, 130, "@c", 6)),
        "hooped": ("Hooped tee", 0, CLIP("@ARML", "sleeve") + CLIP("@ARMR", "sleeve") + P("@TORSO") + TORSO_CLIP(G(*[R(60, y, 80, 8, "@d") for y in (138, 156, 174, 192)])) + NECK),
        "puffer": ("Puffer jacket", 1, CLIP("@ARML", "wrist", 'stroke="@d" stroke-width="5" stroke-opacity=".25"') + CLIP("@ARMR", "wrist", 'stroke="@d" stroke-width="5" stroke-opacity=".25"')
                   + P("@TORSO", "@c", 'stroke="@d" stroke-width="5" stroke-opacity=".25"') + TORSO_CLIP(G(*[L(60, y, 140, y, "@d", 2.5) for y in (144, 164, 184)])) + L(100, 122, 100, 204, "@d", 2) + CUFFS),
        "poncho": ("Poncho", 2, P("M100 114 C118 114 152 176 156 206 Q100 216 44 206 C48 176 82 114 100 114Z") + G(*[L(x, 204, x + 2, 216, "@l", 3) for x in range(54, 150, 12)]) + NECK),
        # Statement pieces: costumes and couture, cut from the same body outlines so they fit both builds.
        "kimono": ("Kimono", 2, P("M72 196 L68 254 Q100 262 132 254 L128 196Z") + P("M68 130 C56 136 50 162 47 198 L71 202 C72 180 72 160 76 140Z") + P("M132 130 C144 136 150 162 153 198 L129 202 C128 180 128 160 124 140Z")
                   + P("@TORSO") + L(88, 120, 104, 172, "@l", 5) + L(112, 120, 96, 172, "@l", 5) + TORSO_CLIP(R(60, 160, 80, 16, "@d")) + R(95, 156, 10, 24, "@l", 3)),
        "royalrobe": ("Royal robe", 3, P("M70 158 L58 254 Q100 266 142 254 L130 158Z", "@d") + CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + R(94, 124, 12, 136, "#fbfbfd", 3)
                      + G(*[C(100, y, 1.6, "#1b1830") for y in range(134, 256, 14)]) + P("M80 121 C88 135 112 135 120 121 C113 115 87 115 80 121Z", "#fbfbfd") + G(*[C(x, 125, 1.4, "#1b1830") for x in (88, 100, 112)])
                      + '<path d="@ARML" fill="#fbfbfd" clip-path="url(#k-cuff)"/><path d="@ARMR" fill="#fbfbfd" clip-path="url(#k-cuff)"/>'),
        "pirate": ("Pirate coat", 2, P("M70 168 L62 236 L92 236 L100 196 L108 236 L138 236 L130 168Z") + CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + POLY("90,119 110,119 100,150", "#fbfbfd")
                   + TORSO_CLIP(R(60, 182, 80, 8, "#c0392b")) + '<path d="@ARML" fill="@l" clip-path="url(#k-cuff)"/><path d="@ARMR" fill="@l" clip-path="url(#k-cuff)"/>'
                   + G(*[C(x, y, 2.2, "#f2c230") for x in (88, 112) for y in (140, 156, 170)])),
        "astronaut": ("Space suit", 3, CLIP("@ARML", "wrist", 'stroke="@d" stroke-width="4" stroke-opacity=".3"') + CLIP("@ARMR", "wrist", 'stroke="@d" stroke-width="4" stroke-opacity=".3"')
                      + P("@TORSO", "@c", 'stroke="@d" stroke-width="4" stroke-opacity=".3"') + R(86, 140, 28, 18, "@d", 4) + C(93, 149, 2.6, "#ff5f5f") + C(100, 149, 2.6, "#ffd24d") + C(107, 149, 2.6, "#3ddc97")
                      + E(100, 122, 20, 6, "#c0c5ce") + TORSO_CLIP(R(60, 188, 80, 8, "@d")) + CUFFS),
        "hero": ("Hero suit", 2, CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + POLY("100,134 116,148 100,168 84,148", "@l") + POLY("100,141 108,148 100,159 92,148", "@d")
                 + TORSO_CLIP(R(60, 186, 80, 8, "#f2c230")) + '<path d="@ARML" fill="@d" clip-path="url(#k-cuff)"/><path d="@ARMR" fill="@d" clip-path="url(#k-cuff)"/>'),
        "sequin": ("Sequin jacket", 2, CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + TORSO_CLIP(G(*[C(x + (6 if (y // 10) % 2 else 0), y, 1.8, "@l", 'opacity=".85"') for x in range(64, 140, 12) for y in range(124, 206, 10)]))
                   + G(*[C(x, y, 1.5, "@l") for x, y in [(60, 150), (62, 166), (140, 150), (138, 166)]]) + P("M90 119 L100 146 L110 119", "none", 'stroke="@d" stroke-width="2"')),
        "leather": ("Leather jacket", 1, CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + POLY("86,120 98,120 92,140", "@d") + POLY("114,120 102,120 108,140", "@d")
                    + L(96, 124, 106, 202, "#c0c5ce", 2) + TORSO_CLIP(R(60, 192, 80, 7, "@d")) + C(80, 150, 1.8, "#c0c5ce") + C(120, 150, 1.8, "#c0c5ce")),
        "tuxedo": ("Tailcoat", 2, P("M76 186 L70 246 L98 204Z") + P("M124 186 L130 246 L102 204Z") + CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + POLY("88,119 112,119 100,166", "#fbfbfd")
                   + POLY("92,124 100,128 92,132", "#15131c") + POLY("108,124 100,128 108,132", "#15131c") + C(100, 146, 1.6, "#15131c") + C(100, 156, 1.6, "#15131c")
                   + '<path d="@ARML" fill="#fbfbfd" clip-path="url(#k-cuff)"/><path d="@ARMR" fill="#fbfbfd" clip-path="url(#k-cuff)"/>'),
        "ballgown": ("Ball gown", 3, P("M78 162 C60 190 46 232 40 264 Q100 282 160 264 C154 232 140 190 122 162Z") + P("M70 238 Q100 252 130 238", "none", 'stroke="@l" stroke-width="3"')
                     + P("M58 256 Q100 272 142 256", "none", 'stroke="@l" stroke-width="3"') + P("@TORSO") + E(70, 134, 11, 10, "@l") + E(130, 134, 11, 10, "@l") + R(78, 158, 44, 7, "@d", 3)
                     + G(*[C(x, 160, 1.6, "#fff") for x in (86, 94, 100, 106, 114)])),
        "ninja": ("Ninja gi", 2, CLIP("@ARML", "wrist") + CLIP("@ARMR", "wrist") + P("@TORSO") + L(88, 120, 110, 170, "@d", 3) + L(112, 120, 96, 150, "@d", 3) + TORSO_CLIP(R(60, 166, 80, 10, "@l"))
                  + R(110, 168, 6, 22, "@l", 2) + CUFFS),
    },
    "face": {
        "round": ("Round glasses", 0, C(88, 76, 11, "none", 'stroke="@c" stroke-width="3"') + C(112, 76, 11, "none", 'stroke="@c" stroke-width="3"') + L(99, 76, 101, 76, "@c", 3)),
        "square": ("Square glasses", 0, R(76, 66, 22, 18, "none", 4, 'stroke="@c" stroke-width="3"') + R(102, 66, 22, 18, "none", 4, 'stroke="@c" stroke-width="3"') + L(98, 74, 102, 74, "@c", 3)),
        "shades": ("Sunglasses", 1, R(75, 66, 24, 17, "@c", 6) + R(101, 66, 24, 17, "@c", 6) + L(99, 72, 101, 72, "@c", 3)),
        "monocle": ("Monocle", 1, C(112, 76, 12, "none", 'stroke="@c" stroke-width="3"') + L(112, 88, 118, 122, "@c", 2)),
        "moustache": ("Moustache", 0, P("M84 94 Q92 86 100 94 Q108 86 116 94 Q108 100 100 96 Q92 100 84 94Z", "@c")),
        "eyepatch": ("Eyepatch", 1, C(88, 76, 10, "@c") + L(62, 62, 138, 84, "@c", 2)),
        "mask": ("Face mask", 0, R(72, 86, 56, 26, "@c", 10) + L(66, 90, 74, 92, "@d", 2) + L(134, 90, 126, 92, "@d", 2)),
        "freckles": ("Freckles", 0, G(*[C(x, y, 1.6, "@d") for x, y in [(78, 88), (84, 91), (80, 94), (116, 88), (122, 91), (118, 94)]])),
        "blush": ("Blush", 0, E(76, 90, 8, 5, "@c", 'opacity=".55"') + E(124, 90, 8, 5, "@c", 'opacity=".55"')),
        "glasses3d": ("3D glasses", 2, R(75, 66, 24, 17, "@c", 3) + R(101, 66, 24, 17, "@d", 3) + L(99, 72, 101, 72, "@l", 3)),
        "paint": ("Face paint", 1, L(72, 84, 82, 96, "@c", 3) + L(76, 82, 86, 94, "@c", 3) + L(128, 84, 118, 96, "@c", 3) + L(124, 82, 114, 94, "@c", 3)),
        "bandage": ("Bandage", 0, R(94, 82, 18, 8, "@c", 3, 'transform="rotate(-18 103 86)"')),
    },
    "hair": {
        "short": ("Short hair", 0, BACK + FRONT_SHORT),
        "long": ("Long hair", 0, P("M60 84 C56 44 80 36 100 36 C120 36 144 44 140 84 C142 112 146 140 140 156 C120 162 80 162 60 156 C54 140 58 112 60 84Z") + BACK + FRONT_PART
                 + P("M64 76 C60 100 62 126 66 146 L74 142 C70 120 69 98 71 80Z") + P("M136 76 C140 100 138 126 134 146 L126 142 C130 120 131 98 129 80Z")),
        "bun": ("Bun", 0, C(100, 34, 15) + C(100, 34, 8, "@d", 'opacity=".25"') + BACK + FRONT_PART),
        "spiky": ("Spiky hair", 1, BACK + P("M63 84 C61 66 62 56 66 48 L62 36 L76 42 L78 26 L90 38 L100 22 L110 38 L122 26 L124 42 L138 36 L134 48 C138 56 139 66 137 84 C132 72 126 64 118 60 C106 66 92 66 82 60 C74 64 68 72 63 84Z")),
        "mohawk": ("Mohawk", 1, P("M64 82 C62 60 72 48 86 44 L114 44 C128 48 138 60 136 82 C130 66 118 58 100 58 C82 58 70 66 64 82Z", "@c", 'opacity=".3"')
                   + P("M90 58 C88 40 92 24 100 14 C108 24 112 40 110 58Z")),
        "afro": ("Afro", 1, G(*[C(100 + 46 * __import__("math").cos(a / 10), 70 + 40 * __import__("math").sin(a / 10), 17) for a in range(-31, 1, 4)]) + C(100, 60, 40) + "|||"
                 + P("M66 84 C64 62 76 50 100 50 C124 50 136 62 134 84 C128 70 116 62 100 62 C84 62 72 70 66 84Z")),
        "bob": ("Bob", 0, P("M60 84 C56 44 80 36 100 36 C120 36 144 44 140 84 L142 116 C126 122 74 122 58 116Z") + "|||"
                + P("M64 84 C60 50 80 40 100 40 C120 40 140 50 136 84 L134 68 C120 60 80 60 66 68Z")
                + P("M62 80 L60 116 L72 116 L70 84Z") + P("M138 80 L140 116 L128 116 L130 84Z")),
        "ponytail": ("Ponytail", 0, P("M124 52 C160 54 166 104 150 144 C146 120 144 90 128 70Z") + C(127, 58, 6, "@d") + BACK + FRONT_SWEPT),
        "pigtails": ("Pigtails", 0, E(54, 104, 12, 24) + E(146, 104, 12, 24) + C(60, 82, 5, "@d") + C(140, 82, 5, "@d") + BACK + FRONT_PART),
        "curly": ("Curly hair", 0, G(*[C(x, y, 13) for x, y in [(64, 76), (68, 56), (82, 44), (100, 39), (118, 44), (132, 56), (136, 76), (62, 96), (138, 96)]]) + "|||"
                  + G(*[C(x, y, 9) for x, y in [(72, 60), (86, 52), (100, 50), (114, 52), (128, 60)]])),
        "buzz": ("Buzz cut", 0, "|||" + P("M64 80 C62 56 78 44 100 44 C122 44 138 56 136 80 C128 64 116 58 100 58 C84 58 72 64 64 80Z", "@c", 'opacity=".7"')),
        "fringe": ("Fringe", 0, BACK + P("M63 86 C59 50 80 38 100 38 C120 38 141 50 137 86 C136 76 134 70 132 68 C112 72 88 72 68 68 C66 72 64 78 63 86Z")),
    },
    "hat": {
        "cap": ("Cap", 0, P("M64 58 Q66 28 100 28 Q134 28 136 58Z") + P("M60 58 L128 58 Q150 58 154 66 L60 66Z", "@d")),
        "beanie": ("Beanie", 0, P("M64 58 Q66 24 100 24 Q134 24 136 58Z") + R(62, 52, 76, 12, "@d", 5) + C(100, 20, 8, "@l")),
        "wizard": ("Wizard hat", 2, POLY("100,-4 130,56 70,56") + E(100, 58, 48, 8, "@d") + STAR(100, 36, 7, "@l")),
        "crown": ("Crown", 2, P("M66 56 L66 28 L82 42 L100 22 L118 42 L134 28 L134 56Z", "@c") + C(100, 22, 4, "@l") + C(66, 28, 4, "@l") + C(134, 28, 4, "@l") + R(66, 50, 68, 6, "@d")),
        "tophat": ("Top hat", 1, R(74, 8, 52, 46, "@c", 4) + E(100, 56, 52, 8, "@c") + R(74, 40, 52, 8, "@d")),
        "halo": ("Halo", 2, E(100, 24, 28, 7, "none", 'stroke="@c" stroke-width="5"')),
        "party": ("Party hat", 0, POLY("100,0 120,52 80,52") + C(100, 2, 5, "@l") + G(*[C(x, y, 2.5, "@l") for x, y in [(98, 22), (92, 38), (108, 36)]]) + E(100, 54, 22, 4, "@d")),
        "gradcap": ("Graduation cap", 1, POLY("100,20 150,38 100,56 50,38") + P("M78 46 L78 60 Q100 70 122 60 L122 46 L100 56Z", "@d") + L(144, 40, 144, 70, "@l", 2) + C(144, 72, 4, "@l")),
        "chef": ("Chef hat", 0, G(C(80, 30, 16, "@c"), C(100, 22, 18, "@c"), C(120, 30, 16, "@c"), R(78, 34, 44, 22, "@c"), R(76, 50, 48, 8, "@d", 2))),
        "cowboy": ("Cowboy hat", 1, E(100, 56, 58, 8, "@d") + P("M72 56 Q72 26 100 30 Q128 26 128 56Z") + R(72, 48, 56, 6, "@l")),
        "helmet": ("Helmet", 1, P("M62 66 Q60 24 100 24 Q140 24 138 66Z") + R(94, 24, 12, 42, "@l") + R(60, 60, 80, 8, "@d", 3)),
        "headphones": ("Headphones", 1, P("M62 84 Q60 26 100 26 Q140 26 138 84", "none", 'stroke="@d" stroke-width="6"') + R(54, 70, 14, 28, "@c", 6) + R(132, 70, 14, 28, "@c", 6)),
        "bow": ("Hair bow", 0, POLY("100,44 76,32 76,56", "@c") + POLY("100,44 124,32 124,56", "@c") + C(100, 44, 6, "@d")),
        "flowers": ("Flower crown", 1, G(*[C(x, y, 7, "@c") + C(x, y, 2.5, "@l") for x, y in [(70, 56), (84, 44), (100, 40), (116, 44), (130, 56)]])),
        "catears": ("Cat ears", 1, POLY("66,52 72,22 92,42", "@c") + POLY("134,52 128,22 108,42", "@c") + POLY("72,44 74,32 84,42", "@l") + POLY("128,44 126,32 116,42", "@l")),
        "tiara": ("Tiara", 2, P("M76 52 L82 38 L90 46 L100 30 L110 46 L118 38 L124 52 Q100 46 76 52Z") + C(100, 40, 3.6, "@l") + C(84, 45, 2.2, "@l") + C(116, 45, 2.2, "@l")),
        "tricorn": ("Tricorn", 2, P("M52 56 Q76 22 100 30 Q124 22 148 56 Q100 44 52 56Z") + P("M56 54 Q100 42 144 54", "none", 'stroke="#f2c230" stroke-width="2.5"')),
        "viking": ("Viking helmet", 2, P("M66 50 Q44 40 48 14 Q56 36 74 42Z", "#f4e8d4") + P("M134 50 Q156 40 152 14 Q144 36 126 42Z", "#f4e8d4") + P("M64 62 Q64 28 100 28 Q136 28 136 62Z") + R(62, 56, 76, 9, "@d", 3)
                   + G(*[C(x, 60.5, 1.8, "@l") for x in (72, 86, 100, 114, 128)])),
        "jester": ("Jester hat", 2, P("M66 60 Q60 30 38 28 Q70 18 100 30 Q130 18 162 28 Q140 30 134 60Z") + P("M100 30 Q96 14 100 6 Q104 14 100 30Z", "@d") + R(64, 54, 72, 9, "@d", 3)
                   + C(38, 28, 5, "#f2c230") + C(162, 28, 5, "#f2c230") + C(100, 6, 5, "#f2c230")),
        "astro": ("Space helmet", 3, C(100, 78, 47, "#bfe6ff", 'opacity=".28" stroke="@c" stroke-width="5"') + P("M70 54 Q84 40 104 38", "none", 'stroke="#ffffff" stroke-width="4" stroke-linecap="round" opacity=".7"')),
    },
    "held": {
        "book": ("Book", 0, R(140, 176, 30, 38, "@c", 3) + R(144, 180, 22, 30, "@l", 1) + R(140, 176, 6, 38, "@d", 2)),
        "pencil": ("Pencil", 0, '<g transform="rotate(30 150 170)">' + R(146, 130, 9, 56, "@c") + POLY("146,186 155,186 150.5,200", "#f1d4a8") + R(146, 124, 9, 8, "@d") + '</g>'),
        "trophy": ("Trophy", 1, P("M138 156 H164 V176 Q164 190 151 190 Q138 190 138 176Z") + R(147, 190, 8, 10, "@d") + R(140, 200, 22, 6, "@d", 2) + P("M138 160 Q128 160 130 172 Q134 178 140 176", "none", 'stroke="@c" stroke-width="3"') + P("M164 160 Q174 160 172 172 Q168 178 162 176", "none", 'stroke="@c" stroke-width="3"')),
        "flask": ("Flask", 1, P("M146 150 H158 V168 L172 202 Q174 210 166 210 H138 Q130 210 132 202 L146 168Z", "#ffffff", 'opacity=".7" stroke="@d" stroke-width="3"') + P("M138 190 H166 L172 202 Q174 210 166 210 H138 Q130 210 132 202Z", "@c")),
        "telescope": ("Telescope", 1, '<g transform="rotate(-35 150 180)">' + R(126, 172, 50, 16, "@c", 4) + R(112, 175, 18, 10, "@d", 3) + R(170, 170, 12, 20, "@d", 3) + '</g>'),
        "wand": ("Wand", 2, L(142, 204, 168, 150, "@d", 5) + STAR(170, 146, 11, "@c")),
        "balloon": ("Balloon", 0, L(146, 194, 156, 130, "#888", 1.5) + E(158, 112, 17, 21, "@c") + POLY("158,133 154,140 162,140", "@d")),
        "magnifier": ("Magnifier", 1, C(158, 170, 15, "#ffffff", 'opacity=".55" stroke="@c" stroke-width="5"') + L(148, 182, 138, 200, "@d", 6)),
        "coffee": ("Coffee", 0, R(142, 176, 24, 26, "@c", 4) + P("M166 182 Q178 184 166 196", "none", 'stroke="@c" stroke-width="4"') + P("M148 170 Q152 162 148 156 M158 170 Q162 162 158 156", "none", 'stroke="@l" stroke-width="2.5"')),
        "calculator": ("Calculator", 0, R(140, 168, 28, 40, "@c", 4) + R(144, 172, 20, 8, "@l", 1) + G(*[R(144 + 7 * i, 184 + 7 * j, 5, 5, "@d", 1) for i in range(3) for j in range(3)])),
        "sword": ("Sword", 2, L(142, 202, 168, 140, "@c", 6) + L(136, 190, 156, 200, "@d", 5)),
        "lollipop": ("Lollipop", 0, L(146, 204, 156, 160, "#e8e8e8", 3) + C(158, 146, 15, "@c") + P("M158 146 m-9 0 a9 9 0 1 1 9 9", "none", 'stroke="@l" stroke-width="3"')),
    },
    "pet": {
        "cat": ("Cat", 0, '<g transform="translate(142 240)">' + E(20, 26, 18, 14) + C(18, 8, 12) + POLY("8,0 10,-12 18,0") + POLY("28,0 26,-12 18,0") + C(14, 8, 1.8, "#222") + C(22, 8, 1.8, "#222") + P("M38 26 Q52 20 46 8", "none", 'stroke="@c" stroke-width="5"') + '</g>'),
        "dog": ("Dog", 0, '<g transform="translate(142 240)">' + E(20, 26, 19, 13) + C(18, 8, 12) + E(8, 8, 5, 10, "@d") + E(28, 8, 5, 10, "@d") + C(14, 8, 1.8, "#222") + C(22, 8, 1.8, "#222") + E(18, 13, 3, 2, "#222") + '</g>'),
        "bunny": ("Bunny", 0, '<g transform="translate(142 240)">' + E(20, 28, 16, 12) + C(20, 12, 10) + E(14, -6, 4, 14) + E(26, -6, 4, 14) + C(16, 12, 1.6, "#222") + C(24, 12, 1.6, "#222") + '</g>'),
        "slime": ("Slime", 0, '<g transform="translate(142 244)">' + P("M0 36 Q0 6 20 6 Q40 6 40 36Z", "@c", 'opacity=".85"') + C(14, 22, 2.5, "#222") + C(26, 22, 2.5, "#222") + E(14, 14, 5, 3, "@l", 'opacity=".7"') + '</g>'),
        "owl": ("Owl", 1, '<g transform="translate(144 232)">' + E(18, 28, 16, 22) + C(11, 18, 8, "#fff") + C(25, 18, 8, "#fff") + C(11, 18, 3.5, "#222") + C(25, 18, 3.5, "#222") + POLY("14,24 22,24 18,32", "#f0a030") + POLY("4,8 8,0 12,10", "@d") + POLY("32,8 28,0 24,10", "@d") + '</g>'),
        "robot": ("Robot", 2, '<g transform="translate(142 232)">' + R(8, 14, 30, 26, "@c", 4) + R(12, 0, 22, 16, "@l", 4) + C(18, 8, 2.5, "#222") + C(28, 8, 2.5, "#222") + L(23, 0, 23, -8, "@d", 2) + C(23, -9, 2.5, "@d") + R(2, 40, 10, 8, "@d", 2) + R(34, 40, 10, 8, "@d", 2) + '</g>'),
        "ghost": ("Ghost", 1, '<g transform="translate(142 234)">' + P("M2 44 L2 18 Q2 0 20 0 Q38 0 38 18 L38 44 L30 38 L22 44 L14 38Z", "@c", 'opacity=".85"') + C(14, 18, 3, "#222") + C(26, 18, 3, "#222") + '</g>'),
        "dragon": ("Dragon", 3, '<g transform="translate(140 228)">' + E(24, 30, 20, 16) + C(40, 14, 11) + POLY("36,6 38,-4 44,6", "@d") + POLY("12,18 -2,6 18,12", "@d") + POLY("34,20 46,12 38,26", "@l") + P("M6 34 Q-8 38 -4 50 Q8 44 10 38", "@c") + C(43, 12, 1.8, "#222") + '</g>'),
        "chick": ("Chick", 0, '<g transform="translate(146 246)">' + C(16, 20, 14) + C(16, 6, 9) + POLY("12,6 20,6 16,12", "#f0a030") + C(13, 4, 1.4, "#222") + C(19, 4, 1.4, "#222") + '</g>'),
        "fishbowl": ("Fish bowl", 1, '<g transform="translate(142 240)">' + C(20, 24, 18, "#bfe6ff", 'opacity=".55" stroke="#8ab" stroke-width="2"') + E(20, 24, 7, 4, "@c") + POLY("26,24 33,18 33,30", "@c") + C(16, 23, 1.2, "#222") + '</g>'),
        "mushroom": ("Mushroom", 0, '<g transform="translate(148 238)">' + R(12, 20, 12, 22, "#f4e8d4", 4) + P("M0 24 Q0 0 18 0 Q36 0 36 24Z", "@c") + C(10, 12, 3, "#fff") + C(22, 8, 3, "#fff") + C(28, 16, 2.4, "#fff") + '</g>'),
        "penguin": ("Penguin", 1, '<g transform="translate(144 232)">' + E(18, 26, 15, 22, "@d") + E(18, 30, 9, 15, "#fff") + C(13, 16, 2, "#fff") + C(23, 16, 2, "#fff") + C(13, 16, 1, "#222") + C(23, 16, 1, "#222") + POLY("14,21 22,21 18,26", "#f0a030") + E(10, 50, 6, 3, "#f0a030") + E(26, 50, 6, 3, "#f0a030") + '</g>'),
    },
    "trinket": {
        "pi": ("Pi", 0, T(100, 188, "π", 130)),
        "sigma": ("Sigma", 0, T(100, 188, "Σ", 130)),
        "infinity": ("Infinity", 0, T(100, 184, "∞", 140)),
        "emc2": ("E = mc²", 1, T(100, 168, "E=mc²", 52)),
        "h2o": ("H₂O", 0, T(100, 168, "H₂O", 64)),
        "atom": ("Atom", 1, G(E(100, 150, 60, 22, "none", 'stroke="@c" stroke-width="5"'), E(100, 150, 60, 22, "none", 'stroke="@c" stroke-width="5" transform="rotate(60 100 150)"'), E(100, 150, 60, 22, "none", 'stroke="@c" stroke-width="5" transform="rotate(120 100 150)"'), C(100, 150, 10, "@d"))),
        "dna": ("DNA", 1, P("M70 80 C130 110 70 150 130 180 S70 220 130 250", "none", 'stroke="@c" stroke-width="7"') + P("M130 80 C70 110 130 150 70 180 S130 220 70 250", "none", 'stroke="@d" stroke-width="7"') + G(*[L(80, y, 120, y, "@l", 4) for y in (96, 150, 205)])),
        "planet": ("Planet", 1, C(100, 150, 42, "@c") + E(100, 150, 74, 16, "none", 'stroke="@l" stroke-width="7" transform="rotate(-20 100 150)"')),
        "star": ("Star", 0, STAR(100, 150, 72, "@c")),
        "bulb": ("Light bulb", 0, C(100, 134, 40, "@c") + R(84, 168, 32, 24, "@d", 5) + R(88, 194, 24, 8, "@d", 3)),
        "rocket": ("Rocket", 2, P("M100 70 Q132 110 124 180 L76 180 Q68 110 100 70Z") + C(100, 126, 12, "@l") + POLY("76,160 54,196 80,186", "@d") + POLY("124,160 146,196 120,186", "@d") + P("M88 184 Q100 230 112 184Z", "#ffb020")),
        "book": ("Book", 0, R(66, 90, 68, 90, "@c", 6) + R(74, 98, 52, 74, "@l", 3) + R(66, 90, 12, 90, "@d", 4)),
        "magnet": ("Magnet", 1, P("M66 90 V150 A34 34 0 0 0 134 150 V90 H112 V150 A12 12 0 0 1 88 150 V90Z") + R(66, 90, 22, 20, "#eee") + R(112, 90, 22, 20, "#eee")),
        "medal": ("Medal", 2, POLY("78,70 100,70 100,116 88,116", "@d") + POLY("122,70 100,70 100,116 112,116", "@l") + C(100, 150, 34, "@c") + STAR(100, 150, 18, "@l")),
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


def fill(markup, item_id=None, skin=None, build=None):
    """Fill the body-part and colour placeholders of one drawing for the build, the item's colour and the skin."""
    markup = geometry(markup, build)
    colour = COLOURS[CATALOG[item_id]["colour"]] if item_id else COLOURS["grey"]
    _, c, d, l, _ = colour
    return markup.replace("@c", c).replace("@d", d).replace("@l", l).replace("@s", SKINS.get(skin, SKINS[DEFAULT_SKIN])[1])


def drawing(item_id, skin=None, build=None):
    item = CATALOG[item_id]
    markup = fill(STYLES[item["slot"]][item["style"]][2], item_id, skin, build).replace("|||", "")
    if item["slot"] in ("trinket", "background"):
        return markup
    # A soft ink outline on every filled shape gives the cartoon look; shapes that set their own stroke keep it.
    return f'<g stroke="#1b1830" stroke-opacity=".38" stroke-width="1.6" stroke-linejoin="round">{markup}</g>'


def shade(colour, factor):
    """`colour` (#rrggbb) moved towards black (factor < 1) or white (factor > 1)."""
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    if factor < 1:
        r, g, b = (round(v * factor) for v in (r, g, b))
    else:
        r, g, b = (round(v + (255 - v) * (factor - 1)) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


INK = "#2a2338"


BUILDS = {"masculine": "Masculine", "feminine": "Feminine"}
DEFAULT_BUILD = "masculine"
# What a character has in a slot with nothing equipped: (style, colour) per build. Under everything both builds wear swimwear
# (`swimwear`), so an undressed character is in board shorts or a sporty two-piece.
STARTER = {
    "masculine": {"hair": ("short", "brown"), "shoes": ("sneakers", "white")},
    "feminine": {"hair": ("long", "brown"), "shoes": ("sneakers", "white")},
}
# Each build's outline of the parts clothes follow, and where its hands are.
GEOMETRY = {
    "masculine": {
        "@TORSO": "M86 118 C76 119 68 123 66 133 C67 150 69 168 70 184 C71 194 72 200 73 205 L127 205 C128 200 129 194 130 184 C131 168 133 150 134 133 C132 123 124 119 114 118Z",
        "@ARML": "M67 130 C60 138 57 160 56 186 C56 193 66 194 66.5 187 C68 166 71 150 76 140Z",
        "@ARMR": "M133 130 C140 138 143 160 144 186 C144 193 134 194 133.5 187 C132 166 129 150 124 140Z",
        "@LEGL": "M77 198 C76 222 77 244 79 263 C83 266 92 266 95 263 C96 244 98 222 99.5 204Z",
        "@LEGR": "M123 198 C124 222 123 244 121 263 C117 266 108 266 105 263 C104 244 102 222 100.5 204Z",
        "hands": ((61, 191, 7.5), (139, 191, 7.5)),
    },
    "feminine": {
        "@TORSO": "M88 118 C79 119 72 123 71 133 C71 148 77 158 80 168 C75 180 70 192 70 205 L130 205 C130 192 125 180 120 168 C123 158 129 148 129 133 C128 123 121 119 112 118Z",
        "@ARML": "M72 130 C65 138 62 160 61 186 C61 192 70 193 70.5 187 C72 166 75 150 79 140Z",
        "@ARMR": "M128 130 C135 138 138 160 139 186 C139 192 130 193 129.5 187 C128 166 125 150 121 140Z",
        "@LEGL": "M78 198 C77 222 79 244 81 263 C84 266 92 266 94 263 C96 244 98 222 99.5 204Z",
        "@LEGR": "M122 198 C123 222 121 244 119 263 C116 266 108 266 106 263 C104 244 102 222 100.5 204Z",
        "hands": ((65.5, 191, 6.8), (134.5, 191, 6.8)),
    },
}
IRIS = "#5a3e2b"


def geometry(markup, build):
    shapes = GEOMETRY.get(build, GEOMETRY[DEFAULT_BUILD])
    for token in ("@TORSO", "@ARML", "@ARMR", "@LEGL", "@LEGR"):
        markup = markup.replace(token, shapes[token])
    return markup


def defs(build):
    """Gradients and filters every picture uses, and the clip paths that cut sleeves and legs for this build."""
    shapes = GEOMETRY.get(build, GEOMETRY[DEFAULT_BUILD])
    clips = "".join(f'<clipPath id="k-{name}"><rect x="-50" y="-50" width="300" height="{y + 50}"/></clipPath>' for name, y in CUTS.items())
    clips += '<clipPath id="k-cuff"><rect x="-50" y="177" width="300" height="7"/></clipPath>'
    clips += f'<clipPath id="k-torso"><path d="{shapes["@TORSO"]}"/></clipPath>'
    return DEFS.replace("</defs>", clips + "</defs>")


def eye(x, feminine):
    """One eye: white, iris, pupil and two highlights; a lid flick on the feminine build."""
    flick = ""
    if feminine:
        side = -1 if x < 100 else 1
        flick = P(f"M{x + side * 6} 74.5 Q{x + side * 8.5} 73.5 {x + side * 10} 71", "none", f'stroke="{INK}" stroke-width="2" stroke-linecap="round"')
    return G(E(x, 79, 6.4, 7.4, "#fff", f'stroke="{INK}" stroke-opacity=".25" stroke-width="1"'), C(x + 0.6, 80, 4.8, IRIS), C(x + 0.6, 80, 2.5, INK),
             C(x + 2.3, 77.4, 1.7, "#fff"), C(x - 1.2, 82.4, 0.8, "#fff"),
             P(f"M{x - 6.6} 76 Q{x} 70.2 {x + 6.6} 76", "none", f'stroke="{INK}" stroke-width="{2.6 if feminine else 1.8}" stroke-linecap="round"'), flick)


def body(skin, build=None, face=True):
    """The character's body in a skin tone (a SKINS key, or a #rrggbb colour); without a face it is the plain mannequin of item icons."""
    build = build if build in BUILDS else DEFAULT_BUILD
    shapes = GEOMETRY[build]
    s = skin if str(skin).startswith("#") else SKINS.get(skin, SKINS[DEFAULT_SKIN])[1]
    o, lit = shade(s, 0.72), shade(s, 1.16)
    feminine = build == "feminine"
    line = f'stroke="{o}" stroke-width="2" stroke-linejoin="round"'
    brows = ("M80 66 Q87 61.5 95 65", "M105 65 Q113 61.5 120 66") if feminine else ("M79 67 Q87 63.5 95 66", "M105 66 Q113 63.5 121 67")
    brow = f'stroke="{shade(s, 0.45)}" stroke-width="{2.2 if feminine else 3.2}" stroke-linecap="round"'
    mouth = (P("M92 95 Q100 103 108 95 Q100 98.5 92 95Z", "#d9566b", f'stroke="{shade("#d9566b", 0.7)}" stroke-width="1.2" stroke-linejoin="round"') if feminine
             else P("M91 95 Q100 103 109 95", "none", f'stroke="{INK}" stroke-width="2.8" stroke-linecap="round"'))
    (lx, ly, lr), (rx, ry, rr) = shapes["hands"]
    blush = .4 if feminine else .25
    return G(
        P(shapes["@LEGL"], s, line), P(shapes["@LEGR"], s, line),
        P(shapes["@ARML"], s, line), P(shapes["@ARMR"], s, line), C(lx, ly, lr, s, line), C(rx, ry, rr, s, line),
        P(shapes["@TORSO"], s, line),
        R(93, 106, 14, 18, s, 6, line), R(93, 114, 14, 6, o, 3, 'opacity=".35"'),                                # neck and its shadow
        E(64.5, 83, 5.5, 8.5, s, line), E(135.5, 83, 5.5, 8.5, s, line),                                        # ears
        E(100, 79, 36, 35, s, line), E(88, 60, 15, 8, lit, 'opacity=".5"'), E(100, 107, 22, 5, o, 'opacity=".12"'),
    ) + (G(
        P(brows[0], "none", brow), P(brows[1], "none", brow),
        eye(88, feminine), eye(112, feminine),
        P("M98.5 85 Q100 88.5 102 86.5", "none", f'stroke="{o}" stroke-width="2" stroke-linecap="round"'),          # nose
        mouth,
        E(77, 92, 6.5, 4, "#ff7a8a", f'opacity="{blush}"'), E(123, 92, 6.5, 4, "#ff7a8a", f'opacity="{blush}"'),
    ) if face else "")


def swimwear(build):
    """The base layer every character wears under their clothes: board shorts, or a sporty two-piece (crop top and swim shorts)."""
    ink = 'stroke="#1b1830" stroke-opacity=".38" stroke-width="1.6" stroke-linejoin="round"'
    if build == "feminine":
        suit, trim = "#e0607e", "#b3405c"
        top = TORSO_CLIP(R(60, 128, 80, 34, suit)) + L(86, 121, 84, 132, suit, 5) + L(114, 121, 116, 132, suit, 5) + R(76, 157, 48, 5, trim, 2)
        legs = "".join(f'<path d="{part}" fill="{suit}" clip-path="url(#k-short)"/>' for part in ("@LEGL", "@LEGR"))
        bottoms = P("M71 194 H129 L130 212 H70Z", suit) + legs + R(71, 194, 58, 5, trim, 2)
        return geometry(f"<g {ink}>{top}{bottoms}</g>", build)
    shorts, stripe = "#2b5aa8", "#f2c230"
    return geometry(f'<g {ink}>' + P("M73 193 H127 L129 212 H71Z", shorts) + '<path d="@LEGL" fill="' + shorts + '" clip-path="url(#k-short)"/>'
                    + '<path d="@LEGR" fill="' + shorts + '" clip-path="url(#k-short)"/>' + L(78, 200, 78, 226, stripe, 3) + L(122, 200, 122, 226, stripe, 3)
                    + R(73, 193, 54, 6, "#1e3f78", 2) + "</g>", build)


def hair_layers(item_id, skin=None, build=None):
    """(behind the head, in front of it) for a hair item."""
    markup = fill(STYLES["hair"][CATALOG[item_id]["style"]][2], item_id, skin, build)
    back, _, front = markup.rpartition("|||") if "|||" in markup else ("", "", markup)
    wrap = lambda m: f'<g stroke="#1b1830" stroke-opacity=".38" stroke-width="1.6" stroke-linejoin="round">{m}</g>' if m else ""
    return wrap(back.replace("|||", "")), wrap(front)


GROUND = E(100, 279, 52, 7, "#000", 'opacity=".18"')
CROPS = {"hat": "44 0 112 96", "hair": "28 8 144 144", "face": "56 54 88 56", "top": "36 100 128 150", "bottom": "50 180 100 100",
         "shoes": "56 236 88 52", "held": "104 120 96 110", "pet": "128 206 72 84"}
FULL_COVER_HATS = ("helmet", "beanie", "tophat", "chef", "viking")


def avatar_svg(outfit, skin=None, size=None, crop=None, build=None):
    """The whole character. `outfit` maps a slot to an item id; unknown or non-wearable entries are ignored, and an empty hair, top,
    bottom or shoes slot shows the build's starter piece instead."""
    build = build if build in BUILDS else DEFAULT_BUILD
    starter = STARTER[build]
    wearing = lambda slot: outfit.get(slot) if outfit.get(slot) in CATALOG and CATALOG[outfit[slot]]["slot"] == slot else None
    hair = wearing("hair")
    if not hair and not (wearing("hat") and CATALOG[wearing("hat")]["style"] in FULL_COVER_HATS):
        hair = "hair.{}.{}".format(*starter["hair"])
    back, front = hair_layers(hair, skin, build) if hair else ("", "")
    layers = []
    for slot in LAYER_ORDER:
        if slot == "BODY":
            layers.append(back + GROUND + body(skin, build) + swimwear(build))
        elif slot == "hair":
            layers.append(front)
        elif wearing(slot):
            layers.append(drawing(wearing(slot), skin, build))
        elif slot in starter:
            layers.append(drawing("{}.{}.{}".format(slot, *starter[slot]), skin, build))
    return _wrap("".join(layers), crop or "0 0 200 300", size, build)


def _wrap(inner, view, size=None, build=None):
    w, h = [float(x) for x in view.split()[2:]]
    dims = f' width="{size}" height="{round(size * h / w)}"' if size else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}"{dims}>{defs(build)}{inner}</svg>'


MANNEQUIN = lambda: GROUND + body("#e2e5ee", face=False)     # the plain stand item icons are shown on


def item_svg(item_id, skin=None):
    """An item on its own, on a transparent ground so the page can colour it by rarity: trinkets as a card, wearables on a faded
    mannequin cropped to where the item sits, backgrounds as a small scene."""
    item = CATALOG[item_id]
    slot = item["slot"]
    if slot == "trinket":
        pale = item["colour"] in LIGHT_COLOURS
        top, bottom = ("#3a3550", "#221f33") if pale else ("#fffdf6", "#efe9da")
        card = (f'<linearGradient id="card" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>'
                + R(10, 10, 180, 280, "url(#card)", 20, 'stroke="#000" stroke-opacity=".13" stroke-width="2"') + R(20, 20, 160, 260, "none", 14, 'stroke="#fff" stroke-opacity=".35" stroke-width="2"'))
        return _wrap(card + drawing(item_id, skin), "0 0 200 300")
    mannequin = MANNEQUIN()
    if slot == "background":
        return _wrap(drawing(item_id) + '<g opacity=".5">' + GROUND + body(skin) + "</g>", "0 0 200 300")
    if slot == "hair":
        back, front = hair_layers(item_id, skin)
        return _wrap(back + mannequin + front, CROPS["hair"])
    return _wrap(mannequin + drawing(item_id, skin), CROPS.get(slot, "0 0 200 300"))


def png(svg, width):
    """The SVG drawn as a PNG `width` pixels wide (for the Android app, which has no SVG renderer)."""
    import cairosvg
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=width)
