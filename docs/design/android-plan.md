# Android app: catching up with the web app

Written 13 November 2026, after #13 (rewards art), #14 (adaptive answer inputs) and #15 (curriculum and spaced review) were
merged into `main`. The owner's intent: the Android app is a full way to use StudyGuider, not a companion. The target is parity
for everything a student does daily: Home, lessons, review, exams and practice, plan, rewards and settings.

Sources read for this plan: the three PR descriptions, `docs/research/study-methods-and-curricula.md`,
`docs/design/answer-input-catalogue.md`, the web pages (`server/web-*.js`), the server routes they call, and every file under
`android/`.

## 1. What the Android app does today, screen by screen

The app is one activity with Compose screens. State lives in `remember` blocks in `MainActivity.StudyApp`; every screen calls
the server with `HttpURLConnection` and reads `org.json` objects. There is no ViewModel layer and no navigation library: a
bottom bar switches six tabs, and sheets and dialogs sit over them.

| Tab / screen | File | What it does now |
|---|---|---|
| Sign in | `MainActivity.kt` | Server URL, username, password. The token is encrypted with an Android Keystore key and restored on start. |
| Home | `HomeScreen.kt` | Overall mastery, lessons done today, reviews due; lessons to do (Start/Continue); topics with mastery bars and "Estimated: …" or "Needs N more review answers for an estimate"; weak concepts; review counts; recent exams with Resume; a Rewards card. |
| Lesson | `LessonsHome.kt`, `LessonScreen.kt` | Today's lessons and carried-over ones, earlier lessons, "New lesson" (streamed generation). The reader shows one section per page with progress synced to the server, Explain (streamed, with follow-ups, save to notes), sources, AI diagrams. Practice sections ("Your Turn", "Question", "Check", "Quiz") get a plain maths text field; other sections get a "Quick check" built on the device from the section text. Answers autosave to `/lessons/{id}/answers/{key}` with conflict recovery. "Check my answer" goes through `/lessons/{id}/explain` with a 2,000-character limit. |
| Review | `ReviewScreen.kt` | Every question from `/review-questions/due` as a card: question, fill-in table if the wording has one, maths text field, photo (camera or gallery) read into the box, hint, confidence 1-5, Submit. After submitting the card disappears: the verdict, feedback and next date are never shown. |
| Exam | `ExamListScreen.kt`, `ExamScreen.kt`, `RapidScreen.kt`, `RevisionScreen.kt` | Three sections. Papers: past papers and AI practice exams by part, digital or handwritten mode, per-part maths fields and fill-in tables, attaching a photo of a diagram, timer, marking and feedback, overrides, source pages. Rapid: one question at a time, results at the end. Revision: packs built from mistakes. |
| Resources | `MainActivity.ResourceHub`, `TopicFiles.kt`, `SourceScreen.kt` | Subjects by NCEA level, topics, files: upload (several at once, recordings streamed), categories, extract/retry, delete, view pages. Adding a subject only accepts NCEA level 1-3. |
| Learning | `MainActivity.LearningScreen` | Topics being learned (with nightly-run status), the free-text "Teaching method" with teacher-slide analysis, daily reminder, AI usage (admin), progress summary, lesson manager, lesson history, topic notes. |
| Settings (sheet) | `MainActivity.SettingsSheet`, `AccountScreen.kt` | Account (picture, username, password, admin account management), appearance (light/dark/system), about, sign out. |
| Rewards (full-screen dialog) | `RewardsScreen.kt` | Character (body build, skin tone, outfit, wardrobe, showcase, recycle), gacha, shop, leaderboards with head-and-shoulders crops, player cards. Uses the server's PNG art. After #13 only the crop and stage colours changed; it has not been looked at on a device since the redraw. |

## 2. The gap against the web app, feature by feature

### From #15: curriculum and spaced review

