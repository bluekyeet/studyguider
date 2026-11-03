# Rapid exam questions: writeup

A rapid-fire way to practise exam questions, plus an Exam revision page for the ones you miss.
Written 4 November 2026 from the current code and question bank, and revised after the product
description from the learner. **Status: built on the server, the website and Android (4 November 2026).**
See section 13 for the decisions that were made and what is and is not verified.

## 1. The idea in one paragraph

Pick a topic and spam questions. They flash up one after another, from real past-paper questions or from
AI-generated ones that were prepared ahead of time so there is never a wait. You answer and move on. You
cannot go back, and you are told nothing about how you are doing. The AI marks each answer quietly in the
background. When you press **End session** you see how you did: a grade for each question, how well the whole
session went, and what you missed. Missed questions are sent to your lessons (so the next lesson revisits
them) and to an **Exam revision** page where you can redo them.

## 2. Where it lives: Exams becomes a hub of three

To save space on the menu bars nothing is added to the main navigation. The existing **Exams** entry opens a
page with three sections:

1. **Classic exam papers**: today's Exams page, unchanged (start a paper, answer, mark).
2. **Rapid questions**: the new feature.
3. **Exam revision**: the new page for missed questions (built after Rapid questions).

Website: a segmented switch at the top of Exams, with addresses `#exams/papers`, `#exams/rapid` and
`#exams/revision` (plain `#exams` keeps meaning Classic exam papers, so old links still work). Android: three
chips at the top of the Exam tab. The bottom bar and the sidebar stay as they are.

## 3. A session, step by step

1. **Set up:** choose a topic. Choose the source of questions: **past-paper questions**, **AI-generated**, or
   **both** (default: past papers first, then AI once the topic's real questions are used up). Optionally
   choose how many (for example 10, 20, 50 or "until I stop").
2. **Flash:** one question fills the screen, with its figure if it has one. You type an answer, or photograph
   a handwritten one. The maths toolbar is available as elsewhere. Pressing **Next** locks that answer and shows
   the next question straight away. **Skip** moves on and counts the question as unanswered.
3. **No going back, no feedback.** There is no Previous button, no running score and no marks shown. The screen
   shows only the question, your answer box and a small count of questions done. Marking happens out of sight.
4. **End session** is always on screen. It ends the session after the current question.
5. **Results:** see section 6.

Pre-generation means Next never waits for the AI to write a question, and marking never waits for you.

## 4. Where the questions come from

### 4.1 Past-paper questions

The bank holds 241 real questions across the six topics (36 to 45 per topic, years 2012 to 2025), each with its
original paper page, schedule page and schedule text. All came from machine routes (PDF layout 187, machine
import 36, parsed 18) and none is recorded as human-reviewed, so the player shows "check against the original"
links after the session, never "verified". Questions you have not seen come first, then the least recently seen.

### 4.1a Parts, not whole questions

An NCEA question is several parts (a), (b), (c)(i), (c)(ii). Some share a set-up and some stand alone, so serving
the whole question is too much for a rapid session. Each paper question is split into its parts
(`server/splitting.py`). A part is stored as its own `exam_questions` row (`source = 'part'`, `parent_id` pointing at the
whole question, label such as `1 d(ii)`), holding:

- only the context that part needs: the shared introduction, the lead-in shared by sub-parts, and, when a part relies on an
  earlier part, that part's wording prefixed `Earlier part (b):`; a self-contained part has no context;
- its own question text, its marks, and its own section of the marking schedule (or the whole schedule if it could not be isolated);
- the figures only if the part refers to a diagram, graph or table.

The model only chooses where to cut. Every word of a part must appear in the paper text (a 92% word check; page furniture
such as page numbers and "ASSESSOR'S USE ONLY" is stripped), and a schedule excerpt must come from the schedule text (85%),
otherwise the excerpt is dropped and the whole schedule is used. A split that fails the check is retried once and then
left whole. Gateway errors do not count as failures: the question stays waiting and the next run tries again.
Splitting runs in the background (and starts again whenever a rapid session starts); `POST /rapid/split` runs it for one topic or all,
and `GET /rapid/split` shows how many are waiting, split, single, failed. Questions waiting to be split are not served. Classic exam
papers, the monthly selection and the paper totals ignore parts.

### 4.2 AI-generated questions, prepared ahead

- When a session starts, the server begins generating questions for the topic and keeps **a buffer of about six
  ready ahead of you**, topping it up as you go. Generation reuses the existing practice-paper generator (a
  question, a rubric with Achievement, Merit and Excellence criteria, and marks).
- Each generated question is reviewed by an independent second model (question and worked answer checked for
  correctness and solvability) **before** it can be served; ones that fail are dropped. This is a safeguard, not
  a guarantee: earlier checks showed the reviewer catches seeded errors but also rejects thin drafts, and
  scientific correctness is never fully verified.
- Generated questions are saved as unofficial AI practice questions, labelled that way everywhere. They have no
  diagrams (text and numbers only), which is a limit of the generator today.
- If generation is slow or fails, the session falls back to real questions, then retries. It never stalls on an
  empty screen and never shows a loading spinner; the learner only sees the next question.

### 4.3 The pool is the real constraint

36 to 45 real questions per topic run out quickly in a spam session. That is why "past papers first, then AI"
is the default and why AI generation is part of the first version rather than an extra.

## 5. Marking in the background

- When you press Next, your answer is saved and a marking job is queued for that question. The existing marking
  is reused: evidence-linked, checked against the schedule (or the AI rubric for generated questions), with a
  second independent mark when the first is uncertain.
- Several marking jobs run at once, so a 30-question session finishes marking within a minute or two of the last
  answer, not 30 times a few seconds afterwards.
- A marking failure never interrupts the session. Failed answers are retried and, if they still fail, shown at
  the end as "could not be marked, try again" with your answer kept.
- **The server enforces the blindfold:** while a rapid session is open, the feedback, marks and override
  endpoints for its questions refuse to answer, so no client can leak results early. They open when you press
  End session.
- Answers cannot be edited after you have moved on (the server rejects changes to a question that already has a
  later question in the session).

## 6. Results after End session

Results appear as soon as they are known and fill in smoothly as late marks arrive (cards and numbers easing in,
never a loading screen).

- **Per question:** the AI's grade for that question: **Not achieved, Achieved, Merit or Excellence** (finer
  N0 to E8 steps are used where the schedule has them), your answer, the schedule or rubric excerpt with a
  link to the original, and the AI's feedback and the evidence it quoted. Real past-paper questions say
  "AI-marked against the schedule, not an NZQA result". Generated questions say "AI-written question and
  rubric, unofficial".
