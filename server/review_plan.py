"""When each review question comes back, and what today's review list holds.

Every question keeps an FSRS memory state (fsrs_model.py) and comes back when its predicted recall falls to a target, so answered
questions return on a growing schedule instead of being asked once. The target depends on the calendar (research D.3):

- No assessment ahead: 0.90.
- An assessment ahead that covers the topic: 0.90, rising to 0.95 over its last 14 days; and if recall on the day would fall
  below the target, the review is pulled forward so one lands about 20% of the remaining time before it (1-28 days).
- Every covering assessment is past: maintenance, 0.85, or 0.80 when the learner only needs it for the assessment. Papers that
  later papers build on ("foundation") also get a refresher in the three weeks before a later paper starts.

Today's list is capped by the learner's study time, ordered by priority when there is a backlog (assessment weight, how much is
forgotten, how close the assessment is), with new questions limited so reviews of known material are not crowded out. Facts are
kept together by topic; problem-solving and explanation questions are interleaved across topics (interleaving helps the first and
hurts word-type material, research A.6). Switched-off topics and paperwork questions never appear.
"""
import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import clock
import fsrs_model as fsrs

BASE_RETENTION = 0.90
EXAM_RETENTION = 0.95
RAMP_DAYS = 14
EXAM_PREP_DAYS = 21          # lessons switch to mixed exam-style practice this close to an assessment
MAINTENANCE = {"assessment": 0.80, "long_term": 0.85, "foundation": 0.85}
DEFAULT_CAP = 40
REVIEW_SHARE = 0.3           # share of daily study time given to reviews
SECONDS_PER_REVIEW = 60

SWITCHED_OFF = "NOT EXISTS (SELECT 1 FROM courses sw WHERE sw.topic_id = {topic} AND NOT sw.active)"


def create_schedule_columns(db):
    for column in ("stability real", "difficulty real", "last_review timestamptz", "reps integer NOT NULL DEFAULT 0",
                   "lapses integer NOT NULL DEFAULT 0", "last_grade smallint", "material text NOT NULL DEFAULT ''"):
        db.execute(f"ALTER TABLE review_questions ADD COLUMN IF NOT EXISTS {column}")
    for column in ("grade smallint", "retrievability real", "elapsed_days real"):
        db.execute(f"ALTER TABLE review_answers ADD COLUMN IF NOT EXISTS {column}")
    backfill_state(db)


def material_of(question, expected=""):
    """Rough kind of material when the generator did not say: calculations are procedures, short cue-answer items facts."""
    text = f"{question}\n{expected}"
    if re.search(r"Relevant formulae|calculate|\$[^$]*[=\d][^$]*\$|\bsolve\b|\bdetermine the value\b|\bwork out\b", text, re.I):
        return "procedure"
    if re.search(r"^\s*(?:what is|define|name|state|what does|which term)\b", question, re.I) and len(question) < 160:
        return "fact"
    return "concept"


def grade_of(correct, confidence, outcome):
    return fsrs.grade_from(bool(correct), confidence, marked=outcome in ("correct", "incorrect"))


def backfill_state(db):
    """Questions answered before FSRS get a memory state by replaying their answers in order. Runs once per question."""
    rows = db.execute("""SELECT q.id, a.answered_at, a.correct, a.confidence, a.outcome FROM review_questions q
        JOIN review_answers a ON a.question_id = q.id WHERE q.reps = 0 AND q.stability IS NULL ORDER BY q.id, a.answered_at, a.id""").fetchall()
    states = {}
    for question_id, answered, correct, confidence, outcome in rows:
        stability, difficulty, last, reps, lapses, _ = states.get(question_id, (None, None, None, 0, 0, None))
        grade = grade_of(correct, confidence, outcome)
        stability, difficulty = fsrs.review(stability, difficulty, last, answered, grade)
        states[question_id] = (stability, difficulty, answered, reps + 1, lapses + (grade == fsrs.AGAIN and reps > 0), grade)
    for question_id, (stability, difficulty, last, reps, lapses, grade) in states.items():
        db.execute("""UPDATE review_questions SET stability = %s, difficulty = %s, last_review = %s, reps = %s, lapses = %s, last_grade = %s
            WHERE id = %s""", (stability, difficulty, last, reps, lapses, grade, question_id))
    if db.execute("SELECT 1 FROM review_questions WHERE material = '' LIMIT 1").fetchone():
        for question_id, question, expected in db.execute("SELECT id, question, expected_answer FROM review_questions WHERE material = ''").fetchall():
            db.execute("UPDATE review_questions SET material = %s WHERE id = %s", (material_of(question, expected), question_id))