| Feature | Web | Android today | Gap |
|---|---|---|---|
| Plan page: set up a programme (NCEA, AUT, UoA, other), hours a week | `web-plan.js` | None | Whole screen |
| Papers: AUT import by code, outline paste or upload, type it in, editable draft with outcomes, weighted dated assessments, semester dates from the calendars | `web-plan.js` | None | Whole flow |
| Per subject: assessments with date, weight and your mark; outcomes/standards; topic-to-outcome links; retention goal; add an NCEA standard and its date | `web-plan.js` | None | Whole flow |
| Today's review list from `/review-plan`: daily limit, left out, ordered by importance | `web-reviews.js` | Uses `/review-questions/due` (every due question, no cap, no order) | Switch to the plan, show cap and left-out |
| Relearning: a miss returns after three other questions in the same session, marked "Again" | `web-reviews.js` | None | Add |
| Answer result: verdict, AI feedback, next review date, confident-miss note | `web-reviews.js` | Never shown | Add |
| Earlier answers to the same question, with drawings | `web-reviews.js` | None | Add |
| All questions: browse, filter by topic and status, search, practise ahead | `web-reviews.js` | None | Add |
| Assessment readiness (predicted recall on the day, at-risk count) | Plan and Home | None | Add to Plan and Home |
| University grade estimates (A+ to D, must-pass flags); NCEA estimates only from full papers | Plan and Home | Home shows the old per-topic estimate, which the server now always sends as null, so every topic says "Needs N more review answers" (wrong) | Use `/grade-estimates`; remove the per-topic line |
| Honest recall numbers: only answered questions count | Home | Shows mastery for every topic including unanswered ones as 0% | Show "—" and "n of m answered" |
| Invitation on Home for existing users | Home | None | Add |
| Lessons in the new structure: pre-questions, worked example to completion problem to full problem, free-recall Your Turn | Server prompt; web shows the sections | The reader shows them, but "Before you start" gets a device-made quick check and the free-recall question looks like any other | Give pre-questions a "have a go" box and label free recall |
| Tone / reading level / pace replace free-text teaching style; old text kept as notes | `web-settings.js` | Free-text "Teaching method" with slide analysis | Replace; keep notes |
| Papers as subjects (level 0-10, kind "paper") | Library and pickers | Add subject refuses anything but 1-3; cards say "NCEA LEVEL n" | Accept papers; group them under "Papers" |

### From #14: adaptive answer inputs

| Feature | Web | Android today | Gap |
|---|---|---|---|
| Each question's answer forms (`answer_forms`) on review items, exam parts, rapid and revision questions; `/answer-forms` for lesson questions | All answer pages | Ignored | Read them and lay the answer out accordingly |
| Text with a symbol bar (Maths, Chemistry, Physics, Greek), inserting at the cursor, `\ce{}` equation line with preview, rendered preview | `web-answer.js` | A text field plus a dialog that appends display maths at the end | New text block |
| Tables: complete a given table, or build your own (add/remove rows and columns) | `web-answer.js` | Fill-in tables only, from Markdown in the wording | Use the form's template; add build-your-own |
| Drawing: pen, line, arrow, label, eraser, undo/redo, clear, three inks, blank/grid/the question's figure | `web-answer.js` | None (exam only: attach a photo) | New native canvas |
| Graph: axes with labels and optional ranges, curve, line, point, label, eraser; a text description for the marker | `web-answer.js` | None | New native canvas plus the same description |
| Drawings uploaded as PNG plus strokes to `/answer-images`, referenced as `![Drawing 1](/answer-images/42)`; strokes reloaded for editing | `web-answer.js` | The reference line shows as text and is preserved on edit, nothing can be drawn | Upload, reference, reload strokes |
| Saved answers show their drawings (review history, lesson answers, exam and rapid results) | `mathText` | Shows the line as text | Render images wherever answers are shown |
| Lesson practice marked by `/lessons/{id}/check` (no 2,000-character limit, drawings go to the marker) | `web-lessons.js` | Uses the explain route | Switch |
| Photo of paper working as the fallback | All | Review only | Keep in review; add to lessons, rapid, revision |

### From #13: rewards art

| Feature | Web | Android today | Gap |
|---|---|---|---|
| Chibi character and items redrawn; `ART_VERSION` 7 | `web-game.js` | Uses the PNG endpoints, so the art is new; layout sized for the old proportions | Look at it on a device and lay it out for the new art (design pass) |
| One stage backdrop behind the character in both themes | `web.css --stage` | Colours copied | Check on device |
| Pets and held things shown alone as icons | Server | Uses the icon PNGs | Check card sizes |

### Multiple choice (in progress on another branch)

A second agent is adding multiple-choice questions and university past-exam import on the server and web. Its contract will be
`docs/api/multiple-choice.md` on its branch. The Android answer box is built so another answer form slots in (section 3, step 2).
When the contract exists, Android gets selectable options (single choice and select-all), and feedback per option, against it.

### Should anything stay web-only?

Judged web-only, with reasons:
- **The advanced manager at `/manage`** (question checks, marking checks, diagram management, exam assembly, saved-lesson
  history for maintenance). These are maintenance tools for the owner, used rarely, wide tables on a big screen. A student does
  not need them daily.