- **Whole session:** how many questions were Not achieved, Achieved, Merit and Excellence, how many were
  skipped, time per question, and the topics and concepts missed.
- **An indicative overall grade** for the session, printed with its rule: a rough band from the average of the
  per-question grades. It is labelled as an estimate that is not an NZQA grade and is not tied to real marks
  (the same honesty rules as the estimated grades on Home).
- **Missed questions** are listed with a button to redo them now.

## 7. Where misses go

A question is **missed** if its grade is Not achieved, or it was skipped or unanswered. (Open decision: whether
a weak Achieved also counts.) Misses are sent two places when the session ends, automatically:

1. **Lessons.** Each miss queues one grounded review question built from the original question and its
   schedule or rubric, with the concept it tests. The overnight lesson generator already takes weak and due
   review concepts and your recent answers, so tomorrow's lesson revisits them. This reuses the existing
   wrong-answer path and its de-duplication, so redoing the same miss does not flood the queue.
2. **Exam revision.** The miss is added to the revision list (section 8).

Note: the lesson path is built and checked with a deterministic model; whether live lessons use the weaknesses
well is still an open item on the task list.

## 8. Exam revision page (the third section)

Revised 3 November 2026. Exam revision is not a list of missed questions. You pick a topic and the server builds a
**revision pack** from the mistakes you have made in it, lesson-like but question-heavy: for each weak concept a short
re-teach (grounded in your resources and the schedules of the questions you missed), then three to five questions, easier
first. Mistakes come from three places: rapid-session misses (including exact parts such as `2 b(ii)`), marked classic exams
(Not achieved) and wrong daily-review answers; review questions that were queued from exam misses are not counted twice.
The topic list shows how many mistakes each topic has; a topic with none cannot build a pack.

- **Generation** is in the background (`server/revision.py`, a few seconds to a minute). One generator call writes the pack; a
  second independent model checks every question and its worked answer, and failed questions are dropped (a section left with fewer
  than two questions goes). Gateway errors are retried. The page shows a quiet status line, never a spinner, and can be left and reopened.
- **Answering** uses the existing daily-review marking: each pack question is saved as a review question, so you get feedback
  straight away, a worked answer after you answer, and a wrong answer comes back tomorrow through spaced repetition. Pack
  questions are due far in the future until answered, so they do not appear in the daily review early.
- **Honesty:** every pack is labelled AI-written and unofficial, shows what it was built from, and is checked by a second model that can miss errors.
- The old list of missed questions and its Redo button were removed; `/exam-revision` and `source: "revision"` remain on the server but no screen uses them.
- Known side effect: unanswered pack questions count in the topic mastery average until they are answered (it is the mean of all review questions in the topic).
- Lesson answers are not a source: they have no right/wrong mark, so there is nothing reliable to learn from.

## 9. How it fits the existing system

