# StudyGuider progress

Status key: **not verified** means the requested end-to-end acceptance test has
not passed, even if part of the implementation exists. This inventory is based
on `writeup.md` and the existing prototype, not a claim of completed features.

## Roadmap and features

## Active scope: writeup completion (user exclusions)

- User clarified wrapping, not shrinking: maths outer HTML now allows breaks between
  intact KaTeX base groups; individual text/subscript/fraction internals keep nowrap.
  Explicit quad/qquad and space-before-Delta-H clauses render as independent inline
  groups with wrap opportunities, preserving reaction + enthalpy order. Removed
  auto-shrink; oversized indivisible groups still have scroll fallback/hint.
  Overflow measurement uses scroll width and refits after width/font/layout settles.
  Debug/test APK builds passed; normal install Success. No connected tests; actual
  screenshot layout unverified, no semantic rewriting of stored lesson text.

- Long-equation discoverability: rendered formulas wider than reader width become
  explicit scroll blocks, shrink at most 20% and display swipe hint only when still
  overflowing; no symbol line wrapping. Refit after font load/resize, report height.
  Debug build passed (existing WebView warnings), normal emulator install Success;
  updated source-level check not connected-run. Exact equation/hint behaviour
  visually unverified; long expressions deliberately scroll rather than become tiny.

- Corrected regression from maths wrapping change: inherited overflow-wrap:anywhere
  and whitespace overrides broke chemistry into vertical symbols. KaTeX base/text/
  HTML now retain nowrap and normal word-breaking; prose-only text conversion kept.
  Long equations remain horizontally scrollable rather than corrupting geometry.
  Debug/test APK builds passed, existing WebView deprecation warnings; normal
  emulator install Success. No connected tests run; screenshot layout pending user.

- Reader maths-text wrapping follow-up: KaTeX text spans now permit wrapping;
  prose-only \text{...} formulas render as normal text rather than unbreakable
  maths. Mixed/long mathematical expressions retain existing overflow behaviour;
  no semantic formula rewriting or stored-content changes. Debug/test APK builds
  passed, two existing WebView setting deprecation warnings; static renderer check
  compiled only, not connected-run. Normal emulator APK install Success. Exact
  screenshot sentence wrapping remains visually unverified.

- Reader heading fix: model-generated ####–###### headings were rendered as prose
  inside one long section because lessonChunks recognised only levels 1–3. Now
  all six ATX heading levels create section boundaries; closing heading hashes
  stripped. Existing saved content unchanged. Added deterministic chunk regression;
  debug/test APK builds passed, normal emulator install Success. No connected
  tests run; runtime section/pagination appearance requires user verification.

- User-supplied icon/wordmark moved from docs to assets/branding (originals intact).
  Generated web favicon/touch icon/cropped wordmark and Android launcher density
  PNGs. Applied website/manager header branding, favicon and README banner; Android
  manifest uses launcher/roundIcon. GitHub social-preview setting not changed.
  207 server tests passed, six warnings/six subtests; debug build passed; API
  rebuilt/deployed, normal emulator install Success. Visual/icon mask appearance
  unverified, no connected tests or data mutations.

- User resumed website study port: new full-width responsive site at / with cookie
  login, Lessons/Review/Exams navigation and Library/settings link to /manage.
  Parallel modules provide lesson feed/section reader/revision saves/follow-up/
  notes/completion; due review/confidence/marking; topic/year original/mixed/AI exam
  creation, saved exams/delete, typed part answers/revision saves/mark feedback and
  schedule excerpts. Bundled KaTeX/mhchem served locally, safe DOM text rendering.
  Navigation guards unsaved study drafts/in-flight review/exam requests; lesson
  module cleanup integrated. 207 tests passed, six warnings/six subtests; JS syntax
  checks passed; API rebuilt/deployed, / and web-lessons.js HTTP200. Browser full
  workflows/visual design unverified. Web exam scan uploads/drawing/timer/aggregate
  grade still missing; full Android parity NOT claimed. No Android/device tests.

- Added Topics you're learning to web Global settings, grouped by subject level/name.
  Checkboxes use same /courses active-course records as Android, saving immediately;
  failed changes restore checkbox and expose error. No new backend/no deleted
  study history. Node route/syntax/image-auth checks passed; API rebuilt/deployed.
  Browser toggle/synchronisation runtime check pending, no user enrolments changed.

- Redesigned Lessons/Reviews/Exams/Standards web sections without changing form
  endpoints: saved lessons first with compact name/date/review-badge rows, refresh
  in header, source/reviewer details collapsed. Schedule/history collapsed below;
  compact responsive form columns. Reviews use short focus/generate controls and
  collapsed evidence. Exams separate collated creation, manual selection and marking
  tools; no automatic scheduling added. Linked standards first, add/update editor
  collapsed. Essential AI/source advisories retained. Node route/syntax/image-auth
  checks passed; API rebuilt/deployed. No DOM/browser interaction test available;
  layout and moved-form workflows require verification. No data mutations/device tests.

- Restored topic-wide Upload at Resources root; shared upload panel stays alive
  across explorer rerenders and opens at current topic without choosing category.
  Distinct view icons for diagrams/classifying/notes/lessons/reviews/standards and
  exam attempts; actual subject/topic/resource collections keep folder icon.
  Node route/syntax/image-auth checks passed; API rebuilt/deployed. Browser
  interaction remains unverified, no file mutations or Android/device activity.

- Removed duplicate topic Settings/Tools diagram screen. Diagrams canonical location
  Resources/Diagrams; old tools bookmarks redirect there. Global settings sidebar
  page holds app-wide teaching method and usage without subject selection; topic
  NZQA standards separate. Gallery selection/create controls aligned. Generic exact
  wave requests now use deterministic SVG geometry (crest-to-crest wavelength,
  equilibrium-to-crest amplitude), still independently reviewed; specific scenarios
  continue model generation. No stored images overwritten/auto-approved. 206 tests
  passed, six warnings/six subtests; route/syntax passed; API rebuilt/deployed.
  Browser navigation/visual results and new live wave review unverified.

- Topic Resources now has Diagrams gallery folder, matching top-right New diagram
  action, hidden creation form, thumbnails, selection/select-all, confirmed single/
  multi-delete and readable collapsible review issues. Authenticated DELETE locks
  diagram row, restricts stored path to uploads/diagrams, removes image then row;
  file failure retains row for retry. No actual user diagram deleted. Generation
  requests fewer/shorter labels, right-edge anchors and exact wave relationships;
  existing defective images not regenerated or approved. 205 tests passed, six
  warnings/six subtests; manager route/syntax check passed; API rebuilt/deployed.
  Browser gallery/deletion workflow and generated scientific quality unverified.

