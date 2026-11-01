# StudyGuider progress

Status key: **not verified** means the requested end-to-end acceptance test has
not passed, even if part of the implementation exists. This inventory is based
on `writeup.md` and the existing prototype, not a claim of completed features.

## Roadmap and features

## Active scope: writeup completion (user exclusions)

- Saved exams now have Delete with an explicit permanent-deletion confirmation.
  Authenticated DELETE /exams/{id} returns 204 (404 if missing); existing database
  cascades remove attempt items/scans/markings/overrides while preserving bank
  questions/resources. Android removes the card only after successful response;
  failures retain it and surface an error. 152 server tests passed, six warnings/
  six subtests; debug build passed; API rebuilt/deployed, health ok; emulator APK
  installed. No actual user exam deleted; live cascade/UI behaviour not tested.

- Exam UI correction: user meant a year dropdown, not an expanded radio list.
  Replaced it with Choose a year / selected year dropdown; entries retain standard
  and question count. Past paper, Collated paper and AI-written practice now share
  one equal-width row; unofficial-rubric notice remains visible for AI mode.
  Debug build passed, APK installed on emulator-5554; visual interaction untested.

- Learning layout follow-up: reminder and AI usage now use the existing full-width
  StudyCard instead of loose text / wrap-content Surface. Reminder toggle sits
  beside its title/time, supporting text uses secondary small typography, and
  usage has separate title/period plus View/Refresh actions. Debug build passed;
  APK installed on emulator-5554. Updated layout not yet visually checked.
  Exam year selection also changed from separate outlined chips to a single
  full-width Available papers list with dividers, year headings, standard/count
  subtitles and accessible single-selection radio rows. Build/install passed;
  runtime selection and visual layout remain unverified.

- 2026-11-02: Added Android Learning AI usage card (manual load/refresh, last
  30 days), showing calls/errors, reported input/output tokens and calls without
  complete token counts. /usage explicitly returns cost=null and explains absent
  gateway-alias billing rates; no invented estimate or claimed budget enforcement.
  Streaming gateway calls now request usage chunks and log tokens/response chars;
  [DONE] marks success, truncation/failure records an error. No historical stream
  backfill possible. 151 server tests passed (six warnings/six subtests), debug
  build passed; deployed API healthy and APK installed on emulator-5554. Live
  endpoint-function SQL check: 436 calls, 101 errors, 2,700,514 input / 826,492
  output reported tokens, 102 calls missing complete counts, cost null. Actual
  gateway stream usage compatibility and Android card interaction untested.
  Dollar cost/budget controls require reliable pricing, and remain outstanding.

- 2026-11-02: Added opt-in daily Android study reminder to Learning, default off,
  around 7 pm device-local time using native inexact alarms (no new dependency,
  network, exact-alarm permission or server change). Requests Android notification
  permission when needed, reports blocked permissions, cancels on disable and
  reschedules after delivery, boot, clock/timezone changes and app replacement.
  Notifications open the app without claiming reviews are due. assembleDebug and
  targeted connectedDebugAndroidTest ReminderTest passed on Pixel_10_Pro emulator
  (one test, Auckland daylight-saving timing). Physical recovery device skipped.
  Two stale lesson instrumentation call sites needed required screen arguments
  to compile the test APK; those tests were not run. Delivery/permission/reboot UI
  behaviour remains unverified. Fixed 7 pm is deliberate; time picker deferred.

- 2026-11-02: Passed lesson diagrams now have an Explain this diagram button,
  opening the existing streaming Explain panel with diagram_id. Server checks
  positive ID, lesson/topic ownership and passed review before any model call.
  Diagram description/SVG structure is supplied as untrusted illustration context
  alongside saved lesson source evidence; prompt explicitly disallows treating
  it as factual evidence or claiming rendered-pixel inspection. Paragraph/global
  Explain clears diagram focus so context does not leak between actions. No new
  dependency or separate chat UI. Checks: 148 server tests passed, six warnings/
  six subtests; assembleDebug passed; API rebuilt/redeployed and /health ok;
  APK installed on emulator-5554. Real gateway diagram explanation, streaming UI
  interaction and visual validation remain untested. Reminders are next.

