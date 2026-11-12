"""Rewards: points earned from correct work, a gacha and shop for cosmetic collectables, a dressable character and leaderboards.

Earnings are derived from the account's own records every time they are read (see `earnings`), so there is nothing to forge or to pay twice;
only spending is stored (the ledger). Leaderboards read `public.game_profiles`, a snapshot of each account's totals refreshed when the
account uses Rewards and on the server's periodic tick, so no query ever reaches into another account's study schema. Design: docs/rewards.md.
"""
import json
import random

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

import game_items as items
import userspace

WELCOME_GIFT = 200
PULL_COST, TEN_PULL_COST = 100, 900
RARE_PITY, EPIC_PITY = 10, 30           # a rare or better at least every 10 pulls, an epic or better at least every 30
SHOWCASE_SIZE = 6
MIN_PAPER_QUESTIONS = 3
POINTS = {"review": 5, "achieved": 4, "merit": 6, "excellence": 8, "lesson": 25, "paper_achieved": 60, "paper_merit": 100,
          "paper_excellence": 160, "day": 10}
PAPER_BANDS = (("excellence", 0.85), ("merit", 0.70), ("achieved", 0.50))      # the same bands as marking.grade_for
BOARDS = {   # board -> (column, label, unit)
    "networth": ("networth", "Net worth", "points"), "questions": ("questions", "Questions correct", "questions"),
    "lessons": ("lessons", "Lessons completed", "lessons"), "papers": ("papers", "Papers passed", "papers"),
    "grade": ("est_mastery", "Estimated grade", ""), "gpa": ("est_gpa", "Estimated GPA", "/ 9"),
    "collection": ("distinct_items", "Collection", "items"),
}


def paper_grade(awarded, available):
    if not available:
        return None
    ratio = awarded / available
    return next((name for name, bound in PAPER_BANDS if ratio >= bound), "not_achieved")


def gpa_from(mastery):
    """Mastery 0..1 on the 0..9 scale: 0 -> 0, 0.4 -> 3, 0.6 -> 5, 0.8 -> 7, 1 -> 9, straight lines between. Unofficial."""
    knots = [(0, 0), (0.4, 3), (0.6, 5), (0.8, 7), (1, 9)]
    mastery = max(0.0, min(1.0, mastery))
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if mastery <= x1:
            return round(y0 + (y1 - y0) * (mastery - x0) / (x1 - x0), 2)
    return 9.0


def grade_name(mastery):
    return "Not achieved" if mastery < 0.4 else "Achieved" if mastery < 0.6 else "Merit" if mastery < 0.8 else "Excellence"


def earnings(stats):
    """(total, breakdown) from counted records. Every line is something already recorded as correct."""
    lines = [
        ("Review questions answered correctly", stats["review_correct"], POINTS["review"]),
        ("Exam questions marked Achieved", stats["achieved"], POINTS["achieved"]),
        ("Exam questions marked Merit", stats["merit"], POINTS["merit"]),
        ("Exam questions marked Excellence", stats["excellence"], POINTS["excellence"]),
        ("Lessons completed", stats["lessons"], POINTS["lesson"]),
        ("Papers passed at Achieved", stats["papers_achieved"], POINTS["paper_achieved"]),
        ("Papers passed at Merit", stats["papers_merit"], POINTS["paper_merit"]),
        ("Papers passed at Excellence", stats["papers_excellence"], POINTS["paper_excellence"]),
        ("Days with a correct answer", stats["days"], POINTS["day"]),
    ]
    breakdown = [{"label": label, "count": count, "each": each, "points": count * each} for label, count, each in lines]
    return sum(line["points"] for line in breakdown), breakdown


def roll_rarity(rng, since_rare, since_epic):
    floor = 3 if since_epic >= EPIC_PITY - 1 else 2 if since_rare >= RARE_PITY - 1 else 0
    weights = [w if i >= floor else 0 for i, w in enumerate(items.ODDS)]
    return rng.choices(range(len(weights)), weights=weights)[0]


