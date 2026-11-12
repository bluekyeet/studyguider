import random
from datetime import date, datetime, timedelta, timezone

import pytest

import fsrs_model as fsrs
import review_plan


def test_sanity_table_from_the_research_report():
    # docs/research/study-methods-and-curricula.md, A.5: "Computed from those formulas" table.
    assert round(fsrs.FACTOR, 4) == 0.9803
    multiples = {0.70: 9.29, 0.80: 3.32, 0.85: 1.91, 0.90: 1.00, 0.95: 0.40, 0.97: 0.22}
    for retention, multiple in multiples.items():
        assert round(fsrs.interval_for(1.0, retention), 2) == multiple
    assert [round(fsrs.initial_stability(g), 2) for g in (1, 2, 3, 4)] == [0.21, 1.29, 2.31, 8.30]
    assert [round(fsrs.initial_difficulty(g), 2) for g in (1, 2, 3, 4)] == [6.41, 5.11, 2.12, 1.0]     # Easy clamps up to 1
    assert fsrs.retrievability(7.5, 7.5) == pytest.approx(0.9)


def test_good_every_time_gives_rapidly_growing_intervals():
    # The report's simulation gives about 2, 14, 64, 238, 766 days; it used the updated difficulty in the stability step. The
    # reference library uses the difficulty before the review, which gives slightly shorter gaps. Either way they explode,
    # hence the 365-day cap.
    t, stability, difficulty, last, day, days = datetime(2026, 1, 1, tzinfo=timezone.utc), None, None, None, 0, []
    for _ in range(5):
        stability, difficulty = fsrs.review(stability, difficulty, last, t, fsrs.GOOD)
        last = t
        gap = round(fsrs.interval_for(stability, 0.9))
        day += gap
        days.append(day)
        t += timedelta(days=gap)
    assert days == [2, 13, 59, 222, 719]
    for ours, report in zip(days, [2, 14, 64, 238, 766]):
        assert abs(ours - report) / report < 0.1
    assert fsrs.next_interval_days(stability, 0.9) == 365


def test_lapses_and_same_day_reviews():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    stability, difficulty = fsrs.review(None, None, None, t, fsrs.GOOD)
    later = t + timedelta(days=10)
    forgot, harder = fsrs.review(stability, difficulty, t, later, fsrs.AGAIN)
    assert forgot < stability and harder > difficulty
    remembered, _ = fsrs.review(stability, difficulty, t, later, fsrs.GOOD)
    assert remembered > stability
    same_day, _ = fsrs.review(stability, difficulty, t, t + timedelta(hours=3), fsrs.HARD)
    assert same_day >= stability                 # a pass never lowers stability
    assert fsrs.next_interval_days(0.212, 0.9) == 1     # never less than a day


def test_fuzz_is_deterministic_and_bounded():
    assert fsrs.next_interval_days(30, 0.9, seed="5:3") == fsrs.next_interval_days(30, 0.9, seed="5:3")
    spread = {fsrs.next_interval_days(30, 0.9, seed=f"{i}:1") for i in range(50)}
    assert len(spread) > 1 and min(spread) >= 27 and max(spread) <= 33
    assert fsrs.next_interval_days(2, 0.9, seed="x") == 2      # short gaps are not fuzzed


def test_grade_mapping():
    assert [fsrs.grade_from(False, c) for c in range(1, 6)] == [1, 1, 1, 1, 1]
    assert [fsrs.grade_from(True, c) for c in range(1, 6)] == [2, 2, 3, 3, 4]
    assert [fsrs.grade_from(None, c, marked=False) for c in range(1, 6)] == [1, 1, 2, 3, 3]     # unmarked: never Easy


