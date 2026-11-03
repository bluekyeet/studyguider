# StudyGuider website: what it does

A functional spec for designing the website. It says what each screen must let the learner
do, what data and states it has, and which rules the design must not break. It says nothing
about how things should look. Written 3 November 2026 from the code in `server/web*.{html,css,js}`.

## Who uses it, and how

- One learner (a New Zealand NCEA student, Levels 1-3, Physics and Chemistry so far), one
  password, no accounts. The same server backs an Android app. Both must show the same lessons,
  answers and reading position.
- Used on a laptop or a large monitor, and on a phone browser. Both matter.
- All times and "today" are New Zealand time (Pacific/Auckland).
- Maths is everywhere: formulae in `$...$` and `$$...$$` (KaTeX, with chemistry via `\ce{}`).
- Everything the AI writes is unverified study help, not an official NZQA grade. The design must
  keep that visible wherever AI output appears (see "Rules that must survive a redesign").

## Technical limits for whoever builds the design

- No build step and no framework. Plain ES modules, hand-written CSS, served by the Python server.
- Files: `server/web.html` (shell), `server/web.css` (all styling), `web.js` (router),
  `web-common.js` (Markdown and maths rendering, maths input, autosave), and one module per
  area: `web-lessons.js`, `web-reviews.js`, `web-exams.js`, `web-library.js`, `web-settings.js`.
- New files must be added to the allow-list in `server/app.py` (`study_module`) and copied in
  `server/Dockerfile`, or they return 404 in the container.
- The JavaScript builds the screens, so a designer changes mostly `web.css` and `web.html`. Where
  the markup must change, the JS builds it and has to change with it.
- The CSS already uses variables for colour and has a dark theme (follows the system). Phones are
  handled with a breakpoint at 800 px; the lesson reader has extra layouts at 1100 px and 1500 px.
- Icons are inline SVG in `web.html`. The logo is `/branding/wordmark.png` (dark background,
  not transparent) and `/branding/favicon.png`.

## Global shell

- **Sign-in screen** shown when there is no session: password field, Sign in button, error text.
  The sidebar is hidden until sign-in.
- **Navigation**, always visible after sign-in: Home, Lessons, Review, Exams, Library, Settings. The
  current page is marked. Sign out is separate. On wide screens it is a left sidebar; on phones a
  top bar with a scrolling row.
- **Hash routing**: `#lessons`, `#reviews`, `#exams`, `#library`, `#settings`. Library adds
  parameters (`?subject=1&topic=2&tab=files&folder=exams`). Reload and back/forward must work.
- **Page notice**: one line under the nav for errors that belong to no single control.
- **Leave guard**: if a page has unsaved or in-progress work, leaving asks for confirmation. Pages
  signal this with `data-dirty="true"` or `data-busy="true"` on their container.

## Home (`#home`, the default page)

A dense dashboard, not cards. Numbers come from `GET /study-summary` and `GET /lessons`.
- **Headline strip:** overall mastery % (average of the topics being learned), lessons done today, reviews due, topics with a grade estimate.
- **Lessons to do:** a table of today's unfinished lessons (topic, lesson, To do / In progress, Start or Continue). Each opens the lesson directly (`#lessons?lesson=ID`). Below it: Start N reviews, and Resume exam when an exam has some but not all answers.
- **Topics:** mastery % with a bar and an **estimated grade** per topic. The estimate is a rough band from review mastery (under 40% not achieved, 40-59% achieved, 60-79% merit, 80%+ excellence), only shown with 5+ review answers on the topic, and labelled as not an NZQA grade. The rule is printed under the table.
- **Weak concepts** and **Reviews** (30-day correct/incorrect, due/upcoming/total) side by side; **Recent exams** as a table, marks labelled unofficial AI marks.
- No streaks, no predicted exam scores.

## Lessons (`#lessons`)

