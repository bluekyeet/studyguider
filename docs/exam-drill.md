# Exam question drill: writeup

A proposal for a rapid-fire way to practise real exam questions: one question at a time, answer it,
see how you did, and press Next, as many times as you like. Written 4 November 2026 from the current
code and the question bank in the database. Nothing here is built yet.

## 1. The idea

Today a full exam is a heavyweight thing: start an exam, work through a paper, mark each answer. Most
revision is not like that. You want to open the app, get a question on the topic you are weak at, do
it, get feedback, and immediately do another. Ten in a row on the bus, not one paper on Sunday.

The **drill** is that: an endless stream of single exam questions from the question bank, with
immediate feedback and no ceremony, tuned to what you are weak at.

Not in scope: replacing exams, official grading, or anything that pretends an AI mark is an NZQA result.

## 2. How it feels to use

1. Choose what to drill (or accept the default): a topic, a standard, or "weakest first". Optionally a
   year range, or only questions with a diagram, or only ones you got wrong last time.
2. A question appears with its figure. You type an answer (maths toolbar as elsewhere) or photograph a
   handwritten one.
3. **Check** gives feedback in two layers:
   - **Instant (no waiting):** the schedule excerpt or rubric is revealed next to your answer so you can
     compare yourself, and you tap how it went (Got it / Partly / Missed). This always works and costs nothing.
   - **AI mark (optional, a few seconds):** the existing marking runs in the background and its
     evidence-linked feedback fills in under your answer. You do not have to wait for it to press Next.
4. **Next** pulls another question straight away. Marking from earlier questions finishes behind the scenes
   and its results appear when you tap the summary or go back.
5. A session summary: how many you did, how many you rated got-it, time per question, the topics and
   concepts you missed, and a button to turn the misses into review questions.

Keyboard on the website: Ctrl+Enter to check, N for next, S to skip. On the phone: swipe to skip.

## 3. What already exists that this should reuse

- **Question bank:** 241 real questions across the six topics (36 to 45 per topic, years 2012 to 2025) plus 9
  AI-written practice questions. The real ones came from machine routes (PDF layout 187, machine import 36,
  parsed 18); none is recorded as human-reviewed. Each carries its original paper page, schedule page and
  schedule text.
- **Marks are mostly missing.** Only 3 questions per topic have a recorded mark total (Organic chemistry has
  39 of 39). Marking already copes: it uses the N0 to E8 whole-question scale when the schedule has one, else
  the recorded marks, else 1. The drill must therefore think in "how did it go" grades, not in marks out of N.
- **Selection logic:** the "mixed practice" start already prefers questions you have not seen, then the least
  recently used. The drill generalises this.
- **Marking, feedback, overrides, scan transcription and the revision conflict rules** all work per
  (exam, question) and can be reused unchanged.
- **Wrong answers feed review:** a marked-wrong exam answer already queues one grounded review question, with
  de-duplication.
- **Home, mastery and weak concepts** are computed from review answers, so a drill that feeds the review queue
  improves Home with no new maths.
- **Handwriting:** per-question photo upload and confirmation already exist on server, website and Android.
- **Generation fallback:** AI practice questions with a rubric already exist and are labelled unofficial.

## 4. Design

### 4.1 A session is a hidden exam

Reusing the existing exam machinery avoids duplicating marking, answers, overrides and scans. A **drill
session** is an `exams` row with `kind = 'drill'` that grows as you press Next: each Next appends one
`exam_items` row. Everything keyed on (exam_id, question_id) then works as it does today.

Consequences to handle: the Saved exams list and the Home "recent exams" must filter out `kind = 'drill'`; the
drill has its own history view. Deleting a session deletes its answers, as exam deletion does now.

The alternative is a new table of attempts. It would be cleaner to query but would need marking, overrides and
scans re-plumbed. Recommendation: hidden exam now; revisit only if the exam tables become awkward.

### 4.2 Choosing the next question

`POST /drills/{session}/next` returns one question, chosen in this order, with the filters applied:

1. Never seen by this learner (across all exams and drills), preferring topics with low mastery and concepts in
   the weak list.
2. Questions last answered wrong or "partly", oldest first, after a cool-down so a miss does not repeat
   straight away (suggest: not within the last 8 questions).
3. Least recently seen.
4. If the pool is exhausted (the real constraint, see 6) the session says so and offers an unofficial AI
   practice question on the same topic, clearly labelled, or a lower-effort restart of the oldest ones.

Never the same question twice within one session unless the pool is smaller than the session.

### 4.3 What is stored

One row per question per session is already `exam_items` (answer, revision, scan revision). Added:

- `drill_self_grade` per item: got_it, partly, missed, or skipped.
- `seconds_spent` per item (measured in the client, sent with the answer).
- No new marking tables.

Selection history comes from `exam_items`, `markings` and `drill_self_grade`.

### 4.4 API (new, small)

