# StudyGuider task list

Editable follow-up to `writeup.md`, based on the implementation comparison on
2 November 2026. This file is the working task list: follow the user's edits to
scope, ordering and priorities rather than automatically restoring the original
writeup's recommendations. Check the current code before acting on an item.

Status: `[ ]` outstanding, `[x]` completed or explicitly decided. Code existing
does not mean its end-to-end acceptance checks have passed.

## Agreed scope and constraints

- [x] Do not add automatic monthly exams.
- [x] Do not add Google Drive sign-in/import.
- [x] Production access and backups are the user's responsibility.
- [x] Use one app-wide teaching method, not separate subject methods.
- [x] Hide inline source markers in reading content; preserve saved evidence.
- [x] Keep AI-written practice clearly labelled unofficial and separate from real NZQA papers.
- [x] Never fabricate human review, source evidence or verification.
- [x] Keep uploaded resources, real papers, credentials and database dumps out of Git.
- [x] Keep normal emulator GPU settings unchanged; do not restart the emulator unless asked.
- [x] Website parity is deferred, not cancelled.

## Recommended next tasks — edit or reorder

- [x] Connect missed exam concepts to grounded daily review items without duplicates (implemented; live learning-cycle validation remains open).
- [ ] Validate a complete learning cycle: wrong answer → review scheduling → next lesson revisits the weakness.
  - [x] Real PostgreSQL / deterministic-model plumbing check: duplicate prevention,
    one-day wrong-answer scheduling, weak concept and isolated evidence in next lesson.
  - [ ] Verify live-model educational quality and actual overnight/device workflow.
- [x] Add retry of independent visual review for an existing diagram without regenerating its image.
- [x] Add actual formula parsing beyond the existing delimiter/brace checks (bundled KaTeX/mhchem via Node.js, bounded execution).
- [ ] Evaluate semantic retrieval against keyword search; add embeddings if needed.
  - Read-only 12-query six-topic probe: strict search had three empty plain-language queries;
    ranked OR-term fallback now returns in-topic matches for all three. Relevance/semantic
    benchmark remains open; non-empty results do not prove evidence quality.
- [x] Add an optional exam timer (local-device start/pause/reset; runtime checks pending).
- [x] Add editing of saved topic notes with safe conflict handling (conditional original-content update; HTTP 409 retains draft).
- [x] Add visible warnings when model-call failures rise (usage panel, at least ten calls and 20% errors).
- [ ] Resume website study-workflow parity when requested.
- [ ] Notification reminders

## Foundation, access and resources

- [x] Implement single-user password authentication, rate limiting, Android Keystore token storage and browser session cookies.
- [x] Implement subject, topic and standard management.
- [x] Implement four resource categories, original-file storage, extraction, processing status and retries.
- [x] Implement PostgreSQL full-text retrieval over extracted chunks/pages.
- [ ] Verify ingestion, counts and deduplication through Android and web for all six standards.
- [ ] Check extracted content against original documents, including slides and scanned pages.
- [ ] Spot-check subject/standard tags on ten chunks and ten questions per standard.
  - [x] Read-only metadata audit of 120 records: topic/resource ownership,
    standard tags and recognised paper/schedule filename/year pairs consistent.
  - [ ] Check content against originals; timestamps are not human-review evidence.
- [ ] Verify Physics/Chemistry retrieval isolation and multi-standard source selection.

## Lessons and Explain

- [x] Implement source-grounded Markdown lessons with goals, explanations, worked examples and practice.
- [x] Store the exact source evidence and standard snapshots supplied to generation.
- [x] Implement independent structured lesson review and bounded rewrites.
- [x] Detect coding-assistant contamination and structurally broken formula delimiters/braces.
- [x] Implement current-section, paragraph and reviewed-diagram Explain context.
- [x] Implement streaming explanations and recognise the gateway's explicit stop completion.
- [x] Implement session-only follow-up context for the last three completed exchanges.
- [x] Save completed explanations to topic notes without regenerating them.
- [x] Read saved topic notes in Android.
- [x] Implement note deletion with confirmation; runtime checks still outstanding.
- [ ] Verify live Explain focus, follow-up context, streaming completion and note saving together.
  - [x] Actual server routes plus real gateway: section/source payload, previous-turn
    context, two normal stream completions and exact note save; synthetic records rolled back.
  - [ ] Android interaction and unsupported-example handling (live reply added an
    unprovided magnesium/acid example; transport success is not grounding verification).
    - Tightened source-supported-example instructions; live rerun omitted that
      experiment. Broad claim-level grounding is still not automatically verified.
- [x] Make source inspection convenient without restoring inline citation clutter (reader Sources panel; saved filename/page/excerpts, runtime check pending).
- [ ] Stream lesson generation safely without presenting unreviewed content as ready.
- [ ] Evaluate validated structured lesson objects instead of relying on Markdown/model structure.
- [ ] Optional: persistent/full explanation chat history.

