"""Contact sheets for the rewards art: the character, every style worn, every item icon and a few whole outfits.

    python docs/design/avatar-iterations/sheet.py <output directory>

Writes one self-contained HTML page per sheet (the art is embedded, drawn by server/game_items.py exactly as the app's
/game/art routes draw it). No server and no database are involved. Screenshot the pages with any headless browser, e.g.

    chrome --headless --screenshot=base.png --window-size=1500,1250 --hide-scrollbars file:///.../base.html
"""
import base64
import html
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server"))
import game_items as items  # noqa: E402

# The parts of server/web.css these pictures sit in, so the sheet shows them the way the Rewards page does.
CSS = """
:root{--bg:#121318;--surface:#1a1b21;--surface-2:#23242b;--surface-3:#2d2e35;--line:rgba(148,163,184,.18);--text:#e4e1e9;--muted:#a8abbb}
:root[data-theme=light]{--bg:#f5f6fa;--surface:#fff;--surface-2:#f0f2f7;--surface-3:#e4e7ef;--line:rgba(30,41,59,.14);--text:#1a1c24;--muted:#525868}
body{margin:0;padding:18px;background:var(--bg);color:var(--text);font:13px/18px Inter,system-ui,"Segoe UI",sans-serif;
  --r0:#a1a7b5;--r1:#3ddc97;--r2:#5aa9ff;--r3:#b77cff;--r4:#ffc23d;--r5:#ff5fb7}
h1{font-size:18px;margin:0 0 12px}h2{font-size:13px;margin:18px 0 8px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.08em}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end}
figure{margin:0;display:flex;flex-direction:column;align-items:center;gap:4px}
figcaption{font-size:11px;color:var(--muted);max-width:150px;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.frame{border-radius:18px;overflow:hidden;background:STAGE;box-shadow:0 10px 30px rgba(0,0,0,.35)}
.frame img,.plain img{display:block;width:100%;height:100%}
.plain{border-radius:14px;overflow:hidden;background:var(--surface-3)}
.plate{--rc:var(--r0);width:120px;height:120px;border-radius:14px;display:grid;place-items:center;overflow:hidden;
  background:PLATE}
.plate img{width:86%;height:86%;object-fit:contain;filter:drop-shadow(0 3px 4px rgba(0,0,0,.18))}
.plate.s{width:64px;height:64px;border-radius:10px}
.icon44{width:44px;height:44px;border-radius:12px;background:ICON;object-fit:cover}
.r1{--rc:var(--r1)}.r2{--rc:var(--r2)}.r3{--rc:var(--r3)}.r4{--rc:var(--r4)}.r5{--rc:var(--r5)}
"""
# The three backgrounds art is shown on; read from web.css so the sheet follows the app when they change.
def _css_value(selector, prop):
    for line in (ROOT / "server" / "web.css").read_text(encoding="utf-8").splitlines():
        if line.startswith(selector + "{") and prop + ":" in line:
            return line.split(prop + ":", 1)[1].split(";")[0].rstrip("}")
    raise SystemExit(f"{selector} {prop} not found in web.css")


def css():
    return (CSS.replace("STAGE", _css_value(".stage-frame", "background")).replace("PLATE", _css_value(".plate", "background"))
            .replace("ICON", _css_value(".slot img", "background")))


def img(svg, w, h=None, cls=""):
    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img class="{cls}" src="data:image/svg+xml;base64,{data}" width="{w}" height="{h or w}" alt="">'


def fig(inner, caption):
    return f"<figure>{inner}<figcaption>{html.escape(caption)}</figcaption></figure>"


def avatar(outfit=None, skin="sand", build="masculine", w=150, box="frame", crop=None):
    kwargs = {"crop": crop} if crop else {}
    svg = items.avatar_svg(outfit or {}, skin, build=build, **kwargs)
    h = w if crop else round(w * 1.5)
    return f'<div class="{box}" style="width:{w}px;height:{h}px">{img(svg, w, h)}</div>'


def plate(item_id, small=False):
    rarity = items.CATALOG[item_id]["rarity"]
    return f'<div class="plate r{rarity}{" s" if small else ""}">{img(items.item_svg(item_id), 100)}</div>'