# ---- the calendar each topic sits in ------------------------------------------------------------------------------------

def coverage(db, topic_ids=None):
    """topic_id -> assessments covering it (dated ones only), each {id, due_date, weight, title, kind, subject_id}, plus the
    subject's retention goal. A topic is covered by an assessment that names one of its outcomes, by an assessment that names
    no outcomes, and (when the topic has no outcome links) by every assessment of its subject."""
    rows = db.execute("""SELECT t.id, a.id, a.due_date, a.weight_pct, a.credits, a.title, a.kind, t.subject_id
        FROM topics t JOIN assessments a ON a.subject_id = t.subject_id
        WHERE a.due_date IS NOT NULL AND (%s::bigint[] IS NULL OR t.id = ANY(%s))
          AND (NOT EXISTS (SELECT 1 FROM assessment_outcomes ao WHERE ao.assessment_id = a.id)
               OR NOT EXISTS (SELECT 1 FROM topic_outcomes x WHERE x.topic_id = t.id)
               OR EXISTS (SELECT 1 FROM assessment_outcomes ao JOIN topic_outcomes x ON x.outcome_id = ao.outcome_id
                          WHERE ao.assessment_id = a.id AND x.topic_id = t.id))
        ORDER BY a.due_date""", (topic_ids, topic_ids)).fetchall()
    out = defaultdict(list)
    for topic_id, assessment_id, due, weight, credits, title, kind, subject_id in rows:
        share = float(weight) / 100 if weight is not None else min(1.0, float(credits) / 6) if credits is not None else 0.5
        out[topic_id].append({"id": assessment_id, "due_date": due, "weight": share, "title": title, "kind": kind, "subject_id": subject_id})
    return out


def goals(db):
    """topic_id -> (retention goal, foundation refresher wanted)."""
    rows = db.execute("""SELECT t.id, COALESCE(d.retention_goal, 'long_term') FROM topics t
        LEFT JOIN subject_details d ON d.subject_id = t.subject_id""").fetchall()
    return {topic_id: goal for topic_id, goal in rows}


def next_starts(db, today):
    """Start dates of papers still to begin (for foundation refreshers)."""
    return sorted(r[0] for r in db.execute("SELECT start_date FROM subject_details WHERE start_date > %s", (today,)).fetchall())


def context_for(assessments, goal, today):
    """(retention target, the next covering assessment or None, phase) for one topic."""
    upcoming = [a for a in assessments if a["due_date"] >= today]
    if upcoming:
        nxt = upcoming[0]
        days = (nxt["due_date"] - today).days
        target = BASE_RETENTION + (EXAM_RETENTION - BASE_RETENTION) * max(0.0, 1 - days / RAMP_DAYS) if days <= RAMP_DAYS else BASE_RETENTION
        return target, nxt, "exam_prep" if days <= EXAM_PREP_DAYS else "learn"
    if assessments:
        return MAINTENANCE.get(goal, 0.85), None, "maintain"
    return BASE_RETENTION, None, "learn"