- 2026-11-02: Exercised real gateway diagram generation with saved mechanics
  lesson 18: authenticated POST returned 201, lesson-filtered listing returned
  200 and contained the generated row, image GET returned 200 with a valid PNG
  signature (50,357 bytes). Independent review rejected incorrect velocity units
  and an ambiguous displacement arrow; status correctly remained flagged.
  Extended the existing three-attempt loop to feed visual-review issues into
  regeneration, not just SVG/render failures. Reviewer outages stop without
  claiming success. Regression check verifies rejected drawing -> correction ->
  independent pass. Full suite: 144 passed, six warnings/six subtests. API rebuilt
  and deployed, health ok. Second live pipeline run rendered a 44,454-byte PNG
  but visual review was unavailable; remained flagged. Cairo emitted
  `Fontconfig error: No writable cache directories`; rendering still returned PNG.
  Both test diagram rows/files removed, temporary HTTP session revoked. No human
  visual validation or successful live correction cycle claimed. Android UI
  interaction remains untested; next task is diagram Explain / reminder work.

- 2026-11-02: Added on-demand reviewed diagrams to non-practice Android lesson
  sections, reusing existing diagram storage/rendering/image endpoints. Generated
  diagrams are linked to the lesson and recovered by description when reopening;
  only passed diagrams are displayed, with an AI-review-not-verification notice.
  Flagged diagrams are withheld with an explicit retry control. Generation and
  independent visual review now receive the lesson's saved sources/standards;
  lesson requests without saved evidence are rejected. Review requires a boolean
  pass and a string issue list; non-empty issues cannot pass. Added lesson_id
  filtering to the existing list endpoint and diagram image accessibility labels.
  Checks: 143 server tests passed (six warnings/six subtests); assembleDebug passed
  with existing deprecated WebView-setting warnings. API rebuilt/redeployed,
  /health ok; APK installed on emulator-5554. Real gateway diagram generation,
  visual correctness and UI interaction remain untested. Automatic diagram
  selection/generation during overnight lessons and diagram Explain remain open.

- 2026-11-02: Added dependency-free formula structural checks to lesson review:
  unclosed/mismatched dollar delimiters, empty formulas, unbalanced argument
  braces and unsupported backslash maths delimiters trigger the existing bounded
  rewrite loop even when the model reviewer approves. Persistent faults remain
  flagged. Escaped braces/dollars and chemistry commands are covered by tests.
  This is NOT full KaTeX compilation, dimensional checking or proof of formula
  correctness; those remain outstanding. Applies to newly reviewed lessons only,
  not a migration of existing saved drafts. 138 server tests passed, six warnings/
  six subtests; API rebuilt/redeployed, /health ok. No live generation attempted.

- 2026-11-02: Android Explain dialog now consumes /explain?stream=1 and updates
  the displayed answer per chunk using the existing HttpURLConnection client.
  Interrupted replies retain partial text with a retry warning; only an explicit
  completion event counts as success. The gateway reader requires [DONE], and
  the explain endpoint emits an error event on upstream HTTP/connection failures.
  Streaming save_to_notes is explicitly rejected rather than silently ignored.
  Practice-answer marking keeps its existing non-streaming path. No new dependency.
  Checks: 125 server tests passed, six warnings/six subtests; assembleDebug passed;
  API rebuilt/redeployed and /health returned ok; APK installed on emulator-5554.
  Actual gateway-to-Android streaming interaction/visual behaviour not yet tested.
  Full lesson generation streaming, explanation chat history and streaming note
  saving remain open. Previous exam-quotation MathText fix is included in this APK.

- Fixed a live user-reported bug: exam marking failed with 502 "Model returned
  invalid marking JSON" on AS 91170 2026 Exam 7 Q1(a). Root cause was the JSON
  validator being too brittle: it required the whole reply to be pure JSON (no
  tolerance for a stray sentence of prose), used strict type validation (no
  tolerance for e.g. marks_awarded as 5.0), and compared evidence quotes against
  the schedule byte-for-byte (no tolerance for typographic quote/dash variants
  the model may retype). Added _extract_json_object (first balanced {...} span),
  switched to strict=False validation, and normalise quotes/dashes before the
  exact-quotation check. Also added one bounded retry specifically on a 502 from
  _validate (both text marking and the new vision_mark() helper covering first
  and second image review), re-prompting with an explicit JSON-only instruction
  before giving up — separate from model_reply_reliable's existing retry for
  transient gateway failures. 119 server tests pass (renamed test plus one new
  recovery-path test). Rebuilt and redeployed the API; live and healthy.

- That fix alone did not resolve the user's live failure; added temporary debug
  logging and reproduced it directly against exam 7/answer 93. Root cause was
  different from the formatting robustness just added: the Feedback schema
  required `evidence` to have at least one item always, but a correctly-marked
  zero-mark answer has nothing positive to quote as "awarded for this" (the
  missed schedule line belongs in `missing`). Every zero-mark question was
  therefore guaranteed to fail validation. Changed `evidence` to default to an
  empty list, and added an explicit check that marks_awarded > 0 requires at
  least one evidence quote (so marks still can't be awarded without citing the
  schedule). Verified live: the real failing request now returns 200 with
  marks_awarded 0 and populated `missing`. Removed the temporary debug logging.
  121 server tests pass (2 new: zero-mark-no-evidence accepted, awarded-marks-
  without-evidence still rejected). Rebuilt and redeployed; confirmed live.