- **Printing an exam** (`/exams/{id}/print`). Printing is a desktop task; a phone can open the web page if needed.
- **Bulk library curation** beyond what Android already has (re-categorising many files, linking standards to topics, searching
  chunks). Android keeps upload (several files, recordings), extract/retry, delete-selected and reading pages, which covers
  getting material in from a phone. Detailed curation is easier on a big screen.

Everything else is in scope.

## 3. Order of work and what each step delivers

Each step ends with a build, a commit and a push to `t3/android-app-parity-with-web`.

1. **Shared foundations.** One small `Api.kt` (GET/POST/PUT/DELETE and multipart with the error detail from the server) for
   new code, so new screens do not each copy another request function. `AnswerContent`: shows saved answer text as blocks
   (rendered maths, native tables, drawings fetched with the token), used everywhere an answer is shown again. Pure-Kotlin
   parsing (`splitAnswer`, table Markdown, image references) with checks in the existing `main()` style, run by one JUnit
   wrapper so `testDebugUnitTest` actually runs them.
2. **The answer box** (`AnswerBox.kt`, `AnswerForms.kt`, `Sketch.kt`, `SymbolBar.kt`). `AnswerForm` is a sealed type (Text,
   Table, Drawing, Graph), parsed from the server's JSON, so multiple choice is one more case. Blocks are laid out from the
   question's forms, filled from saved answer text, and "Add a table / drawing / graph" lets the learner add any other.
   - Text: a `TextFieldValue` field (so symbols go in at the cursor), a scrollable symbol bar with the web's four sets and
     the same LaTeX snippets, a chemistry equation line with live KaTeX preview, and a rendered preview of the answer.
   - Table: complete-the-table (given cells fixed) or build-your-own (rows and columns), written as a Markdown table.
   - Drawing and graph: a Compose canvas in the web's 800-wide coordinate space, so strokes saved on one device open on the
     other. Tools as on the web; drawing over the question's figure; a full-screen mode for drawing comfortably on a phone.
     The PNG is rendered with `android.graphics.Canvas` and uploaded with the strokes JSON a moment after the last change;
     the graph's text description is a port of the web's `describe()`.
   - The answer stays one piece of text, exactly as on the web, so drafts, hints, marking and the web all keep working.
3. **Review.** Today's list from `/review-plan` (cap, left out), one question at a time like the web, the answer box,
   photo fallback, hint, confidence with labels, the result (verdict, feedback, next date, confident miss), relearning
   re-queue, earlier answers with drawings, and an All questions tab with filters and practise-ahead.
4. **Plan.** The Learning tab becomes Plan. First-time setup (where you study, level or programme, hours a week); Today
   (reviews in the list, left out, daily limit, hours); Coming assessments with predicted recall and phase; each programme
   with its subjects or papers: estimate, pass rule, retention goal, assessments (date, weight, mark, remove, add), outcomes or
   standards, topics with outcome links; add an NCEA subject or standard; add a paper by AUT code, by pasting or uploading
   the outline, or by hand, through the editable draft. The old Learning items (lesson manager, history, notes, nightly runs,
   progress summary) stay on the Plan tab under "Your lessons".
5. **Lessons.** Practice answers use the answer box with forms from `/answer-forms` and are checked by
   `/lessons/{id}/check`; saved answers show drawings; "Before you start" pre-questions get a "have a go" box; the free-recall
   Your Turn is labelled "Write what you remember"; worked-example sections no longer get a device-made quick check.
6. **Home.** Plan invitation for accounts without a programme; reviews due with left-out and limit; coming assessments with
   predicted recall; grade estimates; topic recall only from answered questions; the old per-topic estimate removed.
7. **Settings.** A "Study" page: topics you're learning, how explanations read (tone, reading level, pace, with the server's
   descriptions), other notes (the old free text), daily reminder, AI usage for admins. Papers accepted in Resources.
8. **Exams and practice.** Exam parts, rapid and revision use the answer box (forms per part; drawing over the part's
   figure); results show drawings; university grade estimates appear on Home and Plan.
9. **Rewards and the design pass.** Screenshots of every screen go to the design agent, which specifies the Rewards layout for
   the new art, the drawing and graph tools on a phone, the look of the new screens and a consistency pass; I implement it.
10. **Multiple choice**, once `docs/api/multiple-choice.md` exists on the other agent's branch.

## 4. Testing

- Gradle `assembleDebug` and `testDebugUnitTest` locally (JDK 21) and in CI.
- A local server built from this branch's `server/` against a throwaway Postgres in Docker, with throwaway accounts; never
  the real database or the deployed site. The model gateway is used only for marking and lesson checks, one call at a time.
- The Pixel 7a emulator on this machine: every new screen driven and screenshotted, light and dark.