- **A session is a hidden exam.** Reuse `exams` and `exam_items` with a new kind, `rapid`, appending one item per
  question. Marking, answers, scans and review hand-off then work on (exam, question) as they do today. The Saved
  exams list and the Home "recent exams" filter out rapid sessions; Rapid questions has its own session history.
- **New small pieces:** a pre-generation buffer per session; a background marking queue that is fully
  asynchronous; the "locked until ended" rule on feedback endpoints; an `ended_at`, a per-question grade
  summary and the revision list.
- **Suggested endpoints:** `POST /rapid` (start with topic, source, count), `POST /rapid/{id}/next` (lock the
  current answer, return the next question), `POST /rapid/{id}/skip`, `POST /rapid/{id}/end`,
  `GET /rapid/{id}/results` (blocked until ended), `GET /exam-revision`, `POST /exam-revision/redo`.
- **Android:** reuses the question rendering, maths input and photo-answer capture; the player screen is new.

## 10. Rules that must hold

1. **AI honesty.** Every AI grade, mark, question and rubric is labelled unofficial. A generated question is
   labelled as AI-written. The overall grade is an estimate and says so.
2. **No fabricated verification.** Machine-imported questions are not called reviewed; AI questions are not called
   correct.
3. **No lost work.** Each answer is saved as you move on; a lost connection must not lose the answers already
   given. If a save fails, the session holds the answer and retries before it lets you finish.
4. **No results until the end.** Enforced by the server, not just the screen.
5. **Real papers stay out of Git.**
6. **Motion is fluid, never a loading screen.** Transitions between questions ease in; waiting for marks shows
   results arriving, not a spinner.

## 11. Build order

1. **Server:** the rapid session, hidden-exam filtering, the pre-generation buffer with its independent review,
   asynchronous marking, the blindfold rule, results and the miss hand-off to review.
2. **Website:** the three-way Exams switch, the Rapid questions player, results.
3. **Exam revision page:** list and redo, website first.
4. **Android:** the same, with the three chips on the Exam tab.

## 12. Testing

- **Server:** the blindfold (feedback refused until ended, answers locked after Next), the question order and
  exhaustion fallback, that failed generation never stalls a session, and that the miss hand-off creates at most
  one review question per miss.
- **Real database:** a disposable schema check that concurrent Next calls never return the same question twice
  and that rapid sessions never appear in the exam list.
- **Browser:** a mock-server run of setup, flash, skip, end, results and redo, with the check that no result text
  exists in the page before End session.
- **Live:** one real session per topic through the real gateway, to see the time to mark and how often generated
  questions are rejected.
- **Cannot be proved from code:** whether the questions are good. That needs your eyes on a sample of generated
  and imported questions.

## 13. Decisions made, and what was built

Decisions (learner, 4 November 2026):

1. A miss is **Not achieved**, or a skipped question. A weak Achieved does not count.
2. **Skip is allowed** and counts as a miss.
3. Session length is **set (10, 20, 30, 50) or unlimited** until End session.
4. Default mix is **both**: past-paper and AI questions alternate (past papers only or AI only are also offered).
5. Results show the **grade breakdown only**; there is no overall estimated grade.
6. **Website and Android were built together.**

Built:

- Server: `server/rapid.py` and `server/rapid_state.py`. A session is a hidden exam (`kind = 'rapid'`) so marking,
  answers and scans are reused; it is excluded from the exam list. Routes: `POST /rapid`, `GET /rapid/active`,
  `GET /rapid/{id}/current`, `POST /rapid/{id}/next`, `POST /rapid/{id}/end`, `GET /rapid/{id}/results`,
  `POST /rapid/{id}/remark`, `GET /rapid`, `GET /exam-revision`, `GET /exam-revision/summary`. A revision redo is
  `POST /rapid` with `source: "revision"`.
- **Blindfold enforced server side:** while a session is open the exam, feedback, override, schedule-grade, marks and
  print routes refuse (409), the question payload carries no schedule or rubric, answers lock when you move on, and a
  miss is neither recorded in Exam revision nor queued as a lesson review until the session ends (the review is held in
  `rapid_pending_reviews` and released at the end).
- AI questions are generated ahead (a buffer of about six, refilled in the background), each reviewed by a second model
  before it can be served; failures are dropped. Marking runs in the background (three at a time) and is retried; results
  fill in as marks arrive.
- Website: Exams is a hub of **Classic exam papers / Rapid questions / Exam revision** (`#exams`, `#exams/rapid`,
  `#exams/revision`), with the count of outstanding misses on the revision tab.
- Android: the same three sections as chips at the top of the Exam tab.

Differences from the plan: handwriting photo upload is on the website player only, not in the Android player; the
Android topic list shows every topic rather than only the ones you are learning; Android shows figures through the
existing authorised image component.