- Deployed API build with scan-revision locking, NCEA scale detection and cut-score
  extraction. Ran /admin/backfill-cut-scores live against the real database: 44 of
  60 standard/year schedules extracted boundaries, 16 not_found (pre-2015 schedules
  use a different cut-score layout the parser correctly refuses to guess at rather
  than fabricate numbers). Verified /learner/summary against live data: returns
  per-topic correct/wrong counts, repeated mistake concepts, strength concepts,
  lesson activity and today's review count, all from existing review_answers/
  lesson_answers rows with no AI narration layer yet.

- Added SSE token streaming (model_reply_stream in app.py, reading the gateway's
  stream=true response chunk by chunk) and wired it into /lessons/{id}/explain via
  ?stream=1. Added /lessons/{id}/explain/paragraph so a learner can ask about one
  paragraph or equation instead of the whole lesson; Android LessonScreen now shows
  a small "?" button after every plain-text block that pre-fills the existing
  explain dialog with that paragraph as context. Android does not yet consume the
  SSE stream (still issues a normal blocking POST); only the server side streams.
  Added /topics/{id}/import-papers (manual re-run) and /admin/backfill-cut-scores
  as callable endpoints — they previously only ran automatically or not at all.
  114→118 server tests (4 new, explain/paragraph coverage). Android build and
  install passed, no fatal exceptions in logcat after launch. Android SSE
  consumption, cost/budget limits and reminders remain open.

- Cut-score extraction: inspected live 91164/2024, 91171/2017, 91170/2023 schedules;
  four contiguous ranges are printed under Cut Scores (different A/M/E cutoffs).
  Parser now accepts only complete ordered contiguous ranges with all labels and
  stores source page/quote during new paper import. Existing completed import runs
  are not automatically backfilled. Image prompt now specifies N0–E8 descriptor
  selection where recognised; Android fetches schedule-grade separately instead
  of displaying aggregate percentage grades. Full suite 116 passed, six warnings/
  subtests; R8 benchmark build passed. Not deployed/installed or live-grade-tested;
  source-provenance labelling still says human-entered for automatic rules and must
  be corrected. Structured schedule evidence isn't equivalent to human verification.

- Schedule scoring: recognised complete N1/N2/A3/A4/M5/M6/E7/E8 descriptor sets
  now use the eight-point whole-question scale, not percentage thresholds; typed
  marker explicitly instructed to select schedule descriptors. Overall marks
  endpoint no longer invents aggregate A/M/E from percentages; matching schedule
  cut-score endpoint remains separate. Totals use returned marking denominators.
  Suite 115 passed, six warnings/six subtests, including A3/M5/E7 boundary checks.
  Not deployed/live-exemplar-tested. Image prompt scale instructions, automatic
  cut-score extraction and app integration still incomplete; generic fallback for
  unrecognised question scales remains, not verified official grading.

- Built dedicated benchmark variant with R8 optimise/minification/resource
  shrinking, non-debuggable, debug-key signed to update existing emulator install.
  Local-only manifest permits HTTP; production manifest unchanged. Initial manifest
  merge failed until explicit tools:replace added. assembleBenchmark succeeded,
  including minifyBenchmarkWithR8. Installed emulator-5554 and launch status ok
  (WaitTime 355ms, not a controlled benchmark). APK 1,721,149 bytes vs current debug
  10,487,766 bytes. Last 500 logcat lines had no searched fatal/class/bridge errors.
  Full UI and maths bridge regression under R8 not yet verified. No speedup claim.

- Scan confirmation race: answer saves lock the exam item and require the scan
  revision actually reviewed; uploads use the same lock before replacing images.
  Recognition returns revision; Android gallery/drawing and web marking propagate
  it. Stale scan saves return 409 before changing the answer. Full suite 114
  passed, six warnings/six subtests, with stale-scan regression; Android build
  passed. Not deployed/live-concurrency-tested. Original scan version history,
  per-question whole-exam atomic upload and schedule-specific scoring remain open.

- Scan correctness: replacing uploaded pages increments scan revision. Totals/
  schedule grade require current confirmed scan revision plus exact saved answer;
  pending replacements suppress old grades. Uncertain/low-confidence image marks
  now get independent vision second review, cached separately. Full suite 114
  passed, six warnings/six subtests; image-review regression included. Not deployed
  or validated on real drawings. Scan confirmation itself still needs revision
  matching to prevent concurrent upload/save race; schedule scoring still open.

