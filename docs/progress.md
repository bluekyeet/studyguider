# StudyGuider progress

Status key: **not verified** means the requested end-to-end acceptance test has
not passed, even if part of the implementation exists. This inventory is based
on `writeup.md` and the existing prototype, not a claim of completed features.

## Roadmap and features

- 2026-11-01 Lessons feed prototype: Android groups saved lessons by their
  Auckland creation date, with earlier dates in history; the topic-only button
  requests generation using the topic name. Emulator showed the feed, topic
  picker, loading state and a generated draft. This is not a due/completion
  system: automatic daily generation for enrolled courses, completion tracking,
  full history pagination and catch-up scheduling are not implemented. Topic-name
  search can fail even when relevant resources exist. Screenshots:
  `shots/lessons-redo-home.png`, `shots/lessons-redo-loading.png`,
  `shots/lessons-redo-generated.png`; visual inspection not verified.

- [ ] Foundation — local Compose API/database, single-user login and lockout,
  Android and web shells, subjects/topics/standards, migrations and seed data,
  GitHub CI, 9Router gateway, Cloudflare Tunnel, Proxmox deployment and backups.
- [ ] Resources and lessons — four resource categories, uploads and deduplication,
  processing status and removal, PDF/Office/text/HTML/spreadsheet/image and
  Google imports, page/slide images and OCR, tagging, embeddings and isolated
  retrieval, editable teaching style and slide profiles, grounded structured
  lessons with citations and two-model review/revision, Generate now, streaming,
  maths rendering and Explain in detail with follow-up chat and notes.
- [ ] Daily loop — review generation and marking, confidence, concept mastery,
  spaced repetition, learner summaries, nightly local-time generation based on
  results, reviewer verdicts, retries and visible failure handling.
- [ ] Exam system — paper/schedule parsing, figures and marks, human verification,
  verified question bank, monthly balanced non-repeating real-question papers,
  timer and typed/photo working, strict evidence-linked marking, second marking,
  disagreements, grades, comparison, overrides and review feedback.
- [ ] Polish — reviewed diagrams, LaTeX/mhchem rendering, `/latex` input and live
  preview, maths toolbar, handwriting conversion, reminders, verified backups,
  usage/cost dashboard, throttling, prompt override and privacy safeguards.

## Acceptance tests — all not verified

- [ ] Ingestion — six standards, app and web, ready status, counts and deduplication.
- [ ] Tagging — 10 chunks and 10 questions per standard.
- [ ] Question parsing — one checked paper per standard.
- [ ] Retrieval isolation — Physics then Chemistry with correct citations.
- [ ] Multi-standard lessons — correct standard wording for all three.
- [ ] Multi-subject nightly job — both subjects and histories remain separate.
- [ ] Monthly exam — both subjects, all standards, real questions, no repeats and plausible marks.
- [ ] Marking consistency — same answers three times and disagreements flagged.
- [ ] Marking strictness — A/M/E exemplars with schedule quotations.
- [ ] Reviewer — seeded formula and unit errors detected.
- [ ] Maths and diagrams — `/latex`, rendering and reviewed/flagged diagrams.
- [ ] Daily loop — deliberately wrong answers shape the next lesson.
- [ ] Failure handling — stop and restore 9Router without losing work.
- [ ] Prompt override — both configured models produce complete English responses.
- [ ] Day-one test — phone sign-in through tunnel, Physics 91171, upload from
  Android and web, both ready.

## Current blockers and design caveats

- 2026-11-01: The default Compose database and API have been running locally;
  the latest recorded server suite passed 93 tests with six warnings and six
  subtests. This does not establish the end-to-end acceptance criteria.
- Ruff reported 81 errors when run against the Windows-mounted server tree,
  including executable-bit diagnostics from the mount and a real missing
  `json` import in style analysis. The import was fixed and covered by a sample
  test; a clean Ruff run has not been achieved.
- Automated Playwright scripts checked review boxes and approved 18 bank entries
  without an actual human comparing their content, marks and schedule pages to
  the originals. Those approvals are **not evidence of human review**; the bank
  must be reviewed by a person before its questions can be considered verified.
  Staged model outputs also need review; model-generated marks and pairings can
  vary between runs. Do not approve further entries automatically.
- The local paper collection ends in 2024; the requested 2025 papers and
  schedules were not supplied. The tunnel test is deferred. Visual inspection
  of screenshots by the assistant is unavailable in this session.