## Daily learning loop

- [x] Implement review generation, marking, confidence, mastery and due dates.
- [x] Implement Auckland-time overnight lesson scheduling for enrolled courses.
- [x] Include weak/due review concepts and recent learner answers in lesson generation.
- [x] Display learner-summary counts in Android.
- [x] Display nightly job status, errors and generated lesson review status separately.
- [ ] Run the complete live wrong-answer → tomorrow's lesson acceptance check.
- [ ] Verify multi-subject overnight generation keeps histories and evidence separate.
  - [x] Rollback-only PostgreSQL lesson-route probe: Chemistry excludes Physics
    completed lessons/answers/weak concepts and receives Chemistry evidence/standard.
  - [ ] Actual multi-subject scheduled overnight execution and live model output.
  - [x] Actual run_due with isolated PostgreSQL temporary schedule tables: waits
    until Auckland 02:00, uses next local date, links both subjects, prevents duplicate
    claims on repeated ticks. Callback returns synthetic pre-created lessons;
    real wall-clock overnight/model execution remains open.
- [ ] Improve learner-summary memory: preferred explanations and useful per-subject summaries fed into teaching.
  - [x] Lesson prompts receive topic-scoped strengths (three correct reviews and
    no wrong answer for that concept in 30 days), alongside existing weaknesses,
    answer history and explicit app-wide teaching preference. No inferred preferences.
    - [x] PostgreSQL prompt check: three correct reviews include strength; recent
      same-topic mistake excludes it; same label's other-topic mistake does not.
  - [ ] Validate that live lessons use the context appropriately; persistent narrative
    summaries/preference learning remain deferred pending evidence of need.
- [ ] Evaluate durable queued AI jobs and safe crash recovery; do not retry potentially completed jobs blindly.
- [ ] Run Android nightly-status UI checks after the emulator is available.

## Exams and marking

- [x] Implement filename pairing, PDF layout imports, question parts/figures and paper/schedule references.
- [x] Distinguish machine imports from human-reviewed questions.
- [x] Implement past-paper, collated-paper and explicitly unofficial AI-practice modes.
- [x] Implement typed answers, scan transcription confirmation and diagram/image answers.
- [x] Implement answer/scan revisions and stale-write rejection.
- [x] Implement evidence-linked marking, cached marks and uncertain/low-confidence second review.
- [x] Implement separate learner overrides on the server.
- [x] Recognise N0–E8 schedules and extract supported cut-score tables.
- [x] Implement saved-exam deletion with confirmation.
- [ ] Human-check at least one parsed paper/schedule per standard against the originals.
- [ ] Decide how unverified machine-imported questions may be used; current paths differ from the writeup's strict pre-use human approval gate.
- [ ] Validate realistic subject-wide paper coverage, mark totals and non-repetition/exhaustion behaviour.
- [ ] Validate A/M/E exemplar marking against schedules.
- [ ] Test fresh-model marking consistency separately from cache consistency.
  - [x] Three actual marking-route requests with disposable app cache cleared each
    time agreed on 1/1 for synthetic 0.4 Hz answer and cited rubric. Generic
    percentage fallback labelled it excellence; not an official NCEA judgement.
  - [ ] Broader wrong/partial/borderline answers and real schedule exemplars;
    upstream gateway caching and underlying provider independence unverified.
- [ ] Verify Android answer/schedule comparison and override workflow.
- [x] Connect incorrect exam answers to the daily review queue (reuses question/rubric; skips uncertain, disputed, overridden or stale answers).
- [ ] Validate historical cut-score layouts not supported by current extraction; do not guess missing boundaries.
- [ ] Validate real handwritten answers and diagrams, including scan replacement/conflicts.
- [ ] Run exam deletion/cascade and two-client/network-failure acceptance checks using disposable attempts.
  - [x] Real PostgreSQL rollback-only deletion: cascades items/scans/marks/overrides,
    preserves question/resource/review snapshot; repeated deletion returns 404.
  - [x] Sequential stale-client route checks with PostgreSQL: old answer revision and
    replaced scan rejected with 409; newer data preserved; checked replacement confirms.
  - [ ] Concurrent independent clients, lost HTTP response and Android draft recovery.
- [x] Add an optional timer (Android implementation; does not lock or submit answers).
- [ ] Acquire missing 2025 papers if the user supplies them; never commit them.

## Diagrams and maths