- Exam correctness batch: marking rows capture exact answer text; totals and
  schedule-grade queries only select marks matching the current saved answer,
  retaining older mark history. Legacy marks without snapshots require re-marking.
  Typed low-confidence (<0.7) or uncertain marks automatically request the second
  reviewer; image marking and schedule-boundary borderline rules not yet covered.
  Full suite 113 passed, six warnings/six subtests; query regression and automatic
  second-marker test added. Not deployed/live-model-tested. Generic percentage
  grading and image/scan version correctness still open; do not claim NCEA grading
  complete. Saving UI/network acceptance still open despite server conflict check.

- Coding-output contamination: added deterministic coding-fence/ponytail/skipped
  checks that override even a reviewer pass and force bounded rewrites or flagged
  status. History/read endpoints reject contaminated content. Deployed locally;
  live scan flagged lessons 11,15,16 without deleting lessons/answers. Full suite
  111 passed, six warnings/six subtests, including false reviewer-pass regression.
  New live generation after this guard not verified; upstream coding prompt remains
  a risk and pattern checks cannot prove absence of all contamination.

- Saving deployment follow-up: web marking now explicitly loads saved answers and
  revisions before editing/submitting; changing IDs invalidates the loaded revision.
  Android retains exam draft revisions through activity restoration instead of
  rebasing dirty drafts on a fresh server revision. API rebuilt/restarted; APK
  built/installed. Live HTTP/Postgres lesson-answer check: initial PUT 200, revised
  PUT 200, stale-client PUT 409; assistant-written temporary answer/session removed
  afterwards. UI/network-failure and exam two-client tests still outstanding.
  Startup logs show successful startup/health; unrelated GET /v1/models 404s are
  visible, caller unknown. Automated course schedules/reviewer loop are now in the
  deployed API but no complete live teaching/review cycle validated yet.

- Exam saving now uses answer_revision with conditional updates and HTTP 409 for
  stale writes. Android sends/updates revisions on Save and Save & mark. Synthetic
  workflow verifies stale rejection and updated answer retrieval. Recovered lesson
  conflicts now have View recovered draft and explicit Restore draft controls.
  Full suite 110 passed (six warnings/six subtests); Android build passed. Not
  deployed: web marking form still needs revision-aware loading before migration
  is rolled out, and emulator/two-client/network checks remain outstanding.

- Current saving batch: lesson pending-save state now reaches shell navigation,
  blocking tab changes, with reader Back guarded. Reading position has server
  GET/PUT endpoints and revision checks; Android loads server position and waits
  for position saves before advancing/exiting. Retry and reload-server-position
  controls handle sync failures/conflicts. Synthetic regression covers initial
  position, update, restore and stale-write rejection. Full suite 110 passed,
  six warnings/six subtests; Android build passed. Not deployed or emulator/network
  failure tested yet. Exam revision checks and conflict-recovery UI remain open.

- Saving follow-up: lesson answer writes now require revision matching (409 on
  stale/create-over-existing writes). Android sends revisions, blocks reader
  Previous/Next/Exit/Finish while answer loading/saving fails or remains pending,
  preserves recovery revision, and offers server reload retaining a conflict copy.
  Build passed; full server suite 110 passed (six warnings/six subtests), including
  stale-write regression. Not deployed or runtime verified. Tab switching still
  bypasses this reader guard; encrypted recovery, synced reading position, exam
  answer revisioning and background outbox remain open. Conflict copy currently
  lacks a recovery-view UI. Do not claim complete lossless saving.

Do not implement automatic monthly exams, Google Drive import, production access,
or backups. Website parity deferred. Priorities: automatic learning loop, exam
correctness, durable answers. Remaining writeup gaps tracked above remain open;
do not describe this batch as completing the whole request.

- Current batch: active courses get 2am Auckland schedules automatically; inactive
  courses excluded. Scheduler prepares reviews without waiting for app open and
  continues lessons if review service fails. Added structured reviewer verdicts,
  up to two full rewrites/rechecks, preserving unavailable/flagged drafts and
  excluding them from normal feed. Existing legacy completed reviews remain visible.
- Android answer drafts now persist locally before debounced server saves and
  restore unsynced drafts on reopening. This is recovery, not background upload or
  conflict-safe cross-device sync. Local preference drafts are not encrypted yet.
- Server suite 110 passed (six warnings/six subtests) before final scheduler hook;
  Android build passed. New batch not deployed: autonomous model calls must be
  checked before enabling all enrolled daily schedules. Exam grading, retrieval,
  streaming, contextual explanations and other accepted gaps remain unfinished.

