"""The rewards catalogue and its art.

Every item is a style (a shape such as "wizard hat") in a colour (such as "Galaxy"), so the catalogue is large but regular. Item ids are
`slot.style.colour`. Art is plain SVG drawn on a 200 x 300 canvas; the same drawing code makes item icons and the whole character, so
the website and the Android app show exactly the same thing. Colour placeholders in a drawing: @c main, @d dark, @l light, @s skin.
"""

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
SHORT_HAIR = P("M62 78 Q58 36 100 36 Q142 36 138 78 Q124 54 100 54 Q76 54 62 78Z")

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
    },
    "bottom": {
        "jeans": ("Jeans", 0, R(76, 198, 22, 62, "@c", 4) + R(102, 198, 22, 62, "@c", 4) + R(74, 194, 52, 10, "@d", 3)),
        "shorts": ("Shorts", 0, R(74, 196, 25, 32, "@c", 4) + R(101, 196, 25, 32, "@c", 4)),
        "skirt": ("Skirt", 0, P("M72 196 L128 196 L142 240 L58 240Z")),
        "track": ("Track pants", 0, R(76, 198, 22, 62, "@c", 4) + R(102, 198, 22, 62, "@c", 4) + R(87, 198, 4, 62, "@l") + R(109, 198, 4, 62, "@l")),
        "cargo": ("Cargo pants", 1, R(76, 198, 22, 62, "@c", 4) + R(102, 198, 22, 62, "@c", 4) + R(78, 226, 14, 14, "@d", 2) + R(108, 226, 14, 14, "@d", 2)),
        "leggings": ("Leggings", 0, R(80, 198, 16, 62, "@c", 6) + R(104, 198, 16, 62, "@c", 6)),
        "kilt": ("Kilt", 1, P("M72 196 L128 196 L136 236 L64 236Z") + G(*[L(x, 198, x - 2, 234, "@d", 2) for x in (84, 100, 116)]) + L(66, 220, 134, 220, "@d", 2)),
        "bermuda": ("Bermudas", 0, R(74, 196, 25, 46, "@c", 4) + R(101, 196, 25, 46, "@c", 4) + R(74, 196, 52, 6, "@d")),
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
    },
    "top": {
        "tee": ("T-shirt", 0, R(68, 120, 64, 82, "@c", 12) + R(52, 124, 17, 26, "@c", 7) + R(131, 124, 17, 26, "@c", 7)),
        "longsleeve": ("Long sleeve", 0, R(68, 120, 64, 82, "@c", 12) + R(52, 124, 17, 68, "@c", 7) + R(131, 124, 17, 68, "@c", 7)),
        "hoodie": ("Hoodie", 1, R(68, 120, 64, 82, "@c", 12) + R(52, 124, 17, 68, "@c", 7) + R(131, 124, 17, 68, "@c", 7) + P("M80 118 Q100 148 120 118 Q100 134 80 118Z", "@d") + R(86, 170, 28, 20, "@d", 5)),
        "jumper": ("Striped jumper", 0, R(68, 120, 64, 82, "@c", 12) + R(52, 124, 17, 68, "@c", 7) + R(131, 124, 17, 68, "@c", 7) + G(*[R(68, y, 64, 6, "@l") for y in (140, 160, 180)])),
        "labcoat": ("Lab coat", 1, R(66, 120, 68, 112, "@c", 10) + R(50, 124, 18, 70, "@c", 7) + R(132, 124, 18, 70, "@c", 7) + L(100, 126, 100, 230, "@d", 2) + C(94, 150, 2.5, "@d") + C(94, 170, 2.5, "@d") + R(108, 176, 16, 14, "@d", 2, 'opacity=".4"')),
        "suit": ("Suit", 1, R(66, 120, 68, 84, "@c", 10) + R(50, 124, 18, 70, "@c", 7) + R(132, 124, 18, 70, "@c", 7) + POLY("88,122 112,122 100,170", "#ffffff") + POLY("98,128 102,128 104,172 100,182 96,172", "@d")),
        "armour": ("Armour", 2, R(66, 120, 68, 82, "@c", 8) + C(62, 128, 15, "@l") + C(138, 128, 15, "@l") + R(52, 130, 16, 60, "@d", 6) + R(132, 130, 16, 60, "@d", 6) + L(100, 126, 100, 200, "@d", 3) + R(66, 184, 68, 8, "@d")),
        "dress": ("Dress", 1, R(70, 120, 60, 40, "@c", 10) + P("M70 156 L130 156 L150 240 L50 240Z") + R(52, 124, 17, 24, "@c", 7) + R(131, 124, 17, 24, "@c", 7) + R(70, 154, 60, 6, "@d")),
        "tank": ("Tank top", 0, R(74, 120, 52, 80, "@c", 10) + R(52, 124, 14, 60, "@s", 7) + R(134, 124, 14, 60, "@s", 7)),
        "hooped": ("Hooped tee", 0, R(68, 120, 64, 82, "@c", 12) + R(52, 124, 17, 26, "@c", 7) + R(131, 124, 17, 26, "@c", 7) + G(*[R(68, y, 64, 7, "@d") for y in (136, 156, 176)])),
        "puffer": ("Puffer jacket", 1, R(64, 120, 72, 84, "@c", 14) + R(48, 124, 20, 68, "@c", 9) + R(132, 124, 20, 68, "@c", 9) + G(*[L(66, y, 134, y, "@d", 3) for y in (146, 166, 186)])),
        "poncho": ("Poncho", 2, POLY("100,116 150,208 50,208", "@c") + G(*[L(x, 196, x + 4, 208, "@l", 3) for x in range(62, 140, 12)])),
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
        "short": ("Short hair", 0, SHORT_HAIR),
        "long": ("Long hair", 0, SHORT_HAIR + R(60, 60, 14, 78, "@c", 7) + R(126, 60, 14, 78, "@c", 7)),
        "bun": ("Bun", 0, SHORT_HAIR + C(100, 30, 15)),
        "spiky": ("Spiky hair", 1, P("M62 78 L60 48 L74 54 L80 30 L92 46 L100 26 L108 46 L120 30 L126 54 L140 48 L138 78 Q124 54 100 54 Q76 54 62 78Z")),
        "mohawk": ("Mohawk", 1, P("M90 50 L92 22 L100 36 L106 14 L112 40 L116 50Z") + P("M66 74 Q70 48 90 48 L110 48 Q130 48 134 74 Q124 56 100 56 Q76 56 66 74Z", "@c", 'opacity=".4"')),
        "afro": ("Afro", 1, G(C(64, 62, 20), C(76, 42, 22), C(100, 34, 24), C(124, 42, 22), C(136, 62, 20), R(66, 44, 68, 18, "@c"))),
        "bob": ("Bob", 0, SHORT_HAIR + R(60, 60, 16, 44, "@c", 8) + R(124, 60, 16, 44, "@c", 8)),
        "ponytail": ("Ponytail", 0, SHORT_HAIR + P("M134 62 Q168 66 156 118 Q146 92 132 82Z")),
        "pigtails": ("Pigtails", 0, SHORT_HAIR + C(56, 92, 13) + C(144, 92, 13) + R(54, 66, 8, 20, "@c") + R(138, 66, 8, 20, "@c")),
        "curly": ("Curly hair", 0, G(*[C(x, y, 11) for x, y in [(66, 66), (72, 50), (86, 42), (100, 38), (114, 42), (128, 50), (134, 66)]]) + R(68, 44, 64, 12, "@c")),
        "buzz": ("Buzz cut", 0, P("M66 72 Q66 42 100 40 Q134 42 134 72 Q124 50 100 50 Q76 50 66 72Z", "@c", 'opacity=".75"')),
        "fringe": ("Fringe", 0, SHORT_HAIR + R(66, 48, 68, 14, "@c", 6)),
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


def fill(markup, item_id=None, skin=None):
    """Fill the colour placeholders of one drawing for the item's colour and the skin."""
    colour = COLOURS[CATALOG[item_id]["colour"]] if item_id else COLOURS["grey"]
    _, c, d, l, _ = colour
    return markup.replace("@c", c).replace("@d", d).replace("@l", l).replace("@s", SKINS.get(skin, SKINS[DEFAULT_SKIN])[1])


def drawing(item_id, skin=None):
    item = CATALOG[item_id]
    markup = fill(STYLES[item["slot"]][item["style"]][2], item_id, skin)
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


def body(skin):
    s = SKINS.get(skin, SKINS[DEFAULT_SKIN])[1]
    o, lit = shade(s, 0.72), shade(s, 1.18)
    line = f'stroke="{o}" stroke-width="2" stroke-linejoin="round"'
    return G(
        R(77, 196, 21, 66, s, 9, line), R(102, 196, 21, 66, s, 9, line),                                   # legs
        R(53, 126, 16, 66, s, 8, line), R(131, 126, 16, 66, s, 8, line),                                   # arms
        C(61, 195, 8.5, s, line), C(139, 195, 8.5, s, line),                                               # hands
        P("M70 136 Q70 120 86 120 H114 Q130 120 130 136 V194 Q130 204 120 204 H80 Q70 204 70 194Z", s, line),  # torso
        R(91, 104, 18, 22, s, 6, line), R(91, 112, 18, 8, o, 3, 'opacity=".35"'),                           # neck and its shadow
        E(66, 80, 5.5, 9, s, line), E(134, 80, 5.5, 9, s, line),                                           # ears
        E(100, 78, 34, 37, s, line), E(90, 58, 14, 8, lit, 'opacity=".45"'),                                # head and a highlight
        P("M80 66 Q88 62 95 66", "none", f'stroke="{o}" stroke-width="2.6" stroke-linecap="round"'),          # brows
        P("M105 66 Q112 62 120 66", "none", f'stroke="{o}" stroke-width="2.6" stroke-linecap="round"'),
        E(88, 77, 4.2, 5.2, INK), E(112, 77, 4.2, 5.2, INK), C(89.6, 75, 1.5, "#fff"), C(113.6, 75, 1.5, "#fff"),  # eyes
        P("M98 84 Q100 87 102 84", "none", f'stroke="{o}" stroke-width="2" stroke-linecap="round"'),            # nose
        P("M90 93 Q100 102 110 93", "none", f'stroke="{INK}" stroke-width="3" stroke-linecap="round"'),        # smile
        E(78, 89, 6, 3.6, "#ff7a8a", 'opacity=".28"'), E(122, 89, 6, 3.6, "#ff7a8a", 'opacity=".28"'),       # cheeks
    )


GROUND = E(100, 279, 52, 7, "#000", 'opacity=".18"')
CROPS = {"hat": "44 0 112 96", "hair": "44 20 112 96", "face": "56 52 88 56", "top": "36 100 128 120", "bottom": "50 180 100 100",
         "shoes": "56 236 88 52", "held": "104 120 96 110", "pet": "128 206 72 84"}


def avatar_svg(outfit, skin=None, size=None, crop=None):
    """The whole character. `outfit` maps a slot to an item id; unknown or non-wearable entries are ignored."""
    layers = []
    for slot in LAYER_ORDER:
        if slot == "BODY":
            layers.append(GROUND + body(skin))
            continue
        item_id = outfit.get(slot)
        if item_id in CATALOG and CATALOG[item_id]["slot"] == slot:
            layers.append(drawing(item_id, skin))
    return _wrap("".join(layers), crop or "0 0 200 300", size)


def _wrap(inner, view, size=None):
    w, h = [float(x) for x in view.split()[2:]]
    dims = f' width="{size}" height="{round(size * h / w)}"' if size else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}"{dims}>{DEFS}{inner}</svg>'


GHOST = '<g opacity=".22" filter="url(#grey)">{}</g>'


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
    mannequin = GHOST.format(GROUND + body(skin))
    if slot == "background":
        return _wrap(drawing(item_id) + '<g opacity=".5">' + GROUND + body(skin) + "</g>", "0 0 200 300")
    return _wrap(mannequin + drawing(item_id, skin), CROPS.get(slot, "0 0 200 300"))


def png(svg, width):
    """The SVG drawn as a PNG `width` pixels wide (for the Android app, which has no SVG renderer)."""
    import cairosvg
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=width)