def pull_once(rng, state):
    """One gacha pull. `state` carries the pity counters and is updated in place; returns the item id."""
    rarity = roll_rarity(rng, state["since_rare"], state["since_epic"])
    state["since_rare"] = 0 if rarity >= 2 else state["since_rare"] + 1
    state["since_epic"] = 0 if rarity >= 3 else state["since_epic"] + 1
    state["pulls"] += 1
    return rng.choice(items.BY_RARITY[rarity])


def networth(balance, owned):
    return balance + sum(items.CATALOG[i]["value"] * n for i, n in owned.items() if i in items.CATALOG)


# --- tables -------------------------------------------------------------------------------------------------------------

def create_game_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS game_state (
        id integer PRIMARY KEY CHECK (id = 1), pulls integer NOT NULL DEFAULT 0,
        since_rare integer NOT NULL DEFAULT 0, since_epic integer NOT NULL DEFAULT 0,
        skin text NOT NULL DEFAULT 'sand', visible boolean NOT NULL DEFAULT true)""")
    db.execute("ALTER TABLE game_state ADD COLUMN IF NOT EXISTS build text NOT NULL DEFAULT 'masculine'")
    db.execute("""CREATE TABLE IF NOT EXISTS game_ledger (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, kind text NOT NULL, item_id text,
        amount integer NOT NULL, created_at timestamptz NOT NULL DEFAULT now())""")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS game_ledger_welcome_idx ON game_ledger (kind) WHERE kind = 'welcome'")
    db.execute("""CREATE TABLE IF NOT EXISTS game_items (
        item_id text PRIMARY KEY, count integer NOT NULL CHECK (count > 0), first_at timestamptz NOT NULL DEFAULT now())""")
    db.execute("CREATE TABLE IF NOT EXISTS game_outfit (slot text PRIMARY KEY, item_id text NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS game_showcase (position integer PRIMARY KEY CHECK (position BETWEEN 1 AND 12), item_id text NOT NULL)")


def create_public_game_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS game_profiles (
        user_id bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        networth integer NOT NULL DEFAULT 0, balance integer NOT NULL DEFAULT 0,
        questions integer NOT NULL DEFAULT 0, lessons integer NOT NULL DEFAULT 0, papers integer NOT NULL DEFAULT 0,
        est_mastery double precision, est_gpa double precision, distinct_items integer NOT NULL DEFAULT 0, total_items integer NOT NULL DEFAULT 0,
        rarest text, outfit jsonb NOT NULL DEFAULT '{}'::jsonb, showcase jsonb NOT NULL DEFAULT '[]'::jsonb,
        skin text NOT NULL DEFAULT 'sand', visible boolean NOT NULL DEFAULT true, updated_at timestamptz NOT NULL DEFAULT now())""")
    db.execute("ALTER TABLE game_profiles ADD COLUMN IF NOT EXISTS build text NOT NULL DEFAULT 'masculine'")


# --- reading an account -------------------------------------------------------------------------------------------------

NZ_DAY = "(%s AT TIME ZONE 'Pacific/Auckland')::date"