- Backfilled all six current-standard topics live. Bank now has 76 distinct
  standard/year pairs and 235 non-AI question groups. All 2012–2024 years imported
  for Waves, Electricity, Organic and Reactivity. Mechanics 2013 and Structure/
  Bonding 2018 remain missing a schedule heading. Some early Physics papers have
  four genuine whole questions; inspected source headings and corrected rigid
  three-question rule to ordered 3–5. Reactivity 2015 heading TWO (a)(i) now parsed.
  2004 legacy papers lack matching schedules; other legacy standards aren't linked
  as current standards and were not silently relabelled. API rebuilt/restarted.

- Removed standard allowlist at user request; exact filename standard/year pairing
  and structural/schedule-heading warnings remain. Existing import runs need
  backfill for newly eligible standards; no claim all years now appear.
- Browser sessions now use a persistent 30-day HttpOnly SameSite=Strict cookie,
  Secure on HTTPS, retaining Android bearer support. Cookie-auth mutations reject
  cross-site origins; logout revokes server session and clears cookie. Website
  restores via /session without web-storage tokens. Deployed locally; Playwright
  passed login/reload restoration, cookie flags, cross-site logout rejection and
  logout/reload. Cookie regression passed after matching cookie domain to test
  host. HTTPS/tunnel cookie flags not live-tested.

- Removed stale manual-approval/human-review warnings and pending-year request
  from Android paper selector; automatic imports remain machine-labelled in data.
  Build/install passed. This wording removal does not implement an AI paper-review
  pass or unlock ambiguous/unpaired documents; those remain importer limitations.

- Added persistent in-exam Type answers / Write on paper switch. Handwritten
  papers intentionally hide digital boxes until recognition, but learners can now
  change mode without recreating the paper or clearing answers. Build/install and
  local API rebuild/restart passed; actual switch interaction not yet verified.
- Vision output contamination guard rejects coding-advice prose and No answer
  found before scan replacement. Vision system prompt now explicitly requires the
  document task, not coding advice; marking accepts fenced JSON but still validates
  schema and exact schedule evidence. Regression marking tests exited 0; real
  handwritten recognition remains unverified.

- Digital diagram answers: instructions matching draw/sketch/plot/label/Lewis
  structure expose Insert image and Draw diagram. Native white-canvas pen/clear
  produces PNG and uploads through existing scan recognition; original image is
  retained for image-aware marking. Text and per-part answers preserved, diagram
  recognition editable before save/mark. One image per whole question, replacing
  previous image; local canvas draft not persistent. Build/install passed; actual
  strokes/gallery/vision marking not runtime-tested. Website drawing parity absent.

- Deployed structured parser v2/API and installed reader; backfill returned 12
  imported, eight waiting, one needs attention. Emulator selected Chemistry /
  Structure & Bonding / 2024, started exam 5 and displayed Question 1 of 3 with
  inline source table. `shots/exam-structured.png` visually inspected: duplicate
  flattened table text remained above crop. Parser v3 now excludes text geometrically
  contained in diagram/table crops from display parts (original extraction retained).
  Suppressed duplicate question headings and meaningless zero-total grade label.
  Suite 106 passed, six warnings/subtests. V3 and latest reader refinement not
  deployed; exam 5 is intentionally immutable and retains v2 data. End-to-end
  subpart save/restore, correct crop association and handwritten flow unverified.

- Structured paper follow-up: parser parts now carry text and page-coordinate
  diagram anchors; Android consumes these parts instead of re-splitting flattened
  wording and only gives answer boxes to leaf parts. Diagram anchoring uses
  physical preceding text, not semantic interpretation; still needs visual
  validation. Import version 2 refreshes parts only for machine-imported questions
  unused in exams, preserving saved exam content. Build passed, suite 106 passed,
  six warnings/subtests. Latest structured reader/import version not deployed.

- Connected PDF-layout parser to post-extraction processing and added explicit
  backfill endpoint. Live topic 4 import: 12 standard/year pairs imported, eight
  waiting (legacy/unpaired), one needs attention (2018 missing Q2 schedule heading).
  Machine imports have verified_at=NULL, not a fake human approval. Existing 2017
  rows preserved; no existing wording overwritten. Added nullable verified_at
  migration after live constraint failure; applied it to running DB and retried
  successfully. Suite 106 passed, six warnings/subtests. Latest source changes
  after deployed image still require rebuild. OCR/layout text still includes
  artefacts; figures are candidate regions, not semantically validated diagrams.