def plan_due(stability, last_review, target, exam, seed=None, refresher=None):
    """The date a reviewed question is next due. `last_review` is an aware datetime; dates are New Zealand dates."""
    reviewed_on = last_review.astimezone(clock.NZ).date()
    due = reviewed_on + timedelta(days=fsrs.next_interval_days(stability, target, seed))
    if exam is not None and exam["due_date"] > reviewed_on:
        exam_day = exam["due_date"]
        # Only when recall on the day would otherwise fall below the target does a review get pulled in before it.
        if fsrs.retrievability((exam_day - reviewed_on).days, stability) < target:
            gap = min(28, max(1, round(0.2 * (exam_day - reviewed_on).days)))
            latest = exam_day - timedelta(days=gap)
            if latest <= reviewed_on:
                latest = exam_day - timedelta(days=1)
            if latest > reviewed_on:
                due = min(due, latest)
    if refresher is not None and reviewed_on < refresher - timedelta(days=21) < due:
        due = refresher - timedelta(days=21)
    return max(due, reviewed_on + timedelta(days=1))


def _refresher(goal, starts, today):
    if goal != "foundation":
        return None
    return next((d for d in starts if d > today), None)


def record_review(db, question_id, grade, now):
    """Apply one review to a question's memory state and set its next due date. Returns details for the answer response."""
    row = db.execute("""SELECT q.stability, q.difficulty, q.last_review, q.reps, q.lapses, q.topic_id
        FROM review_questions q WHERE q.id = %s""", (question_id,)).fetchone()
    stability, difficulty, last, reps, lapses, topic_id = row
    elapsed = (now - last).total_seconds() / 86400 if last else None
    before = fsrs.retrievability(elapsed, stability) if last and stability else None
    stability, difficulty = fsrs.review(stability, difficulty, last, now, grade)
    today = now.astimezone(clock.NZ).date()
    target, exam, _ = context_for(coverage(db, [topic_id]).get(topic_id, []), goals(db).get(topic_id, "long_term"), today)
    due = plan_due(stability, now, target, exam, seed=f"{question_id}:{reps + 1}",
                   refresher=_refresher(goals(db).get(topic_id), next_starts(db, today), today))
    db.execute("""UPDATE review_questions SET stability = %s, difficulty = %s, last_review = %s, reps = reps + 1,
            lapses = lapses + %s, last_grade = %s, due_date = %s, interval_days = %s, mastery = %s WHERE id = %s""",
               (stability, difficulty, now, int(grade == fsrs.AGAIN and reps > 0), grade, due, (due - today).days,
                fsrs.retrievability((due - today).days, stability), question_id))
    refresh_topics(db, [topic_id], now)
    return {"grade": grade, "retrievability_before": before, "elapsed_days": elapsed, "next_due": due,
            "interval_days": (due - today).days, "stability": stability, "relearn": grade == fsrs.AGAIN,
            "exam": exam}


def replan(db, today=None, subject_id=None):
    """Recompute due dates of reviewed questions (after assessment dates change, and nightly)."""
    today = today or clock.today()
    topics = None
    if subject_id is not None:
        topics = [r[0] for r in db.execute("SELECT id FROM topics WHERE subject_id = %s", (subject_id,)).fetchall()]
        if not topics:
            return 0
    covered, goal, starts = coverage(db, topics), goals(db), next_starts(db, today)
    changed = 0
    for question_id, topic_id, stability, last, reps, due in db.execute("""SELECT id, topic_id, stability, last_review, reps, due_date
            FROM review_questions WHERE reps > 0 AND stability IS NOT NULL AND (%s::bigint[] IS NULL OR topic_id = ANY(%s))""",
                                                                         (topics, topics)).fetchall():
        target, exam, _ = context_for(covered.get(topic_id, []), goal.get(topic_id, "long_term"), today)
        new_due = plan_due(stability, last, target, exam, seed=f"{question_id}:{reps}", refresher=_refresher(goal.get(topic_id), starts, today))
        if new_due != due:
            db.execute("UPDATE review_questions SET due_date = %s WHERE id = %s", (new_due, question_id))
            changed += 1
    return changed