- Reported diagram defects: pre-render SVG text validation now rejects raw dollar/
  common TeX labels; generator explicitly uses plain/SVG labels, focused concept,
  1000x750 viewBox, readable text and outer padding. Reviewer asks to reject clipping,
  overlaps and incorrect graph relationships. Web diagram list flex layout keeps
  image and title/status separate. Existing stored images not rewritten or approved.
  204 server tests passed, six warnings/six subtests; manager route/syntax passed;
  API rebuilt/deployed. Live diagram probe still failed acceptance with clipped
  equilibrium label, correctly flagged; temporary rows/images cleaned. Checklist
  reviewed; incomplete device/science/feature items retained, no blanket completion.

- Explorer toolbar consistency: New subject/topic actions moved out of faux folder
  tiles into top-right header, same placement/shape as Upload. Sidebar now exposes
  current subject topics and topic section/category shortcuts, including Settings
  children. Removed redundant auto-classification sentence. Empty-folder row spans
  file list instead of wrapping inside checkbox-width column. Upload control kept
  alive across header rerenders. Node route/syntax and image-auth checks passed;
  API rebuilt/deployed. Browser visual/navigation interaction still unverified.

- Unified web manager navigation as topic folder hierarchy: Subjects -> Subject ->
  Topic -> Resources/Notes/Lessons/Reviews/Exams/Settings; Resources contains automatic
  category folders, Settings contains Learning settings/Tools. Removed dashboard
  sidebar workspace entries and hid scope/form cards outside their selected folder.
  New subject/topic folder actions open existing creation forms in a modal; no
  permanent creation cards in browsing view. URL section/folder state and breadcrumbs
  retained; resource global search at Resources root. Node route/syntax/image-auth
  checks passed; API rebuilt/deployed. Browser DOM/visual workflow remains unverified,
  no user records moved or deleted. No Android/device changes.

- Web file-view polish: compact search/upload toolbar, collapsed upload panel,
  type badges, filename links, size/page/status metadata and compact action menus
  replace stacked file cards. Notes moved to separate Notes workspace. Global
  search shown only at topic root, searches contents across that topic's folders;
  category folders keep filename filter. Node route/syntax/image-auth checks
  passed, API rebuilt/deployed. Browser visual/accessibility interaction pending;
  no file mutations, Android installs or device tests.

- Web explorer follow-up: topic folders now group Exams (paper + schedule together),
  Slides, Extra resources and Classifying, with folder in URL/breadcrumb. Compact
  alphabetically sorted file rows, open/download links, accessible checkboxes,
  Select all/count and confirmed Delete selected. Sequential deletion reports
  partial successes and per-file failures instead of stopping silently. Dependency
  protections retained; corrected stale saved-lesson deletion guidance. Node route/
  category-grouping/syntax and image-auth checks passed; API rebuilt/deployed.
  Real browser layout/multi-select/deletion workflow untested, no user files deleted.
  No Android/device actions or change to auto-classification.