- Both 9Router models answered small text probes, but exam parsing also received
  intermittent upstream HTTP 503 responses and malformed model replies. Parsing
  and all model-dependent acceptance rows remain unverified end to end.
- Live lesson API probes returned HTTP 201 with completed advisory reviews for
  Mechanics (`momentum`, lesson 1) and Organic chemistry (`alkenes`, lesson 2).
  Their returned source metadata contained only 91171 and 91165 respectively.
  This checks metadata isolation, not whether every generated claim is correctly
  cited or the entire retrieval-isolation acceptance row passes.
- Additional live Physics lesson probes for Waves (`refraction`) and Electricity
  (`electricity`) each returned HTTP 201 with completed advisory reviews and
  source metadata for 91170 and 91173 respectively. Together with the Mechanics
  probe, all three Physics topics produced drafts; wording and citations have not
  been independently checked against the originals.
- A string-presence check of the four persisted lesson drafts found 4/5 source
  IDs in the Waves draft and 5/5 in each other draft. This does not check page
  numbers, citation placement, factual support or whether uncited sources were
  used; it is not a citation-quality pass.
- Android: `assembleDebug` succeeded (35 tasks up-to-date); the APK installed
  and launched on `emulator-5554`. UI Automator confirmed the sign-in screen and
  an error after a deliberately malformed URL was entered by ADB. Screenshot:
  `shots/android-error.png` (not visually inspected). The last 300 logcat entries
  filtered to `AndroidRuntime:E` contained no output. Sign-in and uploads were
  not verified in this run. A separately attached physical device was in recovery
  and was not touched.
- Follow-up Android test: rebuilt and reinstalled the debug APK, signed in via
  emulator ADB to the local API, tapped Physics → Mechanics, and confirmed that
  the resource screen showed Ready after switching to API `display_status`.
  Selected an assistant-written text sample through the Android file picker; the
  topic resources API subsequently reported that sample as extracted/Ready.
  `shots/android-mechanics.png` was captured but not visually inspected. No
  `AndroidRuntime:E` entries appeared in the last 500 logcat lines. The test used
  local HTTP in the debug build, not a phone through the tunnel; the web upload,
  remaining Android features and screenshot inspection are not verified here.
- Android visual refresh: sign-in fields and button use the available width;
  subjects, topics and resources use rounded surfaces, with topics listed before
  the add form. Session tokens are encrypted with Android Keystore and restored
  after restart; app backup is disabled. On emulator, sign-in followed by
  force-stop and restart returned to the subjects screen. Debug build succeeded.
  `shots/android-login-redesign.png` and `shots/android-home-redesign.png` were
  captured but not visually inspected. Release build and tunnel remain untested.
- Lessons is now the first bottom-navigation destination and the default after a
  fresh app start. Emulator UI Automator confirmed the empty topic-selection
  prompt, navigation to Physics → Mechanics, and display of a saved lesson in the
  lesson screen. Lesson body maths remains plain text; the Stitch article layout
  and formula rendering are not yet fully implemented.
- Headless Chromium signed in to `/manage` at 390×844 and 1440×900; the manager
  became visible and no console errors, page errors, failed requests or HTTP
  errors were observed during those two short login probes. This does not cover
  the manager's complete workflows or visual states.
- A live `/review/lesson` call with an assistant-written sample containing both
  an incorrect momentum formula and incorrect SI units returned HTTP 200; the
  configured `education-reviewer` identified both errors against supplied sample
  evidence. This is one seeded-error case, not a guarantee of reviewer accuracy.
- Live diagram generation returned HTTP 201 for a Physics force diagram and a
  Chemistry ethene diagram. Both were stored as `flagged`; the Physics response
  had review text and the Chemistry response did not. Their images and scientific
  correctness were not visually inspected, and `/latex` remains unverified.
- Earlier staging cleanup scripts deleted pending-review rows, including other
  years and topics, rather than only the intended fallback rows. Approved bank
  entries remained, but staging must be inventoried and regenerated as needed;
  do not repeat broad cleanup. The real source files remain private.
- The user identified a local acceptance-data folder; it is inside the workspace
  rather than outside the repository. Keep its contents untracked and private.
- The user will enter the 9Router endpoint and key in the ignored `.env` file.
  The tunnel/domain acceptance test is explicitly deferred by the user.
- 2026-10-31: all four `.env` entries were non-empty. The existing default
  Compose database volume rejected the configured password (`FATAL: password
  authentication failed for user "studyguider"`); it was not modified or
  deleted. A separate fresh `studyguider-verify` project started and its health
  endpoint returned `{"status":"ok"}`. Real `education` and
  `education-reviewer` text requests each timed out after 90 seconds and became
  HTTP 502; no model output or acceptance pass was obtained. The fresh project
  contains the configured database password and is not production data.