def refresh_topics(db, topic_ids=None, now=None):
    """Topic mastery is the average predicted recall now over questions that have been reviewed. Questions never answered are
    not counted as zero: they are coverage, reported separately."""
    now = now or clock.now()
    rows = db.execute("""SELECT t.id, q.stability, q.last_review FROM topics t LEFT JOIN review_questions q
        ON q.topic_id = t.id AND q.reps > 0 AND q.stability IS NOT NULL
        WHERE (%s::bigint[] IS NULL OR t.id = ANY(%s))""", (topic_ids, topic_ids)).fetchall()
    recall = defaultdict(list)
    for topic_id, stability, last in rows:
        recall[topic_id]
        if stability is not None:
            recall[topic_id].append(fsrs.retrievability((now - last).total_seconds() / 86400, stability))
    for topic_id, values in recall.items():
        mastery = sum(values) / len(values) if values else 0.0
        status = "not_started" if not values else "secure" if mastery >= 0.9 else "review" if mastery >= 0.75 else "learning"
        db.execute("UPDATE topics SET mastery = %s, status = %s WHERE id = %s AND (mastery, status) IS DISTINCT FROM (%s, %s)",
                   (mastery, status, topic_id, mastery, status))


def seconds_per_review(db, now):
    """Measured from the gaps between answers given within a few minutes of each other in the last 30 days."""
    rows = db.execute("""SELECT extract(epoch FROM answered_at - lag(answered_at) OVER (ORDER BY answered_at))
        FROM review_answers WHERE answered_at > %s""", (now - timedelta(days=30),)).fetchall()
    gaps = sorted(float(r[0]) for r in rows if r[0] is not None and 5 < float(r[0]) < 900)
    if len(gaps) < 10:
        return SECONDS_PER_REVIEW
    return min(300, max(20, gaps[len(gaps) // 2]))


def daily_cap(db, now):
    row = db.execute("SELECT value FROM settings WHERE key = 'hours_per_week'").fetchone()
    if not row:
        return DEFAULT_CAP, None
    minutes = float(row[0]) * 60 / 7 * REVIEW_SHARE
    return int(min(200, max(10, round(minutes * 60 / seconds_per_review(db, now))))), float(row[0])


def daily_plan(db, today=None, now=None, is_admin_question=None, repeats=None):
    """Today's review list and what was left out. Returns (rows, info); each row is a dict."""
    today = today or clock.today()
    now = now or clock.now()
    rows = db.execute("""SELECT q.id, q.topic_id, q.question, q.due_date, q.concept, q.standard_number, q.mastery, t.name,
            q.exam_origin, q.stability, q.last_review, q.reps, q.material, q.expected_answer, s.name
        FROM review_questions q JOIN topics t ON t.id = q.topic_id JOIN subjects s ON s.id = t.subject_id
        WHERE q.due_date <= %s AND """ + SWITCHED_OFF.format(topic="q.topic_id") + """
        ORDER BY q.due_date, q.id""", (today,)).fetchall()
    covered, goal = coverage(db), goals(db)
    seen = {}
    if repeats is not None:
        for topic_id, question, origin in db.execute("""SELECT q.topic_id, q.question, q.exam_origin FROM review_questions q
                WHERE q.reps > 0""").fetchall():
            seen.setdefault(topic_id, []).append((repeats.plain(question), origin))
    reviews, new = [], []
    for r in rows:
        if is_admin_question and is_admin_question(r[2], r[4]):
            continue
        item = {"id": r[0], "topic_id": r[1], "question": r[2], "due_date": r[3], "concept": r[4], "standard_number": r[5],
                "mastery": r[6], "topic": r[7], "subject": r[14], "material": r[12] or material_of(r[2], r[13]), "reps": r[11]}
        target, exam, phase = context_for(covered.get(r[1], []), goal.get(r[1], "long_term"), today)
        closeness = 1 / (1 + (exam["due_date"] - today).days / 14) if exam else 0.2 if phase == "maintain" else 0.3
        weight = exam["weight"] if exam else 0.5
        if exam:
            item["assessment"] = {"title": exam["title"], "due_date": exam["due_date"]}
        if r[11] > 0 and r[9] is not None:
            recall = fsrs.retrievability((now - r[10]).total_seconds() / 86400, r[9])
            item["recall"] = round(recall, 3)
            item["priority"] = weight * (1 - recall + 0.05) * closeness
            reviews.append(item)
        else:
            if repeats is not None:
                here = seen.setdefault(r[1], [])
                if repeats.repeats(r[2], r[8], here):
                    continue        # the same question again in other words: the answered one already carries the memory
                here.append((repeats.plain(r[2]), r[8]))
            item["priority"] = weight * closeness
            new.append(item)
    cap, hours = daily_cap(db, now)
    reviews.sort(key=lambda i: (-i["priority"], i["due_date"], i["id"]))
    chosen = reviews[:cap]
    new_cap = max(5, cap // 4)
    room = min(new_cap, cap - len(chosen))
    new.sort(key=lambda i: (-i["priority"], i["due_date"], i["id"]))
    chosen += new[:max(0, room)]
    info = {"cap": cap, "hours_per_week": hours, "due_reviews": len(reviews), "due_new": len(new),
            "left_out": len(reviews) + len(new) - len(chosen)}
    return arrange(chosen), info


def arrange(items):
    """Facts first, grouped by topic (blocking is better for word-type material); then problems and explanations round-robin
    across topics, highest priority first within each topic (interleaving)."""
    facts = sorted((i for i in items if i["material"] == "fact"), key=lambda i: (i["topic_id"], -i["priority"]))
    by_topic = defaultdict(list)
    for item in sorted((i for i in items if i["material"] != "fact"), key=lambda i: -i["priority"]):
        by_topic[item["topic_id"]].append(item)
    mixed, queues = [], list(by_topic.values())
    while queues:
        for queue in list(queues):
            mixed.append(queue.pop(0))
            if not queue:
                queues.remove(queue)
    return facts + mixed


def topic_phase(db, topic_id, today=None):
    """'learn', 'exam_prep' or 'maintain' for a topic, with its next assessment (for lesson planning)."""
    today = today or clock.today()
    _, exam, phase = context_for(coverage(db, [topic_id]).get(topic_id, []), goals(db).get(topic_id, "long_term"), today)
    return phase, exam


def readiness(db, today=None):
    """For each upcoming dated assessment: predicted recall on the day (if nothing more is reviewed) across the reviewed
    questions it covers, how many are at risk, and how many questions there are yet to answer."""
    today = today or clock.today()
    covered = coverage(db)
    questions = db.execute("""SELECT q.topic_id, q.stability, q.last_review, q.reps FROM review_questions q
        WHERE """ + SWITCHED_OFF.format(topic="q.topic_id")).fetchall()
    by_topic = defaultdict(list)
    for topic_id, stability, last, reps in questions:
        by_topic[topic_id].append((stability, last, reps))
    out = {}
    for topic_id, assessments in covered.items():
        for a in assessments:
            if a["due_date"] < today:
                continue
            entry = out.setdefault(a["id"], {"assessment_id": a["id"], "title": a["title"], "due_date": a["due_date"],
                                             "days": (a["due_date"] - today).days, "recall": [], "unanswered": 0, "topics": 0})
            entry["topics"] += 1
            day = datetime.combine(a["due_date"], datetime.min.time(), clock.NZ)
            for stability, last, reps in by_topic.get(topic_id, []):
                if reps and stability:
                    entry["recall"].append(fsrs.retrievability((day - last).total_seconds() / 86400, stability))
                else:
                    entry["unanswered"] += 1
    result = []
    for entry in sorted(out.values(), key=lambda e: e["due_date"]):
        values = entry.pop("recall")
        entry["reviewed"] = len(values)
        entry["predicted_recall"] = round(sum(values) / len(values), 3) if values else None
        entry["at_risk"] = sum(1 for v in values if v < 0.85)
        result.append(entry)
    return result