- [x] Implement SVG generation, sanitisation, PNG rendering and independent visual review.
- [x] Use reviewer feedback in the existing bounded regeneration loop.
- [x] Keep failed/unavailable reviews flagged; Android withholds flagged images.
- [x] Display attached passed diagrams with an advisory-review notice and Explain action.
- [x] Remove repetitive diagram-generation buttons from lesson sections.
- [x] Bundle KaTeX/mhchem and provide maths input tools.
- [x] Retry review of existing images after reviewer outages.
- [ ] Automatically select/generate diagrams where useful during lesson creation, not on every section.
- [ ] Verify a successful live diagram correction/review cycle and scientific visual correctness.
  - Malformed-output retry now recovers valid verdicts; latest bounded live loop
    still rejected crest-to-crest arrow/curve faults. Correct rejection is not a pass.
  - Latest prompt correction renders first attempt; visual reviewer returned
    malformed JSON. Failure remains flagged; successful AI review still open.
  - Latest live synthetic wave probe: SVG generation needed two attempts, PNG
    rendered (26,055 bytes), but visual review unavailable/invalid; correctly flagged.
    Temporary files and rows removed. Successful visual review remains blocked.
- [ ] Check diagram attachment, loading and Explain interactions in Android.
- [x] Add full KaTeX-compatible formula parsing to the review/rewrite loop (renderability, not mathematical correctness).
- [ ] Validate formula/units correctness with seeded reviewer tests; parsing alone is not mathematical verification.
- [x] Investigate Cairo's unwritable Fontconfig cache warning (non-root writable XDG cache; PNG render check passes without Fontconfig error).
- [ ] Optional: diagram source editing/regeneration controls.
- [ ] Optional: additional diagram formats only if SVG cannot meet a concrete need.

## Reminders, usage and polish

- [x] Implement opt-in native Android reminder around 7 pm local time, default off.
- [x] Fix browser diagram/page image requests to use the login cookie.
- [x] Implement web/Android call, error and reported-token usage displays.
- [x] Account for streamed model replies and disclose missing token counts.
- [x] Report unavailable dollar costs honestly rather than inventing prices.
- [ ] Runtime-test notification permission, actual delivery, disable/cancel, reboot and timezone rescheduling.
- [x] Verify streaming usage compatibility with the real gateway (education probe: 3 chunks, 226 response characters, 2,566 input / 45 output tokens; one successful accounting row).
- [ ] Add reliable dollar-cost reporting only when billing rates or actual gateway costs are available.
- [ ] Add budget controls after cost/accounting semantics are reliable.
- [x] Add a model-failure warning threshold based on recorded outcomes.
- [ ] Check recent settings, exam dropdown/mode-row, notes and Explain layouts visually.
- [ ] Optional: reminder time picker.
- [ ] Deferred: full website study-workflow parity, including drawing and maths rendering.

## Technical differences from the writeup — not automatic rewrite tasks

- Current database access: synchronous psycopg and startup schema updates, not async SQLAlchemy/Alembic.
- Current background execution: in-process polling threads and database status records, not a separate durable worker queue.
- Current gateway client: standard-library HTTP, not the OpenAI SDK.
- Current Android architecture: Compose state/coroutines/HttpURLConnection, not the proposed Hilt/ViewModel/Retrofit stack.
- Current web manager: server-served HTML/CSS/JavaScript, not a separate Tailwind build.
- Current prompts: largely embedded in Python, not separate prompt files.
- Current diagram format: SVG only.
- Current retrieval: keyword/full-text, not semantic embeddings; the pgvector image alone does not supply semantic search.
- Change these only for a concrete feature, correctness or maintenance need—not merely to match the suggested library list.

## Acceptance and verification baseline

- Latest recorded full server suite: 171 passed, six warnings, six subtests passed.
- Browser image-auth regression check passed; live diagram image cookie-auth request returned 200 with a PNG.
- Recent Android app and instrumentation APK builds passed.
- Some earlier emulator UI tests passed; newest note-deletion/nightly-status tests are compiled but not runtime-verified.
- The complete six-standard acceptance programme has not passed.
- [x] Seed lesson factual/formula/unit errors and verify independent review catches them (two live synthetic cases rejected; reviewer also added an unsupported catalyst statement—broader accuracy not verified).
  - [x] Live teacher/reviewer correction loop on synthetic frequency lesson: initial
    error rejected, two rewrites, final pass, corrected 0.40 Hz and valid KaTeX.
- [ ] Stop/restore the gateway and verify recovery without losing learner work.
  - [x] Fault-injected connection outage returns 502; restored connection accepts
    identical request unchanged, records error then success. Reviewer outage keeps
    exact draft unavailable; retry can pass it. Real gateway never interrupted.
  - [ ] Actual outage plus Android draft/network-response recovery.
- [ ] Validate both gateway aliases under the coding-prompt override and verify genuinely different underlying reviewers where required.
- [ ] Record exact check results and remaining blockers in `docs/progress.md`; do not label untested behaviour verified.