**List: "Today's lessons"**
- Shows only lessons prepared today (a new one is made overnight for each topic the learner is
  studying). Each is a card: subject and topic, status (To do / In progress / Completed), the
  lesson title, and one button (Start lesson / Continue lesson / Review lesson).
- Header shows the date and "N of M done", or "all done".
- Empty state: no lessons today, with a link to Settings to choose topics.
- Earlier days' lessons are in a collapsed "Earlier lessons (N)" list under today's cards (date, topic, status, Open).

**Reader** (opens when a lesson is chosen)
- A lesson is split into sections by its headings (Overview, Learning goal, Explanation, Worked
  example, Your Turn 1-5, Common mistakes, Summary, and so on). One section is shown at a time.
- Needs: a section outline (numbered, current one marked, jump to any), Previous and Next, a way
  back to the list, and "Complete lesson" on the last section.
- Opens at the section the learner last reached on any device, and saves the position as they move.
- Body is rendered Markdown with maths: headings, bold, italic, bullet and numbered lists
  (nested), tables, quotes, rules, code, links, display and inline maths.
- A banner says the lesson is AI-generated and should be checked against the sources.
- **Practice sections** (titles containing "Your Turn", "question", "check" or "quiz"): the
  learner writes an answer in a text box with a **maths toolbar** (fraction, power, subscript,
  root, times, divide, plus-minus, approx, less/greater-equal, Greek letters, arrows, equilibrium
  arrow, degrees, m s^-1, chemistry) and a **live maths preview**. "Check my answer" asks the AI
  to mark it; the feedback appears under the box (unverified).
- **Autosave**: answers and AI feedback save themselves shortly after typing and on leaving the
  box, and appear on the phone. Status text shows Saving / Saved / Not saved (retrying). If another
  device changed the same answer, show a conflict with two choices: "Keep my version" and "Use
  the other version". Unsaved text is also kept in the browser.