- Inspected supplied 91164 Past Papers locally, without copying source material
  into repo. Added paper_parser.py: filename standard/year pairing, PDF physical
  lines/coordinates, whole-question continuation grouping, nested part labels,
  schedule-section pairing and geometric diagram regions. JSON exports went to
  private OpenCode temp storage. 2012–2024 found three groups except image-only
  2021 initially; --ocr recognised all three in 2021 (parts counts 4/6/8). 2018
  schedule lacks a clear TWO heading in extracted text and stays flagged; legacy
  90308 formats also flagged, not assumed equivalent to 91164. Standalone parser
  not yet wired into background imports. It does not guarantee semantic diagram
  association or exact table reading. Suite 105 passed, six warnings/subtests;
  synthetic PDFs test continuation grouping and schedule pairing. No real PDF
  content added to tests/repo. Website parity and automatic import integration
  still in progress; machine-bank import must retain non-human-verified labels.

- Web manager reorganised into Library/Lessons/Reviews/Exams/Question bank/
  Learning/Tools workspaces instead of one long wall of forms. Shared subject/
  topic scope stays available; creation forms collapse. App-wide teaching profile
  endpoint replaces stale web subject profile. Added dark palette and mobile
  overflow fixes. Local API rebuilt/restarted; Playwright signed in and navigated
  at 390x844 and 1440x900: no page/network errors, no document horizontal overflow.
  Screenshots `shots/web-library-390.png`, `shots/web-library-1440.png` and dark
  Learning variants captured; mobile Library visually inspected. Upload/approval/
  marking write workflows not exercised; no question approved during this check.

- Paper availability diagnosed from live DB: bank has 18 questions from 2017;
  2012–2016 and 2018–2024 are parsed pending_review, not lost extraction. Resources
  include 127 extracted exam papers and 145 extracted schedules. No approvals
  changed. Added processing-status endpoint and pending-year notice in selector.
- Digital reader has labelled per-subpart inputs saved in the existing answer
  field as a parts map, retaining legacy whole-question text. Geometric PDF image/
  vector-region extraction endpoints feed inline crops; association and labels
  remain unverified, no semantic diagram-extraction guarantee. OCR wording is not
  rewritten; flattened artefacts still need source-compared correction. Server
  suite 103 passed; API rebuilt/restarted. Android build passed before pending-year
  notice; final APK not built/installed. Whole-exam upload remains untested live.

- Exam flow revision: new exams persist Digital/Handwritten choice; reader shows
  one top-level question group at a time and scrolls to top on page changes.
  Handwritten flow has one final upload step (up to ten gallery images), then
  per-question recognition review/save/mark. Server currently repeats recognition
  per question, storing the combined image; partial failures are not atomic.
  Saved exams now fetch subject/level/topic titles. Build passed and server suite
  103 passed before final text-part renderer. Not yet installed/deployed this round.
- Printed explicit (a)/(b)/(i)/(ii) markers split into readable part blocks under
  the same top-level question; sample hierarchy self-check exited 0. Units in
  parentheses remain intact. Full page images are optional figure references,
  NOT inline extracted diagrams. OCR artefacts remain; diagram cropping/placement,
  per-part digital inputs/marks and robust structured paper editing are unfinished.

- Past-paper question display now uses original page images (plus registered
  figure pages) instead of flattened OCR paragraphs; source button remains for
  full-size reading. This does not discover missing continuation pages. AI items
  keep rendered question text and no null resource links. Android paper-answer
  upload uses the multi-select gallery picker (up to six images). Server accepts
  repeated files, bounded by total size and image dimensions, and preserves their
  order before recognition. API rebuilt/restarted; build/install passed and suite
  103 passed, six warnings/subtests. Gallery multi-selection and original-page
  rendering have not been runtime-verified on this build.

- Exam anytime deployment: local API rebuilt/restarted; emulator APK installed.
  Topic selector, original registered paper/year selector, mixed-bank start and
  AI-practice start implemented. Live Mechanics mixed exam id=1 has three items;
  live education generation created AI-practice id=2 with three validated items.
  Emulator confirmed Mechanics selection and 2017/91171 paper choice. Screenshot
  `shots/exam-menu.png` visually inspected. Printable endpoint returned a text-only
  PDF; no embedded original figures or proper typeset LaTeX, so not a faithful
  printable NCEA paper. Scan upload accepts PNG/JPEG or up to six PDF pages joined
  for vision; real handwriting/diagram accuracy not verified. Single upload per
  question, no multi-photo picker. Grade-rule API stores human-reviewed exact
  schedule quotes and ordered cut scores; separate schedule-grade endpoint refuses
  incomplete/mixed/AI papers. UI still uses generic practice totals; official
  per-question NCEA criterion scoring and grade-rule entry UI remain outstanding.
  Bank human review remains outstanding; original selection is registered items,
  not a verified complete paper. Mixed selection does not guarantee multiple years
  or A/M/E balance. Full suite 103 passed, six warnings/six subtests; Android build
  passed before final removal of stale Monthly exam subtitle. That wording change
  not built/installed. No tunnel/physical-device deployment claimed.

