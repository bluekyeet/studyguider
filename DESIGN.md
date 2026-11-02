# StudyGuider design

The original product design is in `writeup.md`; the user's edited working scope
and priorities are in `docs/task-list.md`. Follow that task list, including its
exclusions, rather than restoring superseded writeup recommendations. Recorded
checks and remaining blockers are in `docs/progress.md`.

The database is private to the Compose network. The API binds to localhost by
default. No uploads, credentials or personal study material belong in the repo.

Current implementation includes source-snapshot lessons, bounded teacher/reviewer
rewrites, KaTeX/mhchem syntax checking, streaming explanations, revision-protected
answers, scan transcription confirmation, exam marking and review scheduling.
Use existing database constraints, native platform features and installed assets
before adding services or dependencies. AI feedback/review remains advisory, not
an official mark, human approval or factual guarantee. Machine imports must never
be presented as human-reviewed. Check runtime/acceptance status in the task list;
code existing does not imply a workflow has passed verification. Public deployment
requires TLS and a security review; access and backups are user-managed.

## Visual direction

The supplied Stitch designs guide presentation: deep indigo (`#1E3A8A`), teal
(`#006A61`), pale neutral surfaces (`#FBF8FF`), rounded cards, and generous
reading space. The screenshots are visual references, not live data: do not
show invented status, verification, grades, metrics, or sample study content.
Use native Material 3 controls and accessible contrast and touch targets.