- Web Library now browses Subjects -> Topics -> Files with breadcrumb links and
  hash routes (#Library?subject=ID&topic=ID); location restored after refresh/login,
  hash navigation supports Back/Forward. Upload cards hidden until inside a topic;
  category detection remains automatic. Creation forms moved to separate Library
  setup workspace; scope dropdowns retained for other management tools. Upload
  handler now sends every selected file/ZIP to existing batch endpoint instead
  of silently uploading only first file. Node route/syntax and image-auth checks
  passed; API rebuilt/deployed. Browser interaction/visual verification outstanding;
  no resource movement/reclassification, Android install or connected tests.

- Auto-category follow-up: reported 91173 2025 paper/schedule were already extracted
  as extra and bypassed auto-only classification. Known filename inference now runs
  at upload for auto/extra clients (including batch duplicate rows), and extraction
  corrects known extra filenames. Explicit specific categories preserved. Corrected
  only the two reported live extra rows: exm->exam_paper, ass->exam_answers. 201
  tests passed, six warnings/six subtests; API rebuilt/deployed. No paper/answer
  text or human review flags changed, no APK/device test required.

- User requested automatic resource categories: new uploads default auto in web/
  Android/API; optional web classification override collapsed. Extraction resolves
  known NZQA exm/ass filenames and PPTX locally; ambiguous files use bounded
  extracted excerpt with education-reviewer, strict category allowlist, conservative
  extra fallback on invalid/gateway failure. Existing explicit categories unchanged;
  no retroactive reclassification. Classification currently runs in extraction
  transaction; unavailable AI leaves extra rather than failing stored resource.
  200 tests passed, six warnings/six subtests; API rebuilt/deployed, Android debug
  build and normal emulator install Success. No connected tests; live classifier
  accuracy and full upload workflow not verified. Does not imply human approval.

- Added shared tap-to-enlarge image dialog for authenticated exam/lesson images
  and source PDF pages: pinch zoom (1–8x), bounded pan, zoom buttons, reset/close.
  Resource viewer now recognises JPEG/PNG originals as well as PDFs, with bounded
  bitmap decode; resource cards expose Open document / image. Uses existing
  Compose gestures, no new dependency. Zoom is existing bitmap magnification,
  not high-resolution PDF tile re-rendering. Debug/test APK builds passed (existing
  WebView deprecation warnings); zoom-bound test compiled only. Normal emulator
  install Success, no connected tests run; gesture/UI runtime check left to user.

- User requested all-paper gutter audit. Added runnable dry-run/opt-in repair
  script and checked all 76 registered paper/schedule pairs, 235 questions. Dense
  patterned gutter text found in six 2023 standards; other PDFs had at most one
  outer line (not this issue). Repaired twelve pdf-layout questions across 91164,
  91166,91171,91173; 91170 already clean. Private original backup in uploads/
  parser-repair-backups/all-papers-gutters-20261102T054942916046Z.json. Conditional
  updates guard concurrent edits; only question_text/parts changed, no answers,
  marks, rubric or verification changes. 91165/2023 machine-import content preserved:
  no long uppercase fragment runs in its three texts/parts, not re-extracted over
  different import. Post-repair audit reports zero repairable layout questions.
  Original scientific/visual accuracy not certified. No APK/device tests needed.

- Centred Settings/Account/Appearance & library/About dialog titles independently
  of left Back action. Removed legacy manual lesson search/generate form from topic
  reader navigation; topic view now shows saved lessons or an enrolment hint.
  Backend generation and daily workflow unchanged. Includes prior requested level
  grouping in picker/Resource Hub. Debug build passed, normal emulator install
  Success; no instrumentation tests, UI verification left to user.

- User-requested level grouping added to Topics you're learning picker and Resource
  Hub: ascending level headings then alphabetical subjects. Picker carries subject
  level/ID metadata, preventing same-named subjects at different levels merging.
  Debug build passed; normal emulator APK install Success. No connected tests run;
  visual/multiple-level interaction verification pending.

- User clarified: normal APK build/install allowed; no connected tests against the
  installed study app (explicit permission or isolated app ID needed). Reader Sources centring corrected using equal-
  weight left/right header slots instead of unequal SpaceBetween siblings. No
  device actions; visual verification pending user install.

- Fixed reported typing-during-autosave race: answer-keyed LaunchedEffect cancelled
  in-flight PUT acknowledgement after server commit, losing revision. Replaced
  with stable sequential snapshotFlow collection; typing queues latest draft,
  completed PUT updates revision before next write; recovery copy only removed
  when acknowledged content is still latest. Controlled emulator regression holds
  first response while typing and asserts next PUT revision1/latest text. Initial
  test failed because Compose virtual debounce clock was not advanced; corrected
  fixture, targeted runtime test passed. Debug APK explicitly installed Success,
  launch Status ok on emulator-5554. Existing conflict drafts still need explicit
  server reload/recovery restore; genuine cross-client conflicts remain protected.

- User's 91170/2023 exam screenshot exposed fragmented no-writing gutter text in
  extracted questions. Confirmed original PDF tiny fragments lie in outer 40pt
  gutters; parser now excludes lines wholly inside those gutters, retaining body
  starting at x=42.5. Synthetic regression; 198 tests passed, six warnings/six
  subtests. API rebuilt/deployed. Reparsed only pdf-layout 91170/2023 questions
  105–107 without parser warnings; updated question_text/parts (4711→851,
  5283→1423,15764→3149 chars). Prior values saved privately at uploads/
  parser-repair-backups/91170-2023-before-gutter-repair.json, never committed.
  Answers/marks/rubrics/verification flags untouched. App refresh needed; visual
  verification and other already-imported papers remain outstanding.

- Atomic scheduling worker integrated: private non-JSON run identity, locked running
  claim, lesson insert and run completion in same final transaction. Pre-call claim
  remains committed; failure updates cannot downgrade completed run. Legacy callback
  path retained; no blind historical retry. Full server suite 197 passed, six warnings/
  six subtests. Rollback-only PostgreSQL acceptance with current source passed
  including simulated insert/link rollback, persistence response loss, provider loss
  and no duplicate attempts. Initial parent run omitted KaTeX bind asset directory
  and failed readiness; corrected test container env/mount, full rerun passed.
  Android worker fixed restored override drafts/account isolation, stale scan feedback
  and second-marker disagreement; stub-server UI tests compiled, not executed.
  Worker reported app/test APK build exit0. No emulator startup/GPU changes/install.
  Combined API image subsequently built/recreated successfully; /health returned ok.

- Second parallel batch: structure enforcement now mandatory in review promotion;
  malformed/missing practice sections trigger bounded revision, not a false pass.
  Worker updated tiny passing fixtures; semantic question quality remains advisory.
  Parent found actual GitHub fresh-install failure: topic_style_profiles created
  before topics. Startup order corrected; fresh_schema_check reproduced old image
  UndefinedTable then passed against mounted current source, with isolated schema
  cleanup and workers stubbed. Added CI regression. Combined server suite 197
  passed, six warnings/six subtests. Atomic scheduling/Android workers still active;
  no production deployment or emulator startup yet for this batch.

- Reminder subagent integrated: explicit POST_NOTIFICATIONS permission check in
  scheduling; disabled/blocked reminders cancel alarm, token and visible reminder;
  disabled receiver clears stale operation. Seven instrumentation checks compiled
  for default-off, operation reuse/cancellation, simulated permission denial,
  disabled receiver, rescheduling handlers and Auckland DST transitions. Subagent
  reported assembleDebug/assembleDebugAndroidTest exit 0 (JDK21). No runtime tests
  or device permission changes; emulator off, no install, normal GPU unchanged.
  Actual AlarmManager delivery/OS broadcasts/channel blocking remain unverified.

- User authorised parallel subagents. Structure worker added standalone tested
  teaching_structure_issues (3–5 sequential level-three Your Turn sections with
  nonempty bodies, fenced headings excluded). Not yet wired into promotion;
  semantic self-containment/unsolved status remains reviewer responsibility.
  Recovery worker assessed claims/lifecycle read-only: broker rewrite not needed,
  but lesson/run atomic linkage and manual request idempotency are unresolved.
  Contract and conservative offline procedure recorded in docs/job-recovery.md.
  Parent extended PostgreSQL acceptance: unconfirmed/replaced scans hide old
  feedback even with identical answer text; full rollback script passed. Full
  server suite 190 passed, six warnings/six subtests. Emulator/GPU unchanged.

- Android previously ignored second_review payloads: now displays second score,
  outcome/feedback and explicit agreement/disagreement warning separate from first
  mark. Saved-feedback reconstruction retains second mark and computes conflict
  from score/outcome. Provider independence explicitly unverified. Debug/test APK
  builds passed, agreeing/disagreeing JSON checks compiled but not run. No backend
  change/deployment/install; emulator/GPU untouched.

- Android exam now offers Load saved feedback when local answer matches saved
  answer; uses current-answer/scan-filtered GET instead of re-marking. Restores
  first mark plus separate saved override; no gateway call. Corrected misleading
  Feedback is not saved footer (server already persisted marks). Debug/test APK
  builds passed before final text-only footer change; new JSON reconstruction
  test compiled, not run. Emulator off, no install/deploy, runtime read/reload open.

- Fixed stored-feedback GET returning all historical marks as if current. Now
  returns latest per marker only when saved answer text and confirmed scan revision
  match; otherwise 404 without deleting history. 173 tests passed, six warnings/
  six subtests; API rebuilt/deployed. PostgreSQL acceptance script verifies current
  mark readable, then editing answer hides it (404); full script passed/rolled back.
  No Android/emulator changes, no model calls. Historical viewing not exposed by
  this endpoint; underlying rows retained.

- Added/executed concurrent_exam_check.py in unique disposable schema: two actual
  answer-route calls on independent connections -> one 200/revision1, one 409;
  winner stored intact. Simulated lost response by discarding winning result and
  retrying revision0 -> 409/no second write; reload revision1 -> success/revision2.
  PASS, disposable tables/schema cleaned; CI step added, hosted run unverified.
  Not real socket-drop or Android recovery test. No user exams changed, no
  production/deploy/emulator/GPU changes or model calls.

- Added/executed concurrent_note_check.py: actual edit_note calls in two threads,
  independent PostgreSQL connections synchronised before competing updates. Uses
  unique isolated schema/table, no public user-note writes. PASS: one 200, one 409,
  winner's content retained; table/schema dropped in finally. CI integration step
  added, hosted run not verified. This tests DB conflict handling, not HTTP loss
  or Android draft recovery. No production code/deploy/emulator changes.

- Added expandable exam answer/schedule comparison without leaving question:
  current draft (including JSON part answers) and extracted schedule/rubric rendered
  with MathText, explicit unofficial AI rubric label or original-check disclaimer.
  Existing original schedule link retained, comparison collapsed by default.
  Debug/test APK builds passed. No new non-trivial transformation helper/API;
  runtime layout/interaction still unverified, task not marked acceptance-complete.
  No install/server deployment/emulator/GPU changes.

- Override reload follow-up: added authenticated GET override endpoint (null when
  none, 404 for missing item). Android expanded override control loads stored
  judgement before enabling edits, with retry on loading failure. No model call
  required; avoids opening existing judgement as default uncertain. Server save/
  read regression added. 172 tests passed, six warnings/six subtests; Android
  debug/test APK builds passed; API rebuilt/deployed. Emulator off, no install or
  runtime interaction check. Cross-client override last-write semantics unchanged.

- Added missing Android saved override controls beneath current feedback: outcome
  dropdown, required reason and explicit statement that AI/schedule result stays
  unchanged. Uses existing PUT endpoint; failure retains local note, success says
  saved separately. Existing feedback override shown and prefilled when supplied.
  Debug/test APK builds passed; ExamOverrideTest compiled (reason required and
  advisory separation), not run because emulator remains off. No server change,
  deployment or APK install; full save/reload/source comparison still unchecked.

- Wired existing image-cookie auth, collated selection and non-root font-cache
  checks into CI (no paid live gateway probes). Explicit compose.yaml build avoids
  ambiguous alternate Compose filenames. All three checks rerun locally PASS;
  GitHub-hosted run not claimed. No production feature/deploy/APK/emulator change.

- Fixed collated paper repeatedly selecting first questions: mixed mode serialises
  selection via existing exam_items lock and orders unseen first, then lowest last
  saved exam ID. Original-year mode preserves published ordering. No automatic
  monthly scheduling added. Usage history follows saved attempts; deleting one
  removes its contribution. 171 tests passed, six warnings/six subtests; API rebuilt/
  deployed. Actual start route + temp-table PostgreSQL check PASS: four questions,
  three two-question attempts -> [1,2], [3,4], [1,2]. Synthetic tables rolled back.
  No Android/emulator changes; subject-wide realistic composition remains open.

- Added/executed read-only retrieval_relevance_check.py: six plain-language queries,
  one per standard, top-five concept-term coverage and resource ownership checks.
  All six have target term combinations at rank 1; all topic-isolated. Mechanics
  returns one strict result, others five sampled. Prints metadata only, no source
  excerpts. This is lexical coverage proxy, NOT semantic/human relevance scoring.
  Evidence does not justify new embedding dependency yet; broader human-labelled
  benchmark remains open. No production code/deploy/model calls/emulator changes.

- Extended live marking probe with partial two-part answer and optional partial-
  only execution to avoid rerunning prior gateway calls. Actual route/gateway
  three fresh results all 1/2, correct frequency cited, omitted wavelength listed
  as missing, one review enqueued. PASS; synthetic rows rolled back, usage retained.
  Generic outcome achieved comes from percentage fallback, not official NCEA
  descriptors. Real exemplar/borderline accuracy remains open. No production
  change/deployment/Android/emulator activity.

- Extended live uncached marking probe to wrong answer 55 Hz: three marks all
  0/1 not_achieved, populated missing criteria, no original zero-evidence 502.
  Correct-answer rerun three marks all 1/1 (generic excellence label remains
  unofficial). Repeated wrong marks enqueue exactly one review row. Full live
  script PASS; all synthetic study rows rolled back, gateway usage retained.
  No broader partial/borderline/official exemplar accuracy claim; upstream cache
  unknown. No production code/deploy/Android/emulator changes.

- Extended rollback-only acceptance check with actual note-edit route + PostgreSQL:
  first client updates content, stale original returns 409 and newer text remains,
  editing after deletion returns 404. Restores injected connection in finally;
  no existing notes touched. Full seven-check script PASS and synthetic transaction
  rolled back (sequence gaps possible). No app/server behaviour change or deploy;
  no model call/emulator use. Android draft retention still requires UI testing.

- Added/executed opt-in live_mark_consistency_check.py: actual marking route,
  synthetic 1-mark frequency rubric, three fresh requests after deleting only
  disposable attempt's cached marks. All uncached results 1/1, cited evidence,
  outcome excellence via existing generic percentage fallback. That label is NOT
  official NZQA grading or proof achievement-level reasoning merits Excellence.
  Synthetic study rows rolled back, real gateway accounting retained. Upstream
  caching cannot be excluded. Broader partial/borderline/exemplar consistency task
  remains open. No production/deploy/Android/emulator changes.

- Strength selection verified in rollback-only PostgreSQL lesson-route check:
  three correct reviews include Frequency units; a Chemistry mistake with same
  concept label does not suppress Physics strength; recent Physics mistake does.
  Initial run exposed order-dependent assertion in fixture (review_focus[0]);
  changed to membership assertion, full six-check script rerun PASS. Production
  code unchanged, all synthetic rows rolled back; sequence gaps possible. No
  model calls, deployment or emulator/GPU changes. Live pedagogical use still open.

- Lesson generation now receives topic-scoped learner_strengths: >=3 correct AI-
  marked reviews and no incorrect answer for that concept/topic in last 30 days.
  Prompt uses counts only to reduce needless repetition, not as mastery proof or
  factual evidence; explicit app-wide style stays authoritative, no preferences
  invented from results. Existing weaknesses/answer history unchanged. 171 tests
  passed, six warnings/six subtests; API rebuilt/deployed. Full rollback-only
  PostgreSQL cycle/isolation/scheduler/stale-write/deletion script passed, including
  Chemistry empty strengths (no Physics leakage). Live pedagogical use unverified.
  No Android/emulator/GPU changes.

- Fixed Fontconfig cache warning with XDG_CACHE_HOME=/tmp/studyguider-cache,
  owned by existing nobody user. No privilege increase/new dependency. Built image
  passes runnable font_cache_check.py as non-root: PNG text render (11,093 bytes)
  and captured stderr contains no Fontconfig error. API recreated, health ok.
  Does not fix scientific diagram faults or prove image visual correctness.
  No full pytest rerun (Docker environment-only change), emulator/GPU unchanged.

- Added gateway recovery fault-injection checks (no real service outage): urllib
  connection refused -> explicit 502; restored fake transport -> same payload
  succeeds, caller messages unchanged, usage logs error then ok. Reviewer outage
  returns exact original draft with unavailable status; later review retries
  without data loss. 171 server tests passed, six warnings/six subtests. These
  are transport/reviewer unit checks, NOT real gateway restart or Android draft
  recovery acceptance. No production change/deployment/model calls/emulator use.

- Read-only six-standard resource_audit.py passed: ten chunks and ten real-paper
  question rows per standard (120 records), no sampled topic/resource ownership,
  standard or recognised filename/year mismatches. Registered real questions by
  91170/91171/91173/91164/91165/91166: 40/39/42/36/39/39, latest year 2024 for all.
  Three rows per standard have verified_at populated; this is a database fact,
  NOT proof of human review or grounds for marking originals checked. No content
  text printed, no data writes, no gateway calls. Original accuracy/tag relevance
  and human review tasks remain open. No deploy/Android/emulator changes.

- Added one bounded visual-review output retry on same image for malformed JSON/
  invalid schema in generation and saved-image re-review. Gateway exceptions not
  retried; strict boolean pass + empty string issue list still required. 169 tests
  passed, six warnings/six subtests; API rebuilt/deployed. Live probe recovered
  parseable reviews but exhausted three drawing attempts with actual faults:
  wavelength arrow not crest-to-crest and curve discontinuity. Remained flagged,
  acceptance exit 1, temporary files/rows cleaned. Up to nine gateway calls in this
  probe (three drawings, two reviews each); no unlimited retries. Successful
  visual correctness task remains open. No Android/emulator/GPU changes.

- Aligned SVG generation prompt with sanitizer: explicit simple element set,
  direct presentation attributes, no style blocks/classes/links, white background
  and bounded labels. Sanitizer unchanged. 168 tests passed, six warnings/six
  subtests; API rebuilt/deployed. Live probe now renders first attempt (30,194-byte
  PNG), but reviewer returns malformed JSON, confirmed by separate diagnostics;
  stays flagged. Temporary rows/files removed. Fontconfig warning still present.
  Next blocker: recover malformed visual-review output without accepting invalid
  verdicts. No Android/emulator changes.

- Diagram diagnostics now distinguish gateway HTTP status, malformed JSON,
  invalid verdict fields and connection failures rather than collapsing them into
  unavailable review. Existing retry error test asserts malformed-JSON wording.
  168 tests passed, six warnings/six subtests; API rebuilt/deployed. Live probe
  rerun failed before vision: three generation attempts, final sanitiser error
  Unsupported SVG element: style, no PNG persisted. Fontconfig warning repeated.
  Temporary files/rows cleaned. Sanitiser not loosened; successful live diagram
  review remains blocked. Emulator/GPU unchanged.

- Added opt-in live_diagram_check.py using rollback-only synthetic wave evidence
  and a temporary image directory. Real run FAILED acceptance (exit 1): two SVG
  generation attempts, one vision review attempt, PNG signature valid/26,055 bytes,
  final status flagged with Visual review was unavailable. Existing handler folds
  invalid review JSON and provider failure into that message, so precise cause is
  unconfirmed. Fontconfig emitted No writable cache directories; PNG still rendered.
  All temporary images removed and study rows rolled back; real call accounting
  retained. Task stays unchecked, no human visual approval claimed. No production
  code/deploy/Android/emulator changes.

- Explain grounding follow-up: prompts now explicitly prohibit new named substances,
  experiments/measurements/givens absent from sources; omit unsupported examples,
  label everyday analogies and never cite unsupported details. Focus instruction
  also requests source-supported examples. 168 server tests passed (six warnings/
  six subtests); API rebuilt/deployed. Real two-turn Explain acceptance rerun passed
  and omitted earlier unsupported magnesium/acid experiment; replies stayed on
  concentration/collision frequency and constant kinetic energy. This is one sample,
  not claim-level grounding enforcement. Synthetic records rolled back, two real
  usage entries retained. Emulator unchanged; Android interaction still untested.

- Live Explain/follow-up acceptance probe passed server workflow: actual Explain
  route supplies synthetic section/source evidence, previous reply reaches second
  prompt, two real gateway streams finish with done, and actual create_note route
  stores exact second reply plus advisory notice. Synthetic lesson/topic/subject/
  note rolled back; two real usage entries retained, identity sequence gaps possible.
  Responses correctly distinguish concentration/collision frequency from speed at
  fixed temperature, but first reply introduced magnesium/acid example absent from
  saved evidence. Grounding compliance and Android workflow remain unverified.
  Added opt-in live_explain_check.py; no production changes/deploy/emulator startup.

- Actual scheduler PostgreSQL check added to rollback-only acceptance script.
  Temporary schedule/run/course tables shadow public ones for this connection,
  so no real jobs are claimed/disabled. At 01:00 Auckland no callback; at 02:00
  both subject callbacks run once, local date is next UTC calendar day, lessons
  link to correct topics; repeating the tick creates no duplicate claims. Full
  script PASS (five checks), transaction rolled back. Callbacks return previously
  generated synthetic lesson IDs, so real overnight model calls/restart durability
  remain unverified. No app/deploy/emulator/GPU changes.

- Added second-subject isolation to rollback-only PostgreSQL acceptance check.
  Physics completed lesson/answer/mistake remains excluded from Chemistry prompt;
  Chemistry receives only its source, standard 91166 and Collision frequency
  weakness, while Physics stored Frequency focus remains intact. First execution
  failed because synthetic lesson answer omitted required question_key; transaction
  rolled back, fixture corrected, full rerun PASS (learning cycle, subject isolation,
  stale writes, deletion). No user records changed. Real overnight scheduler/model
  isolation remains unverified, task left open. Emulator/GPU unchanged.

- Live bounded lesson correction check passed on synthetic frequency lesson:
  initial inverse-definition/metre-unit errors rejected; teacher revised twice;
  third independent review passed with no issues. Final draft correctly gives
  f=N/t, 8/20=0.40 Hz, citations and three unsolved practice tasks; KaTeX checks
  passed. Five real calls logged, no lesson/student rows saved. Reviewer made an
  overly strict/unclear heading complaint despite numbered headings; successful
  correction does not establish broad reviewer reliability/provider independence.
  Retained opt-in live_revision_check.py. No deploy/APK/emulator changes required.

- Extended rollback-only PostgreSQL acceptance script with actual exam answer
  route calls: first revision-0 save succeeds; second client's revision-0 save
  returns 409 and preserves new answer/revision. After scan replacement, old scan
  revision returns 409 without confirming replacement; checked scan revision-2
  save succeeds, increments answer revision and confirms scan. Full script PASS
  including learning flow and deletion checks; synthetic transaction rolled back.
  Sequential stale-client checks, NOT concurrent sockets or network-loss/draft
  recovery tests. No production changes/deploy/install, emulator untouched.

- Extended existing rollback-only learning-cycle check with populated attempt
  deletion through the actual exam route. Live PostgreSQL PASS: items, scan bytes,
  markings and overrides cascade; bank question, resource and review snapshot
  remain; repeated delete returns 404. Learning-cycle check still passes. Entire
  synthetic transaction rolled back; no existing user exams touched. Identity
  sequence gaps may remain. No production code/deployment/APK changes, emulator
  off. Two-client/network-failure acceptance checks remain open.

- Live streaming accounting acceptance passed against education: three chunks,
  226 text characters, explicit normal completion and exactly one ai_runs entry
  with outcome=ok, response_chars=226, prompt_tokens=2566, completion_tokens=45.
  No token estimates used. Runnable opt-in live_stream_usage_check.py retained;
  normal accounting row intentionally retained (real gateway usage). This checks
  the current alias/provider route only, not every fallback provider or billing
  accuracy. No lesson/student data changed, emulator/GPU untouched. Server code
  unchanged; no deployment or APK installation required.

- Executed opt-in real education-reviewer acceptance probe on two synthetic drafts
  using actual review_and_revise reviewer prompt (teacher revisions deliberately
  stopped). Frequency inversion/8÷20 arithmetic/metre-vs-Hz errors all identified;
  constant-temperature concentration/kinetic-energy misconception also identified.
  Both returned structured pass=false with scientific issues, not only format
  complaints. Reviewer additionally claimed activation-energy fraction changes
  with a catalyst without source support: detection success is NOT evidence of
  globally correct reviewer reasoning. Runnable live_reviewer_check.py retained;
  two calls logged, no saved lesson/student records. Emulator unchanged. Broader
  curriculum, actual model-provider independence and live rewrite quality open.

- Added runnable rollback-only PostgreSQL learning-cycle check using synthetic
  records and deterministic model replies. Executed against deployed schema:
  duplicate marking -> exactly one grounded review item; incorrect review ->
  interval one day; next lesson generation receives Frequency weakness and the
  correct source snapshot, and stores review_focus. PASS, all synthetic records
  rolled back (identity sequence gaps can remain). No gateway call, no existing
  learner data changed. CI integration step added; not itself run in GitHub yet.
  Live-model quality, actual overnight execution and Android interaction remain
  unchecked; full learning-cycle task deliberately left open. Emulator untouched.

- Formula review now compiles extracted dollar-delimited formulas through the same
  bundled KaTeX/mhchem JS assets as Android (Node.js added to server image, Compose
  named asset context avoids duplicating vendor files). No model text evaluation;
  trust=false, maxExpand/maxSize limits and ten-second subprocess timeout. Parse
  failures feed existing rewrite loop; unavailable validation keeps lesson from
  passing. Does not prove mathematical/units correctness or migrate old lessons.
  168 server tests passed, six warnings/six subtests; image built/deployed; deployed
  non-root KaTeX/mhchem valid/invalid checks passed. CI Node setup added. No Android
  changes, emulator left off, no install. Compose builds now require additional
  build-context support (supported by the local tested Compose/BuildKit).

- Read-only retrieval probe: twelve technical/plain-language queries across six
  topics; all results topic-isolated but three plain-language queries were empty.
  Added native ranked OR-term chunk fallback only after strict chunk/page search
  yields nothing, preserving source/topic/status filtering. No embedding dependency.
  Deployed live rerun: previously empty queries for topics 3/4/6 each return twenty
  in-topic matches. This proves recall/non-empty results, NOT relevance or semantic
  quality; task remains open for a proper relevance benchmark. 164 server tests
  passed, six warnings/six subtests; API rebuilt/deployed. No emulator changes.

- Added one Sources action to lesson reader header, displaying saved evidence
  filenames, page numbers and excerpts with a clear advisory warning; no inline
  marker clutter restored, no new API/model call. Debug and test APK builds passed.
  LessonSourcesTest compiled, not run: emulator still off, GPU unchanged, no
  installation attempted. Original-page navigation/visual verification not added.

- Added Android note Edit dialog and authenticated scoped PUT notes endpoint.
  Conditional update compares original content atomically; stale edits return 409,
  missing/deleted notes 404. Errors leave editor/draft intact; explicit Discard
  closes without saving. No migration/new table. Compare-by-content deliberately
  permits equivalent content after an intervening edit (not a revision history).
  163 server tests passed, six warnings/six subtests; debug/test APK builds passed.
  API rebuilt/deployed, health ok. Emulator off; no install or UI test attempted.

- Added optional local exam countdown (1–360 minutes) with start/pause/resume/reset.
  Uses elapsedRealtime so wall-clock changes do not distort running time; stores
  state per server/exam to continue after screen navigation. Device reboot pauses
  the timer at its last saved remaining value, not an authoritative server deadline.
  Expiry never submits/locks answers. No new dependency. Debug and test APK builds
  passed; arithmetic regression test compiled but not run (emulator remains off).
  No GPU changes/install attempted; timer UI, background and restart behaviour
  remain runtime-unverified.

- Task-list batch: missed exam questions now create one due review per exam/question
  with the original question and rubric/source snapshot, no extra model call.
  Unique exam_origin prevents duplicates. Current answer/confirmed scan are locked
  and checked; uncertain/low-confidence/disputed marks and overridden attempts
  are skipped. Oversized question/rubric snapshots are skipped rather than truncated.
  No historical backfill; retained review snapshots survive deletion of the attempt.
  Added POST /diagrams/{id}/review plus manager Retry visual review using unchanged
  image bytes; invalid/unavailable reviews do not promote status. Usage panel warns
  for >=10 calls and >=20% errors in the selected reporting period. Full suite 162
  passed, six warnings/six subtests; Android debug and test APK builds passed;
  browser image-auth check passed. API rebuilt/deployed, health ok. No emulator
  startup/install; live full learning cycle and new UI interactions untested.

- Fixed manager image 401: authorisedImage was sending Bearer cookie-session
  (a UI placeholder), overriding the valid HttpOnly cookie. Fetch now explicitly
  uses same-origin cookies without a bearer header, matching other manager calls.
  node tests/image-auth-check.cjs passed. API rebuilt/deployed; live cookie-only
  GET /diagrams/8/image returned 200, PNG signature valid, 108,283 bytes; temporary
  session revoked. Diagram remains flagged because visual review was unavailable;
  no review bypass or fabricated approval. Browser reload/visual check outstanding.

- Nightly run history now joins the generated lesson's review_status and displays
  it separately from job completion in Android. A completed/flagged draft is not
  represented as reviewed-ready. No new tables or generation changes. 159 server
  tests passed (six warnings/six subtests); debug build passed; API rebuilt/deployed
  and health ok. Emulator remains off, GPU unchanged, APK not installed/UI untested.

- Learning topics now expose Nightly status: latest seven scheduled runs, recorded
  errors and generated lesson IDs via existing /schedule/runs endpoint. UI states
  explicitly that completed generation is not passed AI review. Includes refresh,
  loading/error/empty states. Debug/test APK builds passed; new stub-backed
  NightlyStatusTest compiled but not run (emulator remains off). No GPU changes,
  emulator startup or install attempted. No scheduler/retry semantics changed.

- Topic notes now have Delete with confirmation, using the existing scoped DELETE
  endpoint. Cancel preserves the note; failed requests retain it; successful
  requests remove the card. Original lesson/source data is untouched. Debug and
  instrumentation APK builds passed. Extended TopicNotesTest covers cancel and
  confirmed deletion, but NOT RUN: emulator remains off as requested. No install
  or launch attempted; normal GPU settings unchanged.

- Notes display now hides raw UUID source citations too, without changing saved
  note/evidence content. Added regression sample from reported hydrocarbon note.
  Successful tab navigation clears the stale unsaved-lesson navigation warning
  once lessonPending is false; active save guards remain intact. Debug build and
  two ExplanationNoteTest emulator tests passed. Explicit install Success;
  relaunch Status timeout / WaitTime 11772. Visual and save-guard interaction untested.

- Added Learning > Topic notes so saved explanations can actually be read in
  Android: topic dropdown, refresh, date-labelled full-width note cards, Markdown/
  maths rendering and empty/error/loading states. Uses existing notes API, no DB
  changes or new dependencies. Debug build passed; targeted TopicNotesTest passed
  on emulator (one test: choose topic, fetch/display saved note via local stub).
  Explicit APK install Success; launch returned Status timeout / WaitTime 14714.
  Production note loading and visual appearance untested; editing/deletion skipped.

- Fixed false Explain interruption: live gateway probe returned finish_reason=stop
  followed by EOF, without [DONE]. Reader now accepts explicit stop+EOF as normal
  completion, while rejecting length/content-filter/other finish reasons and
  missing terminal signals. 158 server tests passed (six warnings/six subtests),
  API rebuilt/deployed. Live model_reply_stream check completed successfully with
  four chunks. Server-only fix, no APK update needed. UI interaction untested.

- Explain display follow-up: reused TutorText Markdown block rendering instead
  of one MathText for the full response, so headings/paragraph breaks are parsed.
  Prompt defaults to 120–180 words with short paragraphs and no standard-number
  preamble, expanding when requested. 156 server tests and debug build passed;
  API rebuilt/deployed; explicit emulator install Success. Launch reported
  Status timeout (WaitTime 10939); subsequent pidof returned 5693. No visual
  success claimed; live response length/formatting remains unverified.

- Explain focus correction: reader FAB now sends the current open section title/
  body rather than an empty focus, prefills Explain this section in more detail,
  and labels the dialog Explain this section. Prompt only uses Correct/Partly
  correct/Not yet for explicit marking requests, not concept explanations; section
  explanations request teaching/examples rather than grading the question.
  156 server tests passed; debug build passed; API rebuilt/deployed. Explicit
  emulator install Success, force-stop/relaunch Status ok. Live replies untested.

- Explain follow-ups now include the last three completed exchanges in the current
  panel, bounded to 2,000 question / 8,000 answer characters each. Server validates
  limits and treats history as untrusted context, never source evidence or system
  messages. Failed/partial replies do not enter history. New conversation and
  paragraph/diagram/global focus changes clear history. Session-only, no chat DB.
  156 server tests passed (six warnings/six subtests); debug build passed; API
  rebuilt/deployed and health ok. Explicit adb install Success on emulator-5554,
  followed by force-stop/start Status ok. Real model follow-up and visual UI
  behaviour untested; persistent/full transcript intentionally deferred.

- Explain panel now offers Save to notes for a successfully completed reply,
  using the existing topic-notes endpoint without regenerating the answer. Saves
  question, lesson ID, full answer/citations and an unverified-AI notice. Partial
  streams cannot be saved; oversized notes are blocked rather than truncated;
  save failures preserve the reply and warn about checking for duplicate notes.
  Per user request inline [S1]/page-source markers are hidden in reader/tutor/
  Explain presentation only, leaving stored evidence and saved citations intact.
  Debug build and two targeted emulator instrumentation tests passed (exact note
  request and marker removal preserving chemistry/maths brackets). Installed by
  connected test run; physical-device/UI end-to-end interaction not verified.

- Reader UI correction: removed ubiquitous Create reviewed diagram / Retry
  diagram controls from lesson sections. Reader only displays already attached
  passed diagrams plus Explain, or a notice for an attached flagged diagram.
  Server generation remains available via management endpoints. Debug build and
  emulator install passed; visual behaviour not checked.

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

## 3 November 2026 verification

- `scripts/run-server-tests.sh` runs the server suite in a throwaway container
  (the host lacks FastAPI; the API image lacks pytest and the KaTeX assets).
  Result: 207 passed, six warnings, six subtests passed.
- Live seeded reviewer check extended to five cases; all five drafts rejected with
  scientifically specific issues. Each draft also had weak practice sections, and
  no correct-lesson control was run. Not a measure of general reviewer accuracy.
- Progress-only lesson streaming added (stage events, keepalives, lesson only after
  review). Server suite: 210 passed. API container rebuilt and restarted; the new
  endpoint answers 401 without login (so it exists). Debug APK built with JDK 21 and
  installed on the emulator (`adb install -r`, Success). No connected tests were
  run, and the stage display and a full streamed generation have not been
  exercised yet; they need a live run.

## Website redesign (3 November 2026)

- New design system (`server/web.css`): sidebar navigation on wide screens, a top
  bar with scrolling tabs on phones, light/dark themes, shared card/list/tab/chip
  components. Existing class names kept so Lessons, Review and Exams still style.
- Library and Settings are now pages of the main site (`#library`, `#settings`),
  not a separate page. Library: subjects -> topics -> Files (upload with drag and
  drop, folder filter, status polling, retry/re-extract/delete, bulk delete),
  Standards (link, unlink, save), Notes (add, edit with conflict protection,
  delete) and Search. Settings: topics being learned, teaching style, AI usage
  with the failure warning, and a link to advanced tools.
- `/manage` stays as "Advanced tools" (question/marking checks, diagram manager,
  exam assembly, lesson history). It is not ported.
- Verified: server suite 210 passed; a real Edge run against a mock API rendered
  every new page with no script errors and the layout was inspected on desktop and
  phone width. API image rebuilt after finding the Dockerfile did not copy
  `web.css`; live site and new modules now return 200.
- Not verified: against real data, uploads, edits and deletes (mock API only),
  light mode, and the redesigned Lessons, Review and Exams pages beyond their
  empty states.

## Lessons, Review and Exams redesign (3 November 2026)

- Lessons: "Up next" card with progress and lessons grouped by topic. The reader
  has a section outline, a reading column limited to about 780 px, and a tools panel
  (Explain, sources) that sits beside the text on screens 1500 px or wider.
- Review: it used to load only questions due today. New `GET /review-questions`
  (optional `topic_id`, `limit`, `offset`) lists every saved question. The page now has
  Due now and All questions, with topic/status/text filters, and any question can be
  practised early. Confidence is a row of buttons.
- Exams: set-up and saved exams are a column beside the paper; one question at a
  time with Q1..Qn navigation and Previous/Next; optional browser-only timer
  (start, pause, reset; never locks or submits).
- Verified: server suite 211 passed; Edge run against a mock API at 1920, 1440,
  1280 and 390 px with no script errors; screenshots inspected for Lessons, reader,
  Review and Exams.
- Not verified: answering, saving and marking against the real server, the timer
  while running, and light mode. Lesson text is mock data, not a real generated lesson.

- Exam page formatting fix: the full question text was shown and then every part repeated;
  labels doubled ("(a) (a)"); parent parts such as (b) had answer boxes; PDF line
  breaks split sentences; zero marks showed as "0 marks". Now ported from the Android
  rules: parts shown once with the label beside the wording, answer boxes only on the
  lowest-level parts, "QUESTION ONE: TITLE" shown as a heading, per-part figures,
  lines rejoined into sentences, marks shown only when recorded. Verified in Edge
  with mock data shaped like the reported paper; not yet with the real exam, and
  figure images were not loaded (mock has no image route).

- Website text and input fix: lesson text was shown with raw Markdown (`**bold**`, `*` bullets,
  `---`). `web-common.js` now renders headings, bold/italic/code/links, nested bullet and
  numbered lists, tables, quotes, rules and fenced code, with KaTeX maths cut out first. New
  `mathInput`: a symbol toolbar (fractions, powers, subscripts, roots, Greek, arrows,
  equilibrium arrow, units, \ce{}) that inserts LaTeX at the cursor, plus a live preview,
  on lesson answers, the Explain question, review answers and exam answers. Explain and
  sources are now collapsed panels aligned with the text column. Exam figures are capped at
  300 px tall and open full size on click. Citation removal no longer leaves a gap before
  full stops.
- Verified in Edge with mock data: Markdown, nested lists, maths inside bullets, toolbar
  insertion and preview, column alignment. Not verified: a real lesson, real exam figures
  (the test image was small, so the height cap itself was not exercised), light mode.

## Website sync and autosave (3 November 2026)

- Cause of the sync gap: the website chunked lessons differently from Android, so its section
  numbers and its answer keys (SHA-256 of the section text) never matched the phone's.
  `sections()` now reproduces Android's chunking and question text exactly (heading levels,
  blank/rule lines dropped, list and quote markers stripped), and the key is computed the same way
  (with a pure-JS SHA-256 fallback for non-HTTPS addresses).