- Retry: the gateway returned HTTP 200 `text/event-stream` when `stream` was
  omitted, which the JSON client could not parse. Explicitly requesting
  `stream: false` returned a non-empty response for each of `education` and
  `education-reviewer`. This verifies only small text calls, not the full AI
  acceptance tests or image support.
- `AGENTS.md` is absent; `DESIGN.md` and `writeup.md` were read.
- The existing application is a prototype; its advisory model feedback does not
  establish deterministic marking or official NZQA grades. Low temperature alone
  cannot guarantee identical model outputs, and a model reviewer cannot prove
  factual correctness. Acceptance must be measured, not assumed.

## Round: integrated course flow (2026-11-01)

Changes made in this round, and exactly what was and was not verified.

- **Zip batch upload** (`POST /topics/{id}/resources/batch`, `server/app.py`).
  Accepts several `files` parts or one `.zip`; members are stored as ordinary
  queued resources so the existing extraction worker processes them one at a
  time. Traversal paths are rejected (400), unsupported types are reported in
  `skipped`, and re-uploads are counted in `duplicates` (not `queued`).
  Verified live with curl against the running stack: a zip holding `a.txt`,
  `b.txt` and `skip.exe` returned `queued=2`, `skipped=[skip.exe unsupported
  file type]`; both files then became `extracted`/`Ready` with 1 page each; a
  second identical upload reported `duplicates=2`. Unit tests cover the filename
  sanitiser only (`server/tests/test_batch_upload.py`); the endpoint itself needs
  a database and is not covered by the unit suite. Suite: 96 passed.
  The Android app now uses a multi-select picker and zips several files on the
  device before uploading; the upload notice text is not yet seen on device.
- **Teaching style** (`server/styles.py`). Subject profile (already present) plus
  a new per-topic override (`topic_style_profiles`); `style_for_topic` merges
  them. The style is now injected into lesson, explanation and exam-feedback
  prompts (previously lessons only). Android Settings has an editor with subject
  chips, save and revert. Verified on emulator: the sheet opened from Settings,
  accepted text and the chip changed from `NOT SET` to `SET`; the save request
  itself was not observed reaching the server in that run.
- **Back navigation.** The Android back key now steps back one level
  (PDF → topic → subject → tab root) before leaving the app, and the Resources
  screens keep their visible back control. Verified on emulator by ADB key events.
- **Compact header and Settings sheet.** The tall titled header was replaced by a
  single row (tab title plus scope) with a gear opening a bottom sheet holding
  account, library, courses, teaching style, about and sign out. Verified on
  emulator by UI Automator text dumps.
- **Lessons home.** Lessons now lists the learner's chosen courses with a
  numbered lesson spine (Basics → Next up → Completed) and a floating
  "New lesson" button; topic selection moved to a bottom sheet reachable from
  the empty state, "Add another topic", and Settings → Courses. Courses are
  persisted (`courses` table, `GET/POST /courses`, `DELETE /courses/{id}`).
  Verified live: adding Chemical reactivity and Structure and bonding through the
  sheet created courses; `GET /courses` listed them. Verified on emulator:
  Lessons home shows the Mechanics course, its lesson and the floating button;
  tapping it opens the lesson creator.
- **Basics-to-exam lesson structure.** Lesson generation now reports course
  position in the prompt (assumed knowledge, this lesson, unlocks next) and aims
  at exam wording. Verified with one live call (`momentum and impulse`, HTTP 201,
  advisory review completed, `stage=1`, `course_id=1`); the returned lesson
  opened with a "Course Position" block naming prior knowledge and the next
  topic. One live call does not establish consistent prompt adherence.
- **Lesson formatting.** Raw UUID citations are rewritten to `S1`, `S2`… with a
  numbered source key under each lesson, italic spans now render, nested bullets
  and numbered items are indented, and a paragraph followed by a bullet list no
  longer merges into one line. Verified via the WebView DevTools connection: no
  `xxxxxxxx-xxxx` pattern remained in the rendered lesson text, and measured
  WebView heights matched content heights (no clipping). Screenshots
  `shots/lessons-home.png`, `shots/topic-picker.png`, `shots/lesson-format-1.png`
  and `shots/settings-sheet.png` were captured but **not visually inspected**;
  the assistant cannot view images in this session.