- Exam paper-answer foundation (partial): per-question PNG/JPEG upload, bounded
  decoding, vision transcription, persisted original image, explicit save/confirm
  before image-aware schedule marking. Image marking checks exact schedule quotes
  with the existing validator and caches by image/transcription payload. Android
  has an image picker and editable transcription. Single image per question;
  another scan replaces it. No PDF/multipage/camera/print flow yet. Build passed;
  server suite 101 passed, six warnings/subtests, including invalid image rejection.
  Not deployed or live-image-tested in this round. AI-paper generation, original
  year selection, reliable schedule-specific A/M/E aggregation and new exam home
  are still unimplemented. Existing generic grade thresholds are NOT official
  standard/year cut scores. Current bank still lacks genuine human review.

- New lesson practice and both review-generation paths now request source-backed
  Relevant formulae within each applicable question, with symbol/unit definitions
  but no substituted values or solutions. Conceptual questions omit unnecessary
  formulae. Prompt assertions pass; full suite 100 passed with six warnings and
  six subtests. API rebuilt/restarted. Existing saved questions unchanged; live
  generated formula support has not been checked.

- Rejected citation-only descriptions in definition MCQs; regression for meth-/
  eth-/prop- prefix list passes. Long KaTeX can wrap at its native relation/operator
  breakpoints; Chromium check of the user's force-equation shape at 330px reports
  scrollWidth=330 and height=46.4375 (two lines). Indivisible maths still has
  horizontal overflow fallback. Android build/install passed, formatting main
  exited 0. Lesson prompt now requests 3–5 individually headed Your Turn tasks;
  this is not enforced by output validation and hasn't been live-generated.

- Lesson answers: authenticated GET/PUT endpoints now store question, latest
  answer and feedback per lesson/question key. Android restores and debounces
  saves, shows server-save failures; web saved-lesson detail reads the same data.
  Future lesson and automatic review prompts include saved learner answers.
  Server suite 100 passed (six warnings/subtests); Android build/install and API
  rebuild/restart passed. Cross-device restore and web UI not runtime verified.
  Known ceiling: navigation during the 600ms debounce can cancel a pending save;
  concurrent devices are last-write-wins. No claim of lossless sync is made.
- Removed formula-blank extraction altogether. Worked examples keep their worked
  solutions but no duplicate quick check. Separate Answers pages are filtered
  from the reader; headings render maths. Prompt now separates Worked Example
  from different, unsolved Your Turn tasks. AI marking still requires Check my
  answer; advancing pages does not automatically mark. Existing inline solutions
  inside old Your Turn content are not yet hidden. New generation not live-tested.

- Tutor feedback: practice-panel marking now includes the section question and
  context, not just the learner's answer. Prompt requests proportionate feedback
  (up to three short sentences for conceptual answers), no completeness preamble
  or irrelevant units, and working only for calculations. Both marking displays
  render Markdown blocks and shorten citations. Reader header padding reduced.
  Build/install and API rebuild/restart passed; explanation tests exited 0.
  Live feedback brevity and revised header visual appearance not yet verified.

- Removed automatic paraphrase fallback that turned prerequisites and learning
  goals into meaningless questions. Intro/goal/course-position/summary sections
  no longer receive synthetic quick checks. Regression samples for prerequisites
  and learning goals passed in FormattingCheck (exit 0); Android build/install
  passed. Exact saved organic-chemistry pages have not been runtime checked.

- Manager declutter: one grouped list instead of separate tall cards, row tap
  opens the lesson, overflow menu contains Delete, redundant topic/title removed,
  back/date share a line. Build/install passed; screenshot
  `shots/lesson-manager-compact.png` visually inspected and overflow tapped to
  confirm Delete lesson appears. No lesson deleted during this check.

- Lesson manager now opens a newest-first day menu using Pacific/Auckland
  creation dates, with lesson/completed counts. Selecting a day shows that day's
  open/delete controls; Back returns to all days and resets scroll. Main Lessons
  no longer displays history. Debug build and install passed; emulator confirmed
  the day menu (2026-11-01, seven lessons/one completed) and tapped into its list.
  Screenshot `shots/lesson-manager-day.png` captured.

