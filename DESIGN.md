# StudyGuider design

The product design and roadmap are in `writeup.md`. The first increment is a
FastAPI health endpoint, password authentication and subject/topic creation
backed by PostgreSQL. Public deployment requires TLS and a security review.

The database is private to the Compose network. The API binds to localhost by
default. No uploads, credentials or personal study material belong in the repo.

Current milestone: authenticated subjects, topics and standards, resource uploads,
limited text extraction, topic-scoped search, and experimental unsaved lesson
drafts. Reviewer output is advisory, not an approval or factual guarantee.
Public deployment, the complete Android app, ingestion of scans, durable lessons, review and exam
systems remain outstanding. Validate browser workflows and real gateway calls
before treating the prototype as usable for study.

Android now has a Compose preview with login and subject/topic browsing. The
API has manual review questions and answers, but no marking or rescheduling.