COLOURS = ["blue", "red", "green", "purple", "yellow", "black", "white", "teal", "pink", "orange", "gold", "galaxy", "rainbow", "holo", "obsidian", "neon-green"]
BUILDS = ["masculine", "feminine"]
SKINS = list(items.SKINS)


def page(title, body, theme="dark"):
    return (f'<!doctype html><html data-theme="{theme}"><meta charset="utf-8"><title>{html.escape(title)}</title><style>{css()}</style>'
            f"<h1>{html.escape(title)}</h1>{body}</html>")


def base_sheet():
    out = []
    for build in BUILDS:
        out.append(f"<h2>{build}: every skin tone, nothing equipped</h2><div class=row>"
                   + "".join(fig(avatar({}, skin, build, 160), skin) for skin in SKINS) + "</div>")
    sizes = "".join(fig(avatar(OUTFITS[i % len(OUTFITS)][1], SKINS[i % 6], BUILDS[i % 2], w, "plain"), f"{w}px")
                    for i, w in enumerate([104, 104, 84, 84, 64, 64, 32, 32, 32, 32]))
    out.append(f"<h2>the sizes the app shows: podium 104 and 84, phone podium 64, leaderboard row 32</h2><div class=row>{sizes}</div>")
    return "".join(out)


def worn_sheet(slot):
    styles = list(items.STYLES[slot])
    cells = []
    for i, style in enumerate(styles):
        colour = COLOURS[i % len(COLOURS)]
        item_id = f"{slot}.{style}.{colour}"
        outfit = {slot: item_id}
        if slot in ("back", "aura"):
            outfit["top"] = "top.tee.white"
        cells.append(fig(avatar(outfit, SKINS[i % 6], BUILDS[i % 2], 150), f"{style} · {colour}"))
    return f"<div class=row>{''.join(cells)}</div>"


def icon_sheet():
    out = []
    for slot in items.SLOTS:
        cells = []
        for i, style in enumerate(items.STYLES[slot]):
            colour = COLOURS[(i * 3) % len(COLOURS)]
            item_id = f"{slot}.{style}.{colour}"
            cells.append(fig(plate(item_id), f"{style} · {colour}"))
        first = f"{slot}.{next(iter(items.STYLES[slot]))}.grey"
        strip = img(items.item_svg(first), 44, cls="icon44")
        out.append(f"<h2>{slot} &nbsp; {strip}</h2><div class=row>{''.join(cells)}</div>")
    return "".join(out)


