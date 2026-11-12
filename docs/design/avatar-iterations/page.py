"""The Rewards page with made-up data, for looking at the art in place.

    python docs/design/avatar-iterations/page.py [server directory] [port]

Serves the real web-game.js, web.css and art from the given server directory (default: this checkout's), and answers the /game
calls with a fixed player. No database, no accounts, nothing is saved. Open http://127.0.0.1:8765/#rewards, or
/?theme=light#rewards/shop and so on.
"""
import http.server
import json
import pathlib
import sys
import urllib.parse

SERVER = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[3] / "server").resolve()
sys.path.insert(0, str(SERVER))
import game_items as items  # noqa: E402

PAGE = """<!doctype html><html data-theme="THEME"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rewards</title><link rel="stylesheet" href="/web.css"><body><main style="max-width:1180px;margin:0 auto;padding:24px 16px"><div id="view"></div></main>
<script type="module">
import { renderGame } from '/web-game.js';
const api = async (path, options) => { const r = await fetch(path, options); if (!r.ok) throw new Error((await r.json()).detail); return r.json(); };
const show = () => { const [, sub = ''] = location.hash.slice(1).split('/'); renderGame(document.getElementById('view'), api, new URLSearchParams({ sub })); };
addEventListener('hashchange', show); show();
</script></body></html>"""

OUTFIT = {"hair": "hair.bob.black", "top": "top.labcoat.white", "bottom": "bottom.skirt.teal", "shoes": "shoes.loafers.brown", "face": "face.round.black",
          "held": "held.flask.green", "pet": "pet.owl.brown", "background": "background.graph.blue"}
OWNED = list(OUTFIT.values()) + ["hat.cap.red", "hat.wizard.galaxy", "hat.crown.gold", "hat.beanie.teal", "hat.gradcap.black", "hat.headphones.pink", "hat.tophat.silver", "hat.catears.obsidian",
                                 "top.hoodie.green", "top.armour.silver", "hair.spiky.neon-green", "pet.dragon.rainbow", "pet.cat.orange", "held.wand.gold", "trinket.atom.blue",
                                 "trinket.pi.gold", "trinket.rocket.red", "trinket.medal.holo", "back.cape.red", "aura.sparkles.gold", "shoes.rocket.silver"]
SHOWCASE = ["hat.wizard.galaxy", "pet.dragon.rainbow", "trinket.medal.holo", "hat.crown.gold", "trinket.atom.blue"]
PLAYERS = [("mereana", {"hair": "hair.ponytail.orange", "hat": "hat.crown.gold", "top": "top.armour.silver", "bottom": "bottom.greaves.silver", "held": "held.sword.silver", "back": "back.cape.red",
                        "background": "background.sunset.orange"}, "tan", "feminine"),
           ("you", OUTFIT, "sand", "feminine"),
           ("tane", {"hair": "hair.spiky.neon-green", "hat": "hat.headphones.red", "top": "top.hoodie.grey", "bottom": "bottom.cargo.black", "face": "face.shades.black", "pet": "pet.slime.teal"}, "honey", "masculine"),
           ("aroha", {"hair": "hair.bun.brown", "hat": "hat.tiara.gold", "top": "top.ballgown.pink", "back": "back.butterfly.holo", "background": "background.spotlight.purple"}, "umber", "feminine"),
           ("wiremu", {"hat": "hat.astro.white", "top": "top.astronaut.white", "back": "back.jetpack.grey", "background": "background.stars.obsidian"}, "mint", "masculine"),
           ("kiri", {"hair": "hair.afro.black", "top": "top.jumper.yellow", "hat": "hat.cap.red", "background": "background.fade.teal"}, "cocoa", "feminine"),
           ("sam", {}, "porcelain", "masculine")]