| Endpoint | Purpose |
|---|---|
| `POST /drills` | Start a session with filters (topic, standard, year range, figures only, weak only). |
| `POST /drills/{id}/next` | Append and return the next question, or an exhaustion notice. |
| `PUT /drills/{id}/items/{question}/self-grade` | Record got it / partly / missed / skipped and seconds spent. |
| `GET /drills/{id}/summary` | Counts, time, per-topic and per-concept misses, AI marks that have arrived. |
| `POST /drills/{id}/review` | Queue review questions for the misses (reuses the existing generator and de-duplication). |

Existing endpoints are reused as they are: answer save, feedback (AI mark), override and scan upload.

## 5. Screens

**Website:** a Drill page (or a tab inside Exams) with a slim setup row, then a single-column question card:
wording and figures, answer box with the maths toolbar, **Check**, then the schedule excerpt appears beside it
with the three self-grade buttons and an AI-mark panel that fills in when ready. A thin session strip shows
progress (done, got-it count, time) and Finish opens the summary. The motion already in the site (cards easing
in, numbers counting up) applies; nothing should look like a loading screen while marking runs in the
background.

**Android:** a Drill entry on the Exam tab (or a "Quick questions" button on Home). Same flow; the AI mark
arrives as a collapsed result you can pull up. Swipe left to skip. The handwriting camera flow is one tap.

## 6. Constraints that decide the design

- **The pool is small.** 36 to 45 real questions per topic means a keen learner exhausts a topic in one or two
  sittings. That is why exhaustion handling, recycling by weakness and unofficial AI top-ups are part of the
  first version, not extras.
- **AI marking takes seconds and sometimes fails.** Spamming only feels good if it does not block. Self-grading
  is the primary loop; AI marking is background and optional. A failed mark never blocks Next.
- **Machine-imported questions are unverified.** Wording and figure association can be wrong. The drill must show
  "check against the original" next to the paper and schedule links, as exams do, and never claim human review.
  This is the open policy decision in the task list; the drill makes it more visible because it uses far more
  questions.
- **Schedule text is scrambled** for table-style schedules (columns lose their layout). Show the extracted text as
  plain scrollable text with a link to the original schedule page, as exams do now. Improving the extraction would
  help the drill most, and is a separate piece of work.
- **Marks are missing**, so no scores out of N. Show AI outcome words (not achieved, achieved, merit, excellence)
  labelled unofficial, plus your own got-it / partly / missed.

## 7. Rules that must hold

1. **AI honesty:** AI marks and feedback are labelled unofficial and unverified everywhere, including the summary.
   A self-grade is shown as your own judgement, never merged into an AI mark.
2. **No fabricated verification:** AI-written questions say so. Machine imports are not called reviewed.
3. **No lost work:** answers autosave with the existing conflict handling; leaving mid-answer is guarded.
4. **No streak or points** until you decide what counts as a day. A plain count and time per session are enough.
5. **Real papers stay out of Git:** nothing here adds question text to the repository.
6. **Cost is not a constraint** (you said so), but never run more than one AI marking per question per answer, and
   cache by answer as marking does today.

## 8. Build order

1. **Server:** the five endpoints, selection logic, hidden-exam filter in the exam list and Home. Tests for
   selection order, cool-down, exhaustion, filters, and that drill sessions never appear in Saved exams.
2. **Website:** the Drill page with self-grade, background AI mark, summary and the review hand-off.
3. **Android:** the same flow, reusing the existing question and scan composables.
4. **Smarter selection:** weight by weak concepts and Home mastery; optional "exam conditions" mode with a timer.
5. **Top-ups:** unofficial AI questions when a topic is exhausted, reusing the existing generator.

Rough size: step 1 is a day of server work, steps 2 and 3 a day each, steps 4 and 5 smaller.

## 9. How it should be tested

- **Server:** unit tests for the selection order and cool-down; a real-PostgreSQL check (disposable schema, as
  the existing concurrency checks) that two quick `next` calls never return the same question and that a drill
  session does not appear in `GET /exams`.
- **Browser:** a mock-server run for the flow (check, self-grade, next, skip, summary, review hand-off), a check
  that Next is never blocked while an AI mark is pending, and that a failed AI mark shows a message without
  losing the answer.
- **Live:** one real session per topic through the real gateway to confirm marks arrive in the background.
- **Not provable from the code:** whether the questions are good. That needs your eyes on the machine-imported
  bank (the open "human review" item).

## 10. Decisions needed from you

1. Is "partly" worth having, or should self-grade be just got it / missed?
2. Should a miss automatically create a review question, or only when you press the summary button? (Default
   proposed: only on the button, to avoid flooding the review queue during a long session.)
3. When a topic runs out, do you want AI top-up questions offered automatically, or only on request?
4. Should the drill count towards the Home figures (mastery moves only through review answers today)?
   Proposed: no direct effect; misses flow through reviews.
5. Website only first, or website and Android together?