- Incomplete question fix: practice extraction no longer splits sentences at
  decimal points, citation page numbers or equation-list numbers. Context-free
  equation blanks are skipped; regression check covers a numbered equation list.
  Tightened lesson prompts for self-contained problems and worked answers, and
  feedback prompts to refuse marking incomplete questions. Feedback now shortens
  citations too. These prompts do not constitute validated output completeness.
- Learning has Lesson manager (open/delete with confirmation) and Lesson history
  (server-completed lessons). Existing automatic review loading consumes completed
  lessons across topics. Build passed, formatting main exited 0, server 100 passed
  with six warnings/subtests. Emulator opened manager; visual inspection found
  uneven card widths and inherited scroll, fixed by full-width cards and resetting
  scroll per subpage. Final layout fix built but not reinstalled. No real lesson
  deleted or falsely marked complete for verification. API rebuilt/restarted.

- App-wide teaching method replaces subject selection in the Android editor.
  GET/PUT /style-profile persists one global profile; /style-profile/analyse
  samples extracted slides across subjects. Saved global content takes precedence
  over legacy subject/topic profiles, including explicitly clearing it. Existing
  profiles are preserved, not silently combined. Upload filing still asks for a
  topic solely because resources belong to topics; it does not scope the method.
  Android build passed, APK installed, API rebuilt/restarted; server suite 100
  passed, six warnings and six subtests. New tests cover global save/read and
  precedence across topics. Actual cross-subject slide analysis remains unverified.

- Teacher-method editor now offers Upload teacher slides directly. It uses the
  existing multi-file/zip upload endpoint with category=slides, waits for those
  accepted resources to extract, then runs subject teaching-method analysis into
  the editable draft. Duplicate non-slide resources are not recategorised. Build
  passed and APK installed; real emulator taps reached the topic filing dialog
  and Android Downloads picker. Actual slide selection/upload/analysis has not
  been verified; no real teacher slide was available in the emulator picker.

- Learning now has its own bottom-navigation destination: enrolled topics with
  Edit topics and the existing teacher-method editor. Removed those destinations
  from Settings, which retains app/account pages. Debug build passed; installed
  and opened Learning on emulator. `shots/learning-tab.png` was pulled and visually
  inspected: topics, edit action, method card and all five nav labels are visible.
  Subsequent teaching-card wording refinement has not been rebuilt yet.

- Automatic reviews: opening the due-review endpoint creates one persisted
  question set for each completed lesson across all topics, then existing spaced
  repetition reschedules the questions. Locks and the generated timestamp prevent
  duplicate committed sets; invalid model output rolls back. This is on-demand,
  not a background daily job. Regression test covers repeat loads; suite 98
  passed with six warnings and six subtests. Live database had zero completed
  lessons, so no genuine completion was fabricated to claim live model coverage.
- Settings is now a full-screen dialog with Account, Courses, Teaching method,
  Appearance/library and About subpages. Emulator confirmed root and Teaching
  method navigation; screenshot `shots/settings-page.png` pulled using ADB.
  Removed duplicate status-bar padding in reader header. Android build passed;
  final home-label wording change has not been rebuilt yet.

- Follow-up verification: full server suite 97 passed, six warnings and six
  subtests passed. FormattingCheck main compiled and ran with exit 0, covering
  Markdown, formula handling, multiple-choice definitions and typed explanations.
  Android build succeeded. The teacher-method action now allows a longer model
  timeout and Settings scrolls to reach the editor. Live Physics slide analysis
  returned 422: "Upload and extract slides for this subject first"; actual
  teacher-method output is therefore not verified. No existing resources were
  recategorised or fabricated for this check. Completed lessons persist on the
  server; completion endpoint success/repeat/missing cases have fixture coverage.
  The second height bug was a WebView callback holding the previous text's state;
  keying the view by text addresses page transitions, but every page has not been
  runtime-checked. Compact reader header and multiple choice require further
  emulator interaction; no visual acceptance claim is made.

- Text-height root cause found: `KaTeXBridge.onHeight` recursively called itself
  instead of its callback. After renaming the callback, emulator DevTools measured
  the worked-example viewport and content both at 93 CSS px (previously 246 and
  93); no bridge recursion appeared in fresh logcat. Screenshot
  `shots/lesson-height-fixed.png` captured, not visually inspected. Completion
  now persists server-side and feeds completed lesson titles into manual lesson
  and review generation; automatic daily review creation remains unverified.

- Lesson reader update: one section at a time, locally saved section index,
  exit and finish controls, fixed progress header and an Explain dialog using
  the existing explanation endpoint. Android debug build succeeded; emulator
  UI Automator confirmed the reader and Explain dialog open. Completion is
  device-local and is not connected to the daily feed; answer drafts are not
  persisted. Explain submission and finish flow were not exercised.

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