- The website now loads the saved reading position and opens the lesson there, saves the position
  when you move (newest wins), shows "In progress / Continue lesson" on today's cards, and picks up
  answers written on another device when the tab regains focus (never over unsaved local text).
- Lesson and exam answers autosave about 0.8 s after typing stops and on leaving the box, with a
  revision check. A conflict shows "Keep my version" or "Use the other version" instead of overwriting.
  Unsaved text is kept in the browser and restored after a reload; failed saves retry every 6 s.
  Review answers keep an unsent draft across reloads.
- Verified in Edge against a mock server that models revisions and 409s: resume at the saved section,
  phone-written answer shown (key matches Android's formula), autosave with the right revision,
  conflict handling both ways, position saved and restored, exam autosave and conflict. Not verified
  against the real server or a real phone; Android's extra per-section questions on non-practice
  sections ("SectionQuestion") are not on the website, and answers saved by the old website under
  its old keys are no longer shown.

## Dark theme from the supplied design system (3 November 2026)

- Applied the "Academic Precision" system from `stitch_modern_website_design_concept.zip` as a
  dark-only theme (the supplied tokens were light; dark roles were derived, not supplied). Inter for text,
  JetBrains Mono for metadata (chips, stat labels, crumbs, status, part labels, timer), 8 px buttons
  and inputs, 16 px cards, pill chips, indigo primary buttons, teal for active and current items, focus ring
  2 px teal, reading text 17/28 px at about 68 characters, content capped at 1440 px.
- AI output now sits in a dashed teal container with an "AI generated · verify with sources" badge
  (lesson banner and feedback, Explain replies, review feedback, exam marking). Autosave status uses the
  design's mono states with a dot: Saving, Saved (green), Local draft (amber).
- Added real counts (files, standards, notes) to the topic page, a Pacific/Auckland chip and an Advanced
  tools link in the sidebar.
- Not taken from the mock-ups because there is no such feature: student profile, notification bell, "New
  Problem Set", extraction daemon and vector index figures, calculated exam scores, NCEA grade checklists,
  formula sheet and scratchpad panels. Fonts load from Google Fonts and fall back to system fonts when offline.
- Verified in Edge against mock data (lessons, reader, practice, review, exam, library, settings at 1440 px
  and 390 px). Not verified: light-coloured contrast measurement, a real lesson or exam, the Stitch layouts'
  extra side panels.

## 3 Nov 2026: task-list pass

- Added `Idempotency-Key` support to `/topics/{id}/lessons/stream` and `/lessons/automatic/stream`; Android sends a key per topic attempt. Test added; suite 215 passed. API rebuilt, APK installed on the emulator (not exercised by tapping).
- Live reviewer control run (`server/tests/live_reviewer_control.py`, five billed calls): correct-science drafts were all rejected, only on structural grounds from thin synthetic lessons. No scientific false positive was seen, but this is not a clean-pass control.
- Not done, needs you or hardware: device/notification/reboot checks, human review of extracted content and questions, real billing rates and budgets, live overnight and gateway-outage runs, A/M/E exemplar marking, handwritten-scan checks, policy decisions (unverified imports, embeddings, automatic diagram choice).

## 3 Nov 2026: emulator pass (manual, no instrumentation tests)

- Driven by adb taps and screenshots on emulator-5554 against the live server; the installed app was not touched by any test runner.
- Verified: the new APK launches; Lessons home lists today's six cards; the Waves lesson opens, renders after about three seconds (the lesson view is blank until the WebView finishes loading), and "Next section" saved position to the server (`lesson_progress` for lesson 77: section 1, revision 1). That is the value the website resumes from; the website side has only been checked against a mock.
- Not exercised: New lesson generation (billed model call), Explain, notes, exam override, notifications.

## 3 Nov 2026: real-schedule marking probe

- User noted real schedules are in the datasets, that dollar costs/budgets can be dropped, and that overnight lessons appear every morning.
- `live_schedule_mark_check.py` (rollback-only): non-answers 0/15 on 4 of 4; schedule text as answer 15/15 on 2, 0/15 on 2 (marker reported no answer, inconclusive). Real student A/M/E exemplars are not in the data, so exemplar agreement remains unmeasured.