- **Ask about this section**: collapsed by default. A question box, an Explain button, and the
  replies (each can be saved to the topic's notes). Follow-ups remember the last three exchanges.
- **Sources**: collapsed list of the original files and pages the lesson used, plus the raw
  lesson text.

## Review (`#reviews`)

Short spaced-repetition questions made from completed lessons and wrong exam answers.
- Summary numbers: due now, coming up, total.
- **Due now**: questions one at a time. Each shows topic, due date, the concept, the question
  (with maths), an answer box with the maths toolbar, and a **confidence 1-5** choice (required).
  Submitting returns an AI judgement (correct / incorrect / not independently marked), feedback,
  the next due date and a topic mastery estimate. Then Next question, or Finish.
- **All questions**: every saved question, due or not, with filters (topic, status: any/due/
  coming up/never answered, text search). Each row shows concept, snippet, topic, due date, times
  answered, mastery, and Answer or Practise now. Answering early works the same way.
- Empty states: nothing due (offer to browse all), no questions at all.
- An unsent answer survives a reload.

## Exams (`#exams`)

**Set-up**
- Choose subject and topic, then a mode:
  - Original paper: a real past paper's registered questions for a chosen year.
  - Mixed practice: registered questions across years (question count 1-10).
  - AI practice: generated questions with a rubric, clearly **unofficial**.
- Notices under the mode explain limits (registered questions may not cover a whole paper; AI
  practice is not NZQA material). Start exam is disabled until valid.
- **Saved exams** list: each with kind, question count, marks, date, Open and Delete (delete
  asks for confirmation and says question bank entries stay).

**Taking an exam**
- Header: title, kind, total marks (or "marks not recorded"), answer mode, a link to download a
  text-only practice PDF, an optional **timer** (start, pause, resume, reset; browser-only, never
  locks or submits), and question buttons Q1..Qn (answered ones marked).
- One question at a time with Previous and Next.
- A question shows: number, standard (AS 91171), year, marks if known, links to the original paper
  page and marking schedule, a note on which pages hold figures, and the wording split into parts.
- Parts: label beside wording ((a), (b)(i) ...). A question may open with a heading and context
  text. **Only the lowest-level parts get an answer box** (a parent such as (b) just introduces
  (b)(i) and (b)(ii)). Figures from the paper appear under their part; large ones are capped in
  height and open full size on click.
- Answers use the maths toolbar and preview. In exams the symbol bar sits behind a small "Σ Maths" button under each box (one tap) so a multi-part question is not a wall of toolbars; lesson boxes keep it open. A question with no parts has one box. A raw
  text/JSON view is available for structured answers.
- **Autosave** exactly as in lessons (Saving / Saved / conflict choices).
- Buttons per question: Save answer, **Save & mark**, **Load saved feedback**.
- **Feedback view**: AI disclaimer; first mark (marks awarded / available, outcome) with feedback,
  evidence quotes with marks and reasons, missing evidence and next steps; an advisory second
  review when the first was uncertain, with a plain "markers disagree" message; the learner's own
  separate override if set. A compare-with-schedule section shows the registered schedule, or the
  AI rubric labelled unofficial.
- **Switching mode:** an open exam has a "Type answers / Write on paper" switch (as in the Android app). It changes that exam's answer mode on the server and reopens it; unsaved answers prompt before being discarded.
- **Handwritten answers:** when starting an exam the learner chooses "Type my answers" or "Write on paper, then upload photos". In the paper mode the exam page offers an upload of the whole paper (up to 10 PNG/JPEG photos in order, or one PDF, 10 MiB total) and an upload per question. The pages are read by AI (the same recognition the Android app uses); the recognised text appears in the answer box with the message that it is unsaved. It is **not saved or confirmed until the learner presses "Confirm recognised answer"** (or Save answer), and Save & mark is refused until then. Questions with no answer on the uploaded pages keep their saved answer. Marking afterwards uses the saved text, as in typed mode.

## Exams hub: Rapid questions and Exam revision

Exams has three sections, switched at the top of the page (`#exams`, `#exams/rapid`, `#exams/revision`) so the main
menu stays short. The first is the page described above.

**Rapid questions.** Choose a topic, where the questions come from (mix of past-paper and AI, past papers only, AI
only) and a length (10, 20, 30, 50 or unlimited), then start. Questions flash up one at a time with their figures; you
type an answer (maths toolbar), or photograph handwriting, then press Next (Ctrl+Enter), Skip, or End session. There is no
Back, no score and no feedback while the session is open; the server refuses to reveal any. A session in progress is
offered again after a reload. After End session the page shows a grade breakdown (Not achieved, Achieved, Merit, Excellence,
plus Skipped, Unclear and Could not mark when present) as counts and a proportional bar, a note that misses were added to
Exam revision and sent to lessons, and every question with the answer, the AI feedback and quoted evidence, and the schedule
or AI rubric. Grades arrive as marking finishes (no spinner). AI questions are labelled unofficial. Earlier sessions can be reopened.

**Exam revision.** The questions missed or skipped in rapid sessions, grouped by topic with a count on the tab, each showing
your last answer, the feedback and the schedule. Redo starts a rapid session of just those; a question clears when you next get it
Achieved or better. A Show cleared switch lists cleared ones.

## Library (`#library`)

Where files and course structure live. Three levels.
1. **Subjects**: grouped by NCEA level as cards; add a subject (name, level 1-3).
2. **Subject page**: its topics as cards; add a topic; delete the subject (only if empty).
3. **Topic page**, with tabs:
   - **Files**: add files by drop or picker (PDF, Word, PowerPoint, Excel, CSV, text, Markdown,
     HTML, images, ZIP; 50 MiB per upload; duplicates kept once); optional manual category (exam
     paper, exam answers/schedule, slides, extra, or auto-detect). Folder filter (All, Exams, Slides,
     Extra, Sorting), filter by name, select all, bulk delete. Each file: type, name (opens the
     original), status chip (Queued / Processing / Ready / Needs attention), page count, size,
     error text, and Retry, Re-extract, Delete. Status refreshes by itself while files process.
   - **Standards**: standards linked to this topic with their criteria; unlink; link an existing
     standard; add or update a standard (number, title, criteria; saves and links).
   - **Notes**: write notes; list with date; edit (refuses if changed elsewhere); delete. Explain
     replies saved from lessons land here.
   - **Search**: keyword search over the topic's extracted text; results show file, page, standard
     and an excerpt, and link to the original.
   - Delete topic (only if it has no files, notes, lessons or review history).

## Settings (`#settings`)

- **Topics you're learning**: every topic grouped by subject with a switch. Switched-on topics get a
  lesson prepared overnight. Changes save immediately; switching off keeps files and history.
- **Teaching style**: one free-text description of how the learner learns best, applied to all
  lessons and explanations. Save and Revert.
- **AI usage**: period picker (24 h / 7 / 30 / 90 / 365 days); calls, errors, prompt and reply
  tokens; per-model counts; a warning when failures are high; the 20 most recent calls with outcome.
  States that tokens are not a bill.
- **More tools**: link to the advanced tools page.

## Advanced tools (`/manage`, separate page, not part of this redesign)

Developer-style screens kept apart: question parsing and approval, marking check, diagram
generation and review, manual exam assembly, saved-lesson history, scheduled-lesson settings and
run history, review-draft generation, mastery view. Its look is independent.

## Rules that must survive a redesign

1. **AI honesty.** AI lessons, feedback, marks and explanations are labelled unverified wherever
   they appear. AI practice exams say "unofficial". Never present an AI mark as an NZQA grade.
2. **No lost work.** Anything the learner types is autosaved or kept locally; conflicts are shown
   with a choice, never silently overwritten; leaving mid-save is guarded.
3. **Maths first.** Rendered maths must be legible in both themes, scroll horizontally rather than
   overflow, and the maths toolbar must be reachable on a phone.
4. **Text column width.** Reading text should stay a comfortable line length on a 27-inch screen;
   the lesson reader uses outline | text | tools columns at wide widths.
5. **Phone parity.** Every function above works at 390 px wide, with touch targets of 44 px.
6. **Both themes and keyboard use.** Light and dark follow the system; focus is always visible;
   status messages are announced (`role="status"` / `role="alert"`).
7. **Source honesty.** Links to original papers, schedules and files stay one click away from the
   thing they support. Lesson citations are hidden in the text but kept under "sources".
8. **Disabled and busy states** are real: buttons disable during requests; the router relies on
   `data-dirty` and `data-busy`.

9. **Motion is fluid and never a loading screen.** Transitions are eased or spring movements of position and opacity (pages and cards rise in turn, the nav pill glides, bars grow, numbers count up, expanders open smoothly, buttons spring on press). No spinners, skeletons or placeholder animations for waiting. All of it switches off when the system asks for reduced motion.

## Known gaps a designer can plan around

- Lesson history and deleting lessons are not on the website.
- No diagram generation on the website. Uploaded handwriting pages are not shown again after a reload (only the recognised text is kept).
- No reminder settings on the website (reminders are Android-only).
- The Android app asks an extra question at the end of non-practice sections; the website does not.
- No notifications, no multi-user, no onboarding or help pages.

## Where the data comes from (for reference)

Lessons `/lessons`, `/lessons/{id}`, `/lessons/{id}/answers`, `/lessons/{id}/progress`,
`/lessons/{id}/explain`; reviews `/review-questions`, `/review-questions/due`; exams `/exams`,
`/exams/start`, `/exams/{id}`, `/exams/{id}/answers/{q}`, `/exams/{id}/answers/{q}/feedback`;
library `/subjects`, `/subjects/{id}/topics`, `/topics/{id}/resources`, `/topics/{id}/standards`,
`/topics/{id}/notes`, `/topics/{id}/search`; settings `/courses`, `/style-profile`, `/usage`.
Session via `/login`, `/logout`, `/session`.
