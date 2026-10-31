# StudyGuider design

The product design and roadmap are in `writeup.md`. The first increment is a
FastAPI health endpoint, password authentication and subject/topic creation
backed by PostgreSQL. Public deployment requires TLS and a security review.

The database is private to the Compose network. The API binds to localhost by
default. No uploads, credentials or personal study material belong in the repo.

Current prototype: authenticated subjects, topics and standards, resource
uploads and text extraction, search, saved lesson drafts, confidence-based
review scheduling, and manually verified exam references. AI feedback is
advisory, not an official mark or factual guarantee. Public deployment, scan
ingestion and complete exam workflows remain outstanding. Validate browser
workflows and real gateway calls before relying on the prototype for study.

## Visual direction

The supplied Stitch designs guide presentation: deep indigo (`#1E3A8A`), teal
(`#006A61`), pale neutral surfaces (`#FBF8FF`), rounded cards, and generous
reading space. The screenshots are visual references, not live data: do not
show invented status, verification, grades, metrics, or sample study content.
Use native Material 3 controls and accessible contrast and touch targets.
