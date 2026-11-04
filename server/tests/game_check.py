"""End-to-end check of the rewards API on a throwaway PostgreSQL (never the real database).

    docker run -d --name gametest-db -e POSTGRES_PASSWORD=t -e POSTGRES_USER=t -e POSTGRES_DB=t -p 54329:5432 pgvector/pgvector:pg17
    docker run --rm -v <repo>/server:/app -w /app -e PYTHONPATH=/app -e DATABASE_URL=postgresql://t:t@host.docker.internal:54329/t \
        studylarper-api python tests/game_check.py
"""
import random

from fastapi import FastAPI, Header
from fastapi.testclient import TestClient

import app as study
import game
import game_items as items
import userspace
from accounts import create_account_tables

accounts_db = study.connect_account
with accounts_db() as db:
    create_account_tables(db)
    game.create_public_game_tables(db)
    db.execute("DELETE FROM users")
    ids = [db.execute("INSERT INTO users (username, password_hash) VALUES (%s, 'x') RETURNING id", (name,)).fetchone()[0] for name in ("ann", "ben")]
    db.commit()

for uid in ids:
    with userspace.as_user(uid):
        with study.connect() as db:
            db.execute(f'DROP SCHEMA IF EXISTS "u{uid}" CASCADE')
            db.execute(f'CREATE SCHEMA "u{uid}"')
        with study.connect() as db:
            study.init_schema(db)


def seed(uid, correct, wrong, lessons):
    with userspace.as_user(uid), study.connect() as db:
        subject = db.execute("INSERT INTO subjects (name, level) VALUES ('Chem', 2) RETURNING id").fetchone()[0]
        topic = db.execute("INSERT INTO topics (subject_id, name) VALUES (%s, 'Acids') RETURNING id", (subject,)).fetchone()[0]
        db.execute("INSERT INTO courses (topic_id) VALUES (%s)", (topic,))
        db.execute("UPDATE topics SET mastery = %s WHERE id = %s", (0.7, topic))
        for n in range(correct + wrong):
            q = db.execute("""INSERT INTO review_questions (topic_id, question, due_date) VALUES (%s, %s, current_date) RETURNING id""", (topic, f"q{n}")).fetchone()[0]
            db.execute("INSERT INTO review_answers (question_id, answer, confidence, correct) VALUES (%s, 'a', 3, %s)", (q, n < correct))
        for n in range(lessons):
            db.execute("""INSERT INTO lessons (topic_id, query, lesson, review_status, sources, standards, completed_at)
                VALUES (%s, 'q', 'l', 'ok', '[]'::jsonb, '[]'::jsonb, now())""", (topic,))


seed(ids[0], 190, 2, 2)      # 190 correct x5 + 2 lessons x25 + 1 day x10 = 1010, plus the welcome gift of 200
seed(ids[1], 0, 3, 0)

api = FastAPI()


async def auth(x_user: int = Header(default=1)):
    userspace.current_user.set(x_user)


api.include_router(game.game_router(study.connect, accounts_db, auth, rng=random.Random(7)))
client = TestClient(api)
ann, ben = {"X-User": str(ids[0])}, {"X-User": str(ids[1])}

me = client.get("/game/me", headers=ann).json()
assert me["earned"] == 190 * 5 + 2 * 25 + 10, me["earned"]
assert me["balance"] == me["earned"] + 200 and me["stats"]["questions"] == 190 and me["stats"]["lessons"] == 2, me
assert me["estimate"]["grade"] == "Merit" and me["estimate"]["gpa"] == 6.0, me["estimate"]
assert client.get("/game/me", headers=ann).json()["balance"] == me["balance"], "reading twice must not pay twice"
assert client.get("/game/me", headers=ben).json()["balance"] == 200

too_much = client.post("/game/pull", json={"count": 10}, headers=ben)
assert too_much.status_code == 409, too_much.text
assert client.post("/game/pull", json={"count": 3}, headers=ann).status_code == 422

pulled = client.post("/game/pull", json={"count": 10}, headers=ann).json()
assert len(pulled["results"]) == 10 and pulled["state"]["balance"] == me["balance"] - 900
assert sum(i["count"] for i in pulled["state"]["owned"]) == 10
assert pulled["state"]["pity"]["pulls"] == 10