def test_matches_reference_library():
    reference = pytest.importorskip("fsrs")       # the published py-fsrs package (CI installs fsrs==6.3.2)
    if not hasattr(reference, "Scheduler"):
        pytest.skip("not the py-fsrs package")
    worst = 0.0
    for trial in range(200):
        rng = random.Random(trial)
        scheduler = reference.Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False, maximum_interval=36500)
        card, t = reference.Card(), datetime(2026, 1, 1, tzinfo=timezone.utc)
        stability = difficulty = last = None
        for _ in range(8):
            grade = rng.choice([1, 2, 3, 3, 3, 4])
            card, _ = scheduler.review_card(card, reference.Rating(grade), review_datetime=t)
            stability, difficulty = fsrs.review(stability, difficulty, last, t, grade)
            last = t
            worst = max(worst, abs(card.stability - stability) / card.stability, abs(card.difficulty - difficulty))
            t += timedelta(days=rng.choice([0.3, 1, 1.7, 2, 5, 12.5, 40]))
    assert worst < 1e-9


# ---- planning around assessments ---------------------------------------------------------------------------------------

def exam(days_from, today=date(2026, 3, 1), weight=0.4):
    return {"id": 1, "due_date": today + timedelta(days=days_from), "weight": weight, "title": "Final exam", "kind": "exam", "subject_id": 1}


def test_retention_target_follows_the_calendar():
    today = date(2026, 3, 1)
    assert review_plan.context_for([], "long_term", today) == (0.90, None, "learn")
    target, nxt, phase = review_plan.context_for([exam(60)], "long_term", today)
    assert target == 0.90 and phase == "learn" and nxt["due_date"] == date(2026, 4, 30)
    target, _, phase = review_plan.context_for([exam(7)], "long_term", today)
    assert target == pytest.approx(0.925) and phase == "exam_prep"      # halfway up the 14-day ramp to 0.95
    assert review_plan.context_for([exam(-3)], "long_term", today)[0::2] == (0.85, "maintain")
    assert review_plan.context_for([exam(-3)], "assessment", today)[0] == 0.80


def test_a_review_is_pulled_in_before_an_assessment_when_recall_would_be_low():
    reviewed = datetime(2026, 3, 1, 1, tzinfo=timezone.utc)     # 1 March in New Zealand
    # Stability 30 days: the plain FSRS gap at 0.90 is 30 days, past an exam 20 days away, where recall would be ~0.93: no change.
    assert review_plan.plan_due(30, reviewed, 0.90, exam(20)) == date(2026, 3, 31)
    # Exam 35 days away: recall on the day would be 0.889 < 0.90, so the review moves from day 30 to 20% of 35 = 7 days before it.
    assert review_plan.plan_due(30, reviewed, 0.90, exam(35)) == date(2026, 3, 29)
    # A weak item and an exam in 10 days: due well before the exam, never on the same day as the review.
    due = review_plan.plan_due(2.3, reviewed, 0.9, exam(10))
    assert date(2026, 3, 2) <= due <= date(2026, 3, 9)
    # Exam tomorrow: nothing can land in between, so the FSRS date stands (the item is then in maintenance).
    assert review_plan.plan_due(2.3, reviewed, 0.9, exam(1)) == date(2026, 3, 3)


def test_foundation_papers_get_a_refresher_before_the_next_paper_starts():
    reviewed = datetime(2026, 12, 1, 1, tzinfo=timezone.utc)
    start = date(2027, 2, 22)
    plain = review_plan.plan_due(200, reviewed, 0.85, None)
    refreshed = review_plan.plan_due(200, reviewed, 0.85, None, refresher=start)
    assert plain > start and refreshed == start - timedelta(days=21)


def test_daily_order_blocks_facts_and_interleaves_problems():
    items = [{"id": i, "topic_id": topic, "material": material, "priority": priority}
             for i, (topic, material, priority) in enumerate([(1, "procedure", 0.9), (1, "procedure", 0.8), (2, "procedure", 0.7),
                                                              (2, "fact", 0.5), (1, "fact", 0.4), (2, "fact", 0.3), (3, "concept", 0.2)])]
    order = review_plan.arrange(items)
    assert [i["material"] for i in order[:3]] == ["fact"] * 3
    assert [i["topic_id"] for i in order[:3]] == [1, 2, 2]               # facts grouped by topic
    assert [i["topic_id"] for i in order[3:]] == [1, 2, 3, 1]            # problems round-robin across topics