def read_stats(db, min_answers):
    """Counts of recorded correct work in the current account. Nothing here is predicted."""
    review_correct = db.execute(f"SELECT count(DISTINCT (question_id, {NZ_DAY % 'answered_at'})) FROM review_answers WHERE correct").fetchone()[0]
    marked = dict(db.execute("""SELECT outcome, count(*) FROM (
            SELECT DISTINCT ON (exam_id, question_id) result->>'outcome' AS outcome FROM markings
            WHERE kind = 'first' ORDER BY exam_id, question_id, created_at DESC) m GROUP BY outcome""").fetchall())
    lessons = db.execute("SELECT count(*) FROM lessons WHERE completed_at IS NOT NULL").fetchone()[0]
    papers = {"achieved": 0, "merit": 0, "excellence": 0}
    for items_n, answered, marked_n, awarded, available in db.execute("""SELECT
            (SELECT count(*) FROM exam_items i WHERE i.exam_id = e.id),
            (SELECT count(*) FROM exam_items i WHERE i.exam_id = e.id AND i.answer <> ''),
            COALESCE(m.marked, 0), COALESCE(m.awarded, 0), COALESCE(m.available, 0)
        FROM exams e LEFT JOIN LATERAL (
            SELECT count(*) marked, sum((r.result->>'marks_awarded')::numeric) awarded, sum((r.result->>'marks_available')::numeric) available
            FROM (SELECT DISTINCT ON (question_id) result FROM markings WHERE exam_id = e.id AND kind = 'first'
                  ORDER BY question_id, created_at DESC) r) m ON true
        WHERE e.kind <> 'rapid'""").fetchall():
        if items_n >= MIN_PAPER_QUESTIONS and answered == items_n and marked_n == items_n:
            grade = paper_grade(float(awarded), float(available))
            if grade in papers:
                papers[grade] += 1
    days = db.execute(f"""SELECT count(*) FROM (
            SELECT {NZ_DAY % 'answered_at'} d FROM review_answers WHERE correct
            UNION SELECT {NZ_DAY % 'created_at'} FROM markings WHERE kind = 'first' AND result->>'outcome' IN ('achieved', 'merit', 'excellence')
            UNION SELECT {NZ_DAY % 'completed_at'} FROM lessons WHERE completed_at IS NOT NULL) x""").fetchone()[0]
    topics = db.execute("""SELECT t.mastery, (SELECT count(*) FROM review_answers a JOIN review_questions q ON q.id = a.question_id WHERE q.topic_id = t.id)
        FROM topics t JOIN courses c ON c.topic_id = t.id AND c.active""").fetchall()
    graded = [m or 0 for m, n in topics if n >= min_answers]
    mastery = sum(graded) / len(graded) if graded else None
    achieved, merit, excellence = (marked.get(k, 0) for k in ("achieved", "merit", "excellence"))
    return {"review_correct": review_correct, "achieved": achieved, "merit": merit, "excellence": excellence, "lessons": lessons,
            "papers_achieved": papers["achieved"], "papers_merit": papers["merit"], "papers_excellence": papers["excellence"],
            "days": days, "questions": review_correct + achieved + merit + excellence, "papers": sum(papers.values()),
            "mastery": mastery, "graded_topics": len(graded)}


def ensure_state(db):
    db.execute("INSERT INTO game_state (id) VALUES (1) ON CONFLICT DO NOTHING")
    db.execute("INSERT INTO game_ledger (kind, amount) VALUES ('welcome', %s) ON CONFLICT DO NOTHING", (WELCOME_GIFT,))


def lock_state(db):
    ensure_state(db)
    row = db.execute("SELECT pulls, since_rare, since_epic, skin, visible, build FROM game_state WHERE id = 1 FOR UPDATE").fetchone()
    return {"pulls": row[0], "since_rare": row[1], "since_epic": row[2], "skin": row[3], "visible": row[4], "build": row[5]}


def owned_counts(db):
    return {i: n for i, n in db.execute("SELECT item_id, count FROM game_items").fetchall() if i in items.CATALOG}


def full(item_id, count=None):
    item = items.public(items.CATALOG[item_id])
    return {**item, "count": count} if count is not None else item


def snapshot(connect, min_answers):
    """Everything about the current account's rewards in one read."""
    with connect() as db:
        stats = read_stats(db, min_answers)
        state = lock_state(db)
        total, breakdown = earnings(stats)
        spent = db.execute("SELECT COALESCE(sum(amount), 0) FROM game_ledger").fetchone()[0]
        owned = owned_counts(db)
        outfit = {s: i for s, i in db.execute("SELECT slot, item_id FROM game_outfit").fetchall() if owned.get(i)}
        showcase = [i for (i,) in db.execute("SELECT item_id FROM game_showcase ORDER BY position").fetchall() if owned.get(i)]
    balance = total + spent
    return {"stats": stats, "state": state, "earned": total, "breakdown": breakdown, "balance": balance, "owned": owned, "outfit": outfit,
            "showcase": showcase, "networth": networth(balance, owned)}