buy = client.post("/game/shop/buy", json={"item_id": "hat.cap.red"}, headers=ann)
assert buy.status_code == 200, buy.text
assert client.post("/game/shop/buy", json={"item_id": "hat.crown.rainbow"}, headers=ann).status_code == 404     # gacha only
shop = client.get("/game/shop?slot=hat&rarity=0", headers=ann).json()
assert shop["total"] > 10 and all(i["shop"] and i["slot"] == "hat" for i in shop["items"])

# wearing needs ownership and the right slot
assert client.put("/game/outfit", json={"slot": "hat", "item_id": "hat.cap.red"}, headers=ann).status_code == 200
assert client.put("/game/outfit", json={"slot": "hat", "item_id": "hat.cap.blue"}, headers=ann).status_code == 409
assert client.put("/game/outfit", json={"slot": "top", "item_id": "hat.cap.red"}, headers=ann).status_code == 422
state = client.put("/game/outfit", json={"skin": "cocoa"}, headers=ann).json()
assert state["outfit"] == {"hat": "hat.cap.red"} and state["skin"] == "cocoa"

# the body choice is saved, validated, published to the boards and drawn
assert client.put("/game/outfit", json={"build": "feminine"}, headers=ann).json()["build"] == "feminine"
assert client.put("/game/outfit", json={"build": "robot"}, headers=ann).status_code == 422
assert {b["id"] for b in client.get("/game/me", headers=ann).json()["catalog"]["builds"]} == {"masculine", "feminine"}
fem = client.get("/game/art/avatar.svg?build=feminine").text
assert fem != client.get("/game/art/avatar.svg?build=masculine").text and "#d9566b" in fem      # lips on the feminine face
assert client.get("/game/art/avatar.png?build=feminine&w=120").headers["content-type"] == "image/png"

# duplicates stack and spare copies recycle; the last one stays
client.post("/game/shop/buy", json={"item_id": "hat.cap.red"}, headers=ann)
before = client.get("/game/me", headers=ann).json()
recycled = client.post("/game/recycle", json={"item_id": "hat.cap.red", "count": 5}, headers=ann).json()
assert recycled["recycled"] == 1 and recycled["refund"] == round(10 * items.RECYCLE_SHARE)
assert client.post("/game/recycle", json={"item_id": "hat.cap.red"}, headers=ann).status_code == 409

# showcase
own = [i["id"] for i in client.get("/game/me", headers=ann).json()["owned"]][:3]
assert client.put("/game/showcase", json={"items": own}, headers=ann).json()["showcase"] == own
assert client.put("/game/showcase", json={"items": ["hat.crown.gold"]}, headers=ann).status_code == 409

# leaderboards
client.get("/game/me", headers=ben)
board = client.get("/game/leaderboard/networth", headers=ben).json()
assert [r["username"] for r in board["rows"]][0] == "ann" and board["rows"][0]["rank"] == 1
assert client.get("/game/leaderboard/questions", headers=ben).json()["rows"][0]["value"] == 190
assert [r["username"] for r in client.get("/game/leaderboard/grade", headers=ben).json()["rows"]] == ["ann"]      # ben has too few answers
assert client.get("/game/leaderboard/nope", headers=ben).status_code == 404

# privacy: hiding removes you from other people's boards but not from your own
client.put("/game/settings", json={"visible": False}, headers=ann)
assert "ann" not in [r["username"] for r in client.get("/game/leaderboard/networth", headers=ben).json()["rows"]]
assert "ann" in [r["username"] for r in client.get("/game/leaderboard/networth", headers=ann).json()["rows"]]
assert client.get(f"/game/players/{ids[0]}", headers=ben).status_code == 404
client.put("/game/settings", json={"visible": True}, headers=ann)
card = client.get(f"/game/players/{ids[0]}", headers=ben).json()
assert card["build"] == "feminine"
assert client.get("/game/leaderboard/networth", headers=ben).json()["rows"][0]["build"] == "feminine"
assert card["username"] == "ann" and card["showcase"] and card["outfit"] == {"hat": "hat.cap.red"} and card["collection"]["total"] == len(items.CATALOG)

# art
svg = client.get("/game/art/avatar.svg?hat=hat.cap.red&skin=cocoa&top=hat.cap.red")
assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml") and "hat.cap" not in svg.text
assert client.get("/game/art/item/hat.wizard.galaxy.svg").status_code == 200
assert client.get("/game/art/item/nope.svg").status_code == 404

game.refresh_all(study.connect, accounts_db, lambda: ids)
print("rewards check passed")
