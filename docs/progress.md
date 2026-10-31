# StudyGuider progress

Status key: **not verified** means the requested end-to-end acceptance test has
not passed, even if part of the implementation exists. This inventory is based
on `writeup.md` and the existing prototype, not a claim of completed features.

## Roadmap and features

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
