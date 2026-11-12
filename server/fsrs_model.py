"""FSRS-6 memory model: how likely an item is to be recalled, and when to ask it again.

Each review item carries stability S (days for recall to fall from 100% to 90%), difficulty D (1-10) and the time of its last
review. A review is graded 1 Again, 2 Hard, 3 Good, 4 Easy. Formulas and the 21 default weights follow the FSRS-6 description in
docs/research/study-methods-and-curricula.md (A.5) and the reference py-fsrs 6.x implementation: the new stability is computed
from the difficulty, stability and recall probability before the review, then the difficulty is updated; a review less than a
day after the last uses the short-term formula. Weights are the published defaults; one learner has too few reviews to fit them.
"""
import hashlib
import math
from datetime import datetime, timedelta

W = (0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722, 0.1666,
     0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014, 1.8729, 0.5425, 0.0912, 0.0658, 0.1542)
DECAY = -W[20]
FACTOR = 0.9 ** (1 / DECAY) - 1
STABILITY_MIN = 0.001
MAX_INTERVAL = 365          # days; school and university material is re-planned at least yearly (research D.1.2)
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4


def retrievability(elapsed_days, stability):
    """Probability of recall after `elapsed_days` (may be fractional) for an item of this stability."""
    if stability is None or stability <= 0:
        return 0.0
    return (1 + FACTOR * max(0.0, elapsed_days) / stability) ** DECAY


def interval_for(stability, retention):
    """Days until recall falls to `retention` (unrounded). Equals S when retention is 0.9."""
    return stability / FACTOR * (retention ** (1 / DECAY) - 1)


def _clamp_d(value):
    return min(10.0, max(1.0, value))


def initial_stability(grade):
    return max(W[grade - 1], STABILITY_MIN)


def initial_difficulty(grade, clamp=True):
    value = W[4] - math.exp(W[5] * (grade - 1)) + 1
    return _clamp_d(value) if clamp else value


def next_difficulty(difficulty, grade):
    delta = -W[6] * (grade - 3)
    damped = difficulty + delta * (10 - difficulty) / 9
    return _clamp_d(W[7] * initial_difficulty(EASY, clamp=False) + (1 - W[7]) * damped)


def short_term_stability(stability, grade):
    increase = math.exp(W[17] * (grade - 3 + W[18])) * stability ** (-W[19])
    if grade >= HARD:
        increase = max(increase, 1.0)
    return max(STABILITY_MIN, stability * increase)


def recall_stability(difficulty, stability, recall, grade):
    hard = W[15] if grade == HARD else 1.0
    easy = W[16] if grade == EASY else 1.0
    return max(STABILITY_MIN, stability * (1 + math.exp(W[8]) * (11 - difficulty) * stability ** (-W[9])
                                           * (math.exp((1 - recall) * W[10]) - 1) * hard * easy))


def forget_stability(difficulty, stability, recall):
    long_term = W[11] * difficulty ** (-W[12]) * ((stability + 1) ** W[13] - 1) * math.exp((1 - recall) * W[14])
    short_term = stability / math.exp(W[17] * W[18])
    return max(STABILITY_MIN, min(long_term, short_term))


def review(stability, difficulty, last_review, now, grade):
    """New (stability, difficulty) after a review graded `grade` at `now`. `stability` is None for a first review."""
    if grade not in (AGAIN, HARD, GOOD, EASY):
        raise ValueError("grade must be 1-4")
    if stability is None or difficulty is None or last_review is None:
        return initial_stability(grade), initial_difficulty(grade)
    elapsed = (now - last_review).days      # whole days, as the reference implementation counts them
    if elapsed < 1:
        new_stability = short_term_stability(stability, grade)
    else:
        recall = retrievability(elapsed, stability)
        new_stability = forget_stability(difficulty, stability, recall) if grade == AGAIN \
            else recall_stability(difficulty, stability, recall, grade)
    return new_stability, next_difficulty(difficulty, grade)


def _fuzz(days, seed):
    """Spread due dates so items learned together do not all fall due on one day (py-fsrs fuzz ranges). Deterministic per seed."""
    if days < 2.5:
        return days
    delta = 1.0
    for start, end, factor in ((2.5, 7.0, 0.15), (7.0, 20.0, 0.1), (20.0, math.inf, 0.05)):
        delta += factor * max(0.0, min(days, end) - start)
    low, high = max(2, round(days - delta)), min(round(days + delta), MAX_INTERVAL)
    span = high - low + 1
    pick = int(hashlib.sha256(str(seed).encode()).hexdigest()[:8], 16) % max(span, 1)
    return low + pick


def next_interval_days(stability, retention, seed=None, maximum=MAX_INTERVAL):
    """Whole days until the next review: at least 1, at most `maximum`, fuzzed when a seed is given."""
    days = min(maximum, max(1, round(interval_for(stability, retention))))
    if seed is not None:
        days = min(maximum, max(1, _fuzz(days, seed)))
    return days


def grade_from(correct, confidence, marked=True):
    """Map the app's signals to an FSRS grade (research D.1.3). Confidence is asked before the answer is revealed.

    AI-marked: wrong -> Again; right with confidence 1-2 -> Hard, 3-4 -> Good, 5 -> Easy.
    Unmarked (marking unavailable): confidence alone, never Easy: 1-2 -> Again, 3 -> Hard, 4-5 -> Good.
    """
    if not marked:
        return AGAIN if confidence <= 2 else HARD if confidence == 3 else GOOD
    if not correct:
        return AGAIN
    return HARD if confidence <= 2 else GOOD if confidence <= 4 else EASY


def due_after(last_review: datetime, days: int) -> datetime:
    return last_review + timedelta(days=days)