def me():
    owned = [{**items.public(items.CATALOG[i]), "count": 3 if n % 5 == 0 else 1} for n, i in enumerate(OWNED)]
    by_slot = {s: {"owned": sum(1 for o in owned if o["slot"] == s), "total": sum(1 for i in items.CATALOG.values() if i["slot"] == s)} for s in items.SLOTS}
    return {"balance": 1840, "earned": 2600, "networth": 6315, "outfit": OUTFIT, "skin": "sand", "build": "feminine", "visible": True, "owned": owned, "showcase": SHOWCASE,
            "breakdown": [{"label": "Review answers", "count": 212, "each": 5, "points": 1060}, {"label": "Lessons completed", "count": 31, "each": 25, "points": 775},
                          {"label": "Papers at Merit", "count": 3, "each": 100, "points": 300}, {"label": "Papers at Excellence", "count": 0, "each": 160, "points": 0}],
            "notice": "Points come from work recorded as correct. Estimated grade and GPA are unofficial estimates, not NZQA results.",
            "estimate": {"grade": "Merit", "gpa": 6.2, "topics": 7}, "pity": {"pulls": 14, "rare_in": 6, "epic_in": 16}, "costs": {"pull": 100, "ten": 900},
            "odds": dict(zip(items.RARITIES, items.ODDS)),
            "catalog": {"art": items.ART_VERSION, "total": len(items.CATALOG), "owned": len(owned), "by_slot": by_slot, "rarities": items.RARITIES,
                        "slots": [{"id": s, "name": items.SLOT_NAMES[s], "worn": s in items.WORN, "icon": f"{s}.{next(iter(items.STYLES[s]))}.teal"} for s in items.SLOTS],
                        "builds": [{"id": k, "name": v} for k, v in items.BUILDS.items()], "skins": [{"id": k, "name": v[0], "colour": v[1]} for k, v in items.SKINS.items()]}}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, body, kind):
        body = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = dict(urllib.parse.parse_qsl(url.query))
        path = url.path
        if path == "/":
            return self.send(PAGE.replace("THEME", query.get("theme", "dark")), "text/html; charset=utf-8")
        if path == "/game/art/avatar.svg":
            outfit = {s: query[s] for s in items.WORN if query.get(s) in items.CATALOG}
            try:
                svg = items.avatar_svg(outfit, query.get("skin", ""), crop=query.get("crop"), build=query.get("build", ""))
            except TypeError:                                    # the art before the redesign had no crop
                svg = items.avatar_svg(outfit, query.get("skin", ""), build=query.get("build", ""))
            return self.send(svg, "image/svg+xml")
        if path.startswith("/game/art/item/"):
            return self.send(items.item_svg(urllib.parse.unquote(path.rsplit("/", 1)[1][:-4]), query.get("skin", "")), "image/svg+xml")
        if path == "/game/me":
            return self.send(json.dumps(me()), "application/json")
        if path == "/game/shop":
            found = [i for i in items.CATALOG.values() if i["shop"] and i["slot"] == query.get("slot") and ("rarity" not in query or i["rarity"] == int(query["rarity"]))]
            page = found[int(query.get("offset", 0)):][:int(query.get("limit", 24))]
            return self.send(json.dumps({"total": len(found), "items": [{**items.public(i), "owned": 0} for i in page]}), "application/json")
        if path.startswith("/game/leaderboard/"):
            rows = [{"user_id": n, "username": name, "rank": n + 1, "text": f"{9000 - n * 1130:,}", "outfit": outfit, "skin": skin, "build": build} for n, (name, outfit, skin, build) in enumerate(PLAYERS)]
            return self.send(json.dumps({"rows": rows, "you": 1, "note": ""}), "application/json")
        file = SERVER / path.lstrip("/")
        if file.is_file() and file.suffix in (".js", ".css") and file.parent == SERVER:
            return self.send(file.read_bytes(), "text/javascript" if file.suffix == ".js" else "text/css")
        self.send_error(404)


if __name__ == "__main__":
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    print(f"Rewards page from {SERVER} at http://127.0.0.1:{port}/#rewards")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