def publish_profile(connect_account, user_id, snap):
    owned = snap["owned"]
    rarest = max(owned, key=lambda i: (items.CATALOG[i]["rarity"], items.CATALOG[i]["value"]), default=None)
    stats = snap["stats"]
    mastery = stats["mastery"]
    with connect_account() as db:
        db.execute("""INSERT INTO game_profiles (user_id, networth, balance, questions, lessons, papers, est_mastery, est_gpa, distinct_items, total_items,
                rarest, outfit, showcase, skin, visible, build, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s, now())
            ON CONFLICT (user_id) DO UPDATE SET networth=EXCLUDED.networth, balance=EXCLUDED.balance, questions=EXCLUDED.questions,
                lessons=EXCLUDED.lessons, papers=EXCLUDED.papers, est_mastery=EXCLUDED.est_mastery, est_gpa=EXCLUDED.est_gpa,
                distinct_items=EXCLUDED.distinct_items, total_items=EXCLUDED.total_items, rarest=EXCLUDED.rarest, outfit=EXCLUDED.outfit,
                showcase=EXCLUDED.showcase, skin=EXCLUDED.skin, visible=EXCLUDED.visible, build=EXCLUDED.build, updated_at=now()""",
                   (user_id, snap["networth"], snap["balance"], stats["questions"], stats["lessons"], stats["papers"], mastery,
                    gpa_from(mastery) if mastery is not None else None, len(owned), len(items.CATALOG), rarest,
                    json.dumps(snap["outfit"]), json.dumps(snap["showcase"]), snap["state"]["skin"], snap["state"]["visible"], snap["state"]["build"]))


# --- API ----------------------------------------------------------------------------------------------------------------

class PullBody(BaseModel):
    count: int = Field(default=1)


class BuyBody(BaseModel):
    item_id: str = Field(max_length=80)


class RecycleBody(BaseModel):
    item_id: str = Field(max_length=80)
    count: int = Field(default=1, ge=1, le=1000)


class OutfitBody(BaseModel):
    slot: str | None = Field(default=None, max_length=20)
    item_id: str | None = Field(default=None, max_length=80)
    skin: str | None = Field(default=None, max_length=20)
    build: str | None = Field(default=None, max_length=20)
    clear: bool = False


class ShowcaseBody(BaseModel):
    items: list[str] = Field(max_length=SHOWCASE_SIZE)


class SettingsBody(BaseModel):
    visible: bool | None = None


def art_outfit(query):
    """Slot -> item id from a query string; anything that is not a catalogue item for that slot is dropped."""
    return {slot: query[slot] for slot in items.WORN if query.get(slot) in items.CATALOG and items.CATALOG[query[slot]]["slot"] == slot}