OUTFITS = [
    ("scholar", {"hair": "hair.bob.black", "top": "top.labcoat.white", "bottom": "bottom.skirt.teal", "shoes": "shoes.loafers.brown", "face": "face.round.black",
                 "held": "held.flask.green", "pet": "pet.owl.brown", "background": "background.graph.blue"}),
    ("wizard", {"hair": "hair.long.silver", "hat": "hat.wizard.galaxy", "top": "top.royalrobe.purple", "bottom": "bottom.hakama.obsidian", "shoes": "shoes.boots.brown",
                "held": "held.wand.gold", "pet": "pet.dragon.green", "aura": "aura.sparkles.gold", "background": "background.stars.purple"}),
    ("skater", {"hair": "hair.spiky.neon-green", "hat": "hat.headphones.red", "top": "top.hoodie.grey", "bottom": "bottom.cargo.black", "shoes": "shoes.hightops.red",
                "face": "face.shades.black", "back": "back.backpack.orange", "pet": "pet.slime.teal", "background": "background.checker.grey"}),
    ("knight", {"hair": "hair.ponytail.orange", "hat": "hat.crown.gold", "top": "top.armour.silver", "bottom": "bottom.greaves.silver", "shoes": "shoes.boots.black",
                "held": "held.sword.silver", "back": "back.cape.red", "aura": "aura.flames.orange", "background": "background.sunset.orange"}),
    ("gala", {"hair": "hair.bun.brown", "hat": "hat.tiara.gold", "top": "top.ballgown.pink", "shoes": "shoes.glass.holo", "face": "face.blush.pink",
              "back": "back.butterfly.holo", "aura": "aura.petals.pink", "pet": "pet.bunny.white", "background": "background.spotlight.purple"}),
    ("pirate", {"hair": "hair.curly.black", "hat": "hat.tricorn.black", "top": "top.pirate.red", "bottom": "bottom.bermuda.brown", "shoes": "shoes.cowboy.brown",
                "face": "face.eyepatch.black", "held": "held.telescope.bronze", "pet": "pet.chick.yellow", "background": "background.waves.blue"}),
    ("astronaut", {"hat": "hat.astro.white", "top": "top.astronaut.white", "bottom": "bottom.track.white", "shoes": "shoes.rocket.silver", "back": "back.jetpack.grey",
                   "aura": "aura.orbit.blue", "pet": "pet.robot.silver", "background": "background.stars.obsidian", "hair": "hair.buzz.black"}),
    ("casual", {"hair": "hair.afro.black", "top": "top.jumper.yellow", "bottom": "bottom.jeans.blue", "shoes": "shoes.sneakers.white", "hat": "hat.cap.red",
                "held": "held.coffee.white", "pet": "pet.dog.brown", "background": "background.fade.teal"}),
    ("graduate", {"hair": "hair.pigtails.pink", "hat": "hat.gradcap.black", "top": "top.suit.black", "bottom": "bottom.kilt.red", "shoes": "shoes.platform.black",
                  "held": "held.trophy.gold", "face": "face.freckles.brown", "pet": "pet.cat.orange", "background": "background.dots.yellow"}),
    ("ninja", {"hair": "hair.mohawk.purple", "top": "top.ninja.black", "bottom": "bottom.leggings.black", "shoes": "shoes.sandals.black", "face": "face.mask.black",
               "back": "back.bat.obsidian", "aura": "aura.storm.purple", "pet": "pet.ghost.white", "held": "held.lollipop.pink"}),
    ("rainbow", {"hair": "hair.fringe.rainbow", "hat": "hat.flowers.pink", "top": "top.dress.rainbow", "shoes": "shoes.skates.pink", "back": "back.angel.white",
                 "aura": "aura.hearts.red", "held": "held.balloon.red", "pet": "pet.penguin.black", "background": "background.stripes.pink"}),
    ("chef", {"hat": "hat.chef.white", "top": "top.tank.white", "bottom": "bottom.shorts.green", "shoes": "shoes.slippers.pink", "face": "face.moustache.brown",
              "held": "held.magnifier.gold", "pet": "pet.mushroom.red", "back": "back.shell.green", "aura": "aura.ring.gold"}),
]


def combo_sheet():
    cells = [fig(avatar(outfit, SKINS[i % len(SKINS)], BUILDS[i % 2], 200), name) for i, (name, outfit) in enumerate(OUTFITS)]
    return f"<div class=row>{''.join(cells)}</div>"


def zoom_sheet():
    """A few characters large, to judge line, shading and how pieces sit."""
    picks = [({}, "sand", "masculine"), ({}, "tan", "feminine")] + [(OUTFITS[i][1], SKINS[i % len(SKINS)], BUILDS[i % 2]) for i in (0, 3, 7)]
    return f"<div class=row>{''.join(avatar(outfit, skin, build, 280) for outfit, skin, build in picks)}</div>"


def main(out):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sheets = {"base": ("The character", base_sheet()), "combos": ("Whole outfits", combo_sheet()), "zoom": ("Close up", zoom_sheet()), "icons": ("Item icons, as the shop and wardrobe show them", icon_sheet())}
    for slot in items.WORN:
        sheets[f"worn-{slot}"] = (f"Every {slot} style, worn", worn_sheet(slot))
    for name, (title, body) in sheets.items():
        (out / f"{name}.html").write_text(page(title, body), encoding="utf-8")
    (out / "icons-light.html").write_text(page("Item icons, light theme", icon_sheet(), "light"), encoding="utf-8")
    (out / "base-light.html").write_text(page("The character, light theme", base_sheet() + combo_sheet(), "light"), encoding="utf-8")
    print(f"wrote {len(sheets) + 2} sheets to {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sheets")
