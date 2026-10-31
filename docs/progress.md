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

- The acceptance data path in the request is still the literal placeholder
  `[PATH TO MY LOCAL DATA FOLDER, outside the repo]`; no papers, schedules or
  slides have been supplied for the required six-standard run.
- Real 9Router endpoint/credentials and the deployed tunnel/domain are not
  provided in the request. Do not record secrets or private material here.
- `AGENTS.md` is absent; `DESIGN.md` and `writeup.md` were read.
- The existing application is a prototype; its advisory model feedback does not
  establish deterministic marking or official NZQA grades. Low temperature alone
  cannot guarantee identical model outputs, and a model reviewer cannot prove
  factual correctness. Acceptance must be measured, not assumed.