def game_router(connect, connect_account, authorised, min_answers=5, rng=None):
    rng = rng or random.SystemRandom()
    router = APIRouter()

    def me_id():
        return userspace.current_user.get()

    def state_json(snap):
        owned = snap["owned"]
        by_slot = {s: sum(1 for i in owned if items.CATALOG[i]["slot"] == s) for s in items.SLOTS}
        return {
            "balance": snap["balance"], "earned": snap["earned"], "networth": snap["networth"], "breakdown": snap["breakdown"],
            "stats": {k: snap["stats"][k] for k in ("questions", "lessons", "papers", "days")},
            "estimate": None if snap["stats"]["mastery"] is None else {
                "grade": grade_name(snap["stats"]["mastery"]), "mastery": round(snap["stats"]["mastery"], 3),
                "gpa": gpa_from(snap["stats"]["mastery"]), "topics": snap["stats"]["graded_topics"]},
            "owned": sorted((full(i, n) for i, n in owned.items()), key=lambda x: (-x["rarity"], x["slot"], x["name"])),
            "outfit": snap["outfit"], "showcase": snap["showcase"], "skin": snap["state"]["skin"], "build": snap["state"]["build"], "visible": snap["state"]["visible"],
            "pity": {"pulls": snap["state"]["pulls"], "rare_in": RARE_PITY - snap["state"]["since_rare"], "epic_in": EPIC_PITY - snap["state"]["since_epic"]},
            "costs": {"pull": PULL_COST, "ten": TEN_PULL_COST},
            "catalog": {"art": items.ART_VERSION, "total": len(items.CATALOG), "owned": len(owned), "by_slot": {s: {"owned": by_slot[s], "total": sum(1 for i in items.CATALOG.values() if i["slot"] == s)} for s in items.SLOTS},
                        "rarities": items.RARITIES, "slots": [{"id": s, "name": items.SLOT_NAMES[s], "worn": s in items.WORN, "icon": f"{s}.{next(iter(items.STYLES[s]))}.teal"} for s in items.SLOTS],
                        "skins": [{"id": k, "name": v[0], "colour": v[1]} for k, v in items.SKINS.items()],
                        "builds": [{"id": k, "name": v} for k, v in items.BUILDS.items()]},
            "odds": dict(zip(items.RARITIES, items.ODDS)),
            "notice": "Points come from work recorded as correct. Estimated grade and GPA are unofficial estimates, not NZQA results.",
        }

    def current():
        user = me_id()
        snap = snapshot(connect, min_answers)
        publish_profile(connect_account, user, snap)
        return snap

    @router.get("/game/me", dependencies=[Depends(authorised)])
    def me():
        return state_json(current())

    @router.post("/game/pull", dependencies=[Depends(authorised)])
    def pull(body: PullBody):
        if body.count not in (1, 10):
            raise HTTPException(422, "Pull 1 or 10 at a time")
        cost = PULL_COST if body.count == 1 else TEN_PULL_COST
        with connect() as db:
            state = lock_state(db)
            snap_stats = read_stats(db, min_answers)
            balance = earnings(snap_stats)[0] + db.execute("SELECT COALESCE(sum(amount), 0) FROM game_ledger").fetchone()[0]
            if balance < cost:
                raise HTTPException(409, f"You need {cost} points; you have {balance}. Correct answers, lessons and passed papers earn points.")
            owned = owned_counts(db)
            results = []
            for _ in range(body.count):
                item_id = pull_once(rng, state)
                results.append({**full(item_id), "new": item_id not in owned})
                owned[item_id] = owned.get(item_id, 0) + 1
                db.execute("INSERT INTO game_items (item_id, count) VALUES (%s, 1) ON CONFLICT (item_id) DO UPDATE SET count = game_items.count + 1", (item_id,))
            db.execute("UPDATE game_state SET pulls=%s, since_rare=%s, since_epic=%s WHERE id = 1", (state["pulls"], state["since_rare"], state["since_epic"]))
            db.execute("INSERT INTO game_ledger (kind, amount) VALUES ('pull', %s)", (-cost,))
        snap = current()
        return {"results": results, "state": state_json(snap)}

    @router.get("/game/shop", dependencies=[Depends(authorised)])
    def shop(slot: str = "", rarity: int = -1, offset: int = 0, limit: int = 60):
        rows = [i for i in items.CATALOG.values() if i["shop"] and (not slot or i["slot"] == slot) and (rarity < 0 or i["rarity"] == rarity)]
        rows.sort(key=lambda i: (i["rarity"], i["slot"], i["name"]))
        limit = max(1, min(limit, 120))
        with connect() as db:
            owned = owned_counts(db)
        page = rows[max(0, offset):max(0, offset) + limit]
        return {"total": len(rows), "items": [{**items.public(i), "owned": owned.get(i["id"], 0)} for i in page]}

    @router.post("/game/shop/buy", dependencies=[Depends(authorised)])
    def buy(body: BuyBody):
        item = items.CATALOG.get(body.item_id)
        if not item or not item["shop"]:
            raise HTTPException(404, "That item is not in the shop. Rare-and-above finds come from the gacha.")
        with connect() as db:
            lock_state(db)
            balance = earnings(read_stats(db, min_answers))[0] + db.execute("SELECT COALESCE(sum(amount), 0) FROM game_ledger").fetchone()[0]
            if balance < item["price"]:
                raise HTTPException(409, f"{item['name']} costs {item['price']} points; you have {balance}.")
            db.execute("INSERT INTO game_items (item_id, count) VALUES (%s, 1) ON CONFLICT (item_id) DO UPDATE SET count = game_items.count + 1", (item["id"],))
            db.execute("INSERT INTO game_ledger (kind, item_id, amount) VALUES ('shop', %s, %s)", (item["id"], -item["price"]))
        return {"bought": full(item["id"]), "state": state_json(current())}

    @router.post("/game/recycle", dependencies=[Depends(authorised)])
    def recycle(body: RecycleBody):
        item = items.CATALOG.get(body.item_id)
        if not item:
            raise HTTPException(404, "Unknown item")
        with connect() as db:
            lock_state(db)
            row = db.execute("SELECT count FROM game_items WHERE item_id = %s", (item["id"],)).fetchone()
            spare = (row[0] if row else 0) - 1
            if spare < 1:
                raise HTTPException(409, "Only spare copies can be recycled; your last copy stays.")
            n = min(body.count, spare)
            refund = round(item["value"] * items.RECYCLE_SHARE) * n
            db.execute("UPDATE game_items SET count = count - %s WHERE item_id = %s", (n, item["id"]))
            db.execute("INSERT INTO game_ledger (kind, item_id, amount) VALUES ('recycle', %s, %s)", (item["id"], refund))
        return {"recycled": n, "refund": refund, "state": state_json(current())}

    @router.put("/game/outfit", dependencies=[Depends(authorised)])
    def outfit(body: OutfitBody):
        with connect() as db:
            lock_state(db)
            if body.skin is not None:
                if body.skin not in items.SKINS:
                    raise HTTPException(422, "Unknown skin tone")
                db.execute("UPDATE game_state SET skin = %s WHERE id = 1", (body.skin,))
            if body.build is not None:
                if body.build not in items.BUILDS:
                    raise HTTPException(422, "Unknown body")
                db.execute("UPDATE game_state SET build = %s WHERE id = 1", (body.build,))
            if body.clear:
                db.execute("DELETE FROM game_outfit")
            if body.slot is not None:
                if body.slot not in items.WORN:
                    raise HTTPException(422, "That slot is not worn")
                if body.item_id is None:
                    db.execute("DELETE FROM game_outfit WHERE slot = %s", (body.slot,))
                else:
                    item = items.CATALOG.get(body.item_id)
                    if not item or item["slot"] != body.slot:
                        raise HTTPException(422, "That item does not go in this slot")
                    if not db.execute("SELECT 1 FROM game_items WHERE item_id = %s", (body.item_id,)).fetchone():
                        raise HTTPException(409, "You do not own that item yet")
                    db.execute("INSERT INTO game_outfit (slot, item_id) VALUES (%s, %s) ON CONFLICT (slot) DO UPDATE SET item_id = EXCLUDED.item_id", (body.slot, body.item_id))
        return state_json(current())

    @router.put("/game/showcase", dependencies=[Depends(authorised)])
    def showcase(body: ShowcaseBody):
        if len(set(body.items)) != len(body.items):
            raise HTTPException(422, "Each item can be shown once")
        with connect() as db:
            lock_state(db)
            owned = owned_counts(db)
            if any(i not in owned for i in body.items):
                raise HTTPException(409, "You can only show items you own")
            db.execute("DELETE FROM game_showcase")
            for position, item_id in enumerate(body.items, 1):
                db.execute("INSERT INTO game_showcase (position, item_id) VALUES (%s, %s)", (position, item_id))
        return state_json(current())

    @router.put("/game/settings", dependencies=[Depends(authorised)])
    def settings(body: SettingsBody):
        with connect() as db:
            lock_state(db)
            if body.visible is not None:
                db.execute("UPDATE game_state SET visible = %s WHERE id = 1", (body.visible,))
        return state_json(current())

    def board_rows(db, board, limit, viewer):
        column, label, unit = BOARDS[board]
        extra = f"AND p.{column} IS NOT NULL" if board in ("grade", "gpa") else f"AND p.{column} > 0"
        ranked = f"""SELECT p.user_id, u.username, p.{column}, p.outfit, p.skin, p.visible, p.networth, p.est_mastery, p.est_gpa,
                RANK() OVER (ORDER BY p.{column} DESC) AS place, p.build FROM game_profiles p JOIN users u ON u.id = p.user_id
                WHERE (p.visible OR p.user_id = %s) {extra}"""
        rows = db.execute(f"SELECT * FROM ({ranked}) r ORDER BY place, username LIMIT %s", (viewer, limit)).fetchall()
        mine = db.execute(f"SELECT * FROM ({ranked}) r WHERE user_id = %s", (viewer, viewer)).fetchone()
        return column, label, unit, rows, mine

    @router.get("/game/leaderboard/{board}", dependencies=[Depends(authorised)])
    def leaderboard(board: str, limit: int = 25):
        if board not in BOARDS:
            raise HTTPException(404, "Unknown leaderboard")
        viewer = me_id()
        current()
        with connect_account() as db:
            column, label, unit, rows, mine = board_rows(db, board, max(1, min(limit, 100)), viewer)
        def value(r):
            if board == "grade":
                return {"value": round(r[2], 3), "text": grade_name(r[2])}
            if board == "gpa":
                return {"value": r[2], "text": f"{r[2]:.2f} / 9"}
            return {"value": r[2], "text": f"{r[2]:,}"}
        def row_json(r):
            return {"rank": r[9], "user_id": r[0], "username": r[1], "outfit": r[3], "skin": r[4], "build": r[10], "hidden": not r[5], **value(r)}
        return {"board": board, "label": label, "unit": unit, "you": viewer,
                "note": "Estimated grade and GPA come from review answers and are unofficial." if board in ("grade", "gpa") else "",
                "rows": [row_json(r) for r in rows], "mine": row_json(mine) if mine else None}

    @router.get("/game/players/{user_id}", dependencies=[Depends(authorised)])
    def player(user_id: int):
        viewer = me_id()
        if user_id == viewer:
            current()
        with connect_account() as db:
            row = db.execute("""SELECT u.username, p.networth, p.questions, p.lessons, p.papers, p.est_mastery, p.est_gpa, p.distinct_items, p.total_items,
                    p.rarest, p.outfit, p.showcase, p.skin, p.visible, p.build FROM game_profiles p JOIN users u ON u.id = p.user_id WHERE p.user_id = %s""", (user_id,)).fetchone()
        if not row or (not row[13] and user_id != viewer):
            raise HTTPException(404, "No such player, or they keep their rewards private")
        return {"user_id": user_id, "username": row[0], "networth": row[1], "questions": row[2], "lessons": row[3], "papers": row[4],
                "estimate": None if row[5] is None else {"grade": grade_name(row[5]), "gpa": row[6]},
                "collection": {"owned": row[7], "total": row[8], "percent": round(100 * row[7] / row[8], 1) if row[8] else 0},
                "rarest": full(row[9]) if row[9] in items.CATALOG else None, "outfit": row[10], "skin": row[12], "build": row[14],
                "showcase": [full(i) for i in row[11] if i in items.CATALOG], "you": user_id == viewer}

    # Public and deterministic: the art of catalogue items and of an outfit given in the query. No account data is involved.
    @router.get("/game/art/item/{item_id}.svg", include_in_schema=False)
    def item_art(item_id: str, skin: str = ""):
        if item_id not in items.CATALOG:
            raise HTTPException(404, "Unknown item")
        return Response(items.item_svg(item_id, skin), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})

    @router.get("/game/art/avatar.svg", include_in_schema=False)
    def avatar_art(request: Request):
        query = request.query_params
        return Response(items.avatar_svg(art_outfit(query), query.get("skin", ""), crop=query.get("crop"), build=query.get("build", "")), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})

    # The same art as PNG for the Android app, which has no SVG renderer. Widths are limited so a request cannot ask for a huge image.
    def png_response(svg, width):
        width = max(32, min(width, 768))
        return Response(items.png(svg, width), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})

    @router.get("/game/art/item/{item_id}.png", include_in_schema=False)
    def item_png(item_id: str, w: int = 256, skin: str = ""):
        if item_id not in items.CATALOG:
            raise HTTPException(404, "Unknown item")
        return png_response(items.item_svg(item_id, skin), w)

    @router.get("/game/art/avatar.png", include_in_schema=False)
    def avatar_png(request: Request, w: int = 400):
        query = request.query_params
        return png_response(items.avatar_svg(art_outfit(query), query.get("skin", ""), crop=query.get("crop"), build=query.get("build", "")), w)

    return router


def refresh_all(connect, connect_account, user_ids, min_answers=5):
    """Keep every account's leaderboard row current (called from the server's periodic tick)."""
    def one():
        publish_profile(connect_account, userspace.current_user.get(), snapshot(connect, min_answers))
        return False
    userspace.each_user(user_ids, one)
