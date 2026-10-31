# StudyGuider

A personal NCEA study companion. See `writeup.md` for the product design and
`DESIGN.md` for the current implementation scope.

## Run locally

Install Docker and Docker Compose, copy `.env.example` to `.env`, and set
`POSTGRES_PASSWORD` to a strong, unique password. Set
`POSTGRES_PASSWORD_URLENCODED` to the URL-encoded version of the same password
(for a password containing only letters and digits, the values are identical).
Then run:

```sh
docker compose up --build
```

Visit http://localhost:8000/health. This initial endpoint checks that the API
process is running; it does not check database connectivity. Stop the services
with `docker compose down`; the database volume is retained.

Set the login password interactively with `docker compose exec api python
set_password.py` (at least 12 characters). The API provides `/login`, `/logout`,
`/subjects`, and `/subjects/{id}/topics`; use the login token as a Bearer token.
Changing the password revokes existing sessions. Five failed logins lock login
for 15 minutes. The health endpoint only checks the API process.
Open `http://localhost:8000/manage` for the basic resource manager. Its token is
held in memory and is discarded when the page is closed or refreshed.
Subjects and topics can be created, listed, renamed and deleted through the API.
Delete a subject's topics first; subject deletion will not silently remove them.
Standards can be added or updated with `PUT /standards/{number}`, listed at
`/standards`, and linked or unlinked with `PUT` or `DELETE` at
`/topics/{id}/standards/{number}`. Official standard text is not preloaded;
verify any entered criteria against NZQA.
The resource manager can save standard records and link or unlink them from a
topic. Saving an existing number replaces its title and notes.

The API also supports manually created review questions and recorded answers
with confidence-based rescheduling. Confidence is self-assessed, not AI marking;
review history prevents topic deletion.
The web manager and Android app can generate review-question drafts from
matching resources. Check and approve each question before adding it to the queue;
generation sends source excerpts to the configured model provider.

## Android preview

Open `android/` in Android Studio, or run `gradlew.bat assembleDebug` there
with JDK 17 or 21 and Android SDK 36 installed. The debug APK supports login
and creating and browsing subjects and topics, uploading resources, answering
review questions and generating experimental lesson drafts. Sessions are kept
only in memory. The debug build permits
HTTP for local emulator testing; release builds require HTTPS. Never use real
passwords over HTTP. On the Android emulator, `10.0.2.2` refers to the host.
Authenticated clients can upload files (up to 50 MiB) to
`/topics/{id}/resources`, list them there and download them at
`/resources/{id}/download`. Files are stored in a separate Docker volume and
are automatically processed by a background worker; `POST /resources/{id}/extract`
can also retry processing manually. Interrupted jobs may remain `extracting`
and need administrative recovery after all workers are stopped. Extraction
extracts UTF-8 TXT, Markdown, CSV, HTML, XLSX, text-based PDFs, PowerPoint slide
text and Word paragraph text; scanned or empty PDF
pages require OCR, which is not implemented. `GET /resources/{id}/text` returns
the text and `/resources/{id}/pages` returns page references. Extracted text is
can be used for experimental lesson drafts. Other file formats are not implemented yet.
`GET /topics/{id}/search?q=...` searches extracted text within one topic using
PostgreSQL full-text search and returns up to 20 matching source pages or slides.
The resource manager also provides a search form for the selected topic.
Topic notes can be saved and deleted in the resource manager; topics containing
notes cannot be deleted until those notes have been removed.
For an experimental, unsaved lesson draft, set `ROUTER_BASE_URL` to the
9Router OpenAI-compatible base URL and `ROUTER_API_KEY` in `.env`, then call
`POST /topics/{id}/lesson-draft` with JSON `{"query":"..."}`. It sends up to
five matching source excerpts and linked standards to `education` and
`education-reviewer`. Both calls send your material to those model providers.
The result is always a draft: citations and reviewer claims are not verified,
and no lesson is saved. The calls can take up to 90 seconds each.
Alternatively, `POST /topics/{id}/lessons` generates and saves a draft with
snapshots of the supplied evidence, and `GET /topics/{id}/lessons` lists saved
drafts. A reviewer failure is recorded; neither review nor source citations
are automatically verified.

The exam manager registers questions by verified references to uploaded paper
and schedule pages, and assembles exams from selected questions. Experimental
feedback requires extracted text on both referenced pages and checks that its
quoted evidence appears in the schedule. It is not an official mark and is not
saved; independently check the original assessment schedule.
`POST /exams/monthly` can select verified questions for a subject, preferring
unused questions. It does not schedule exams automatically or guarantee a
realistic balance of standards, topics or marks.
PowerPoint references are slide numbers; Word text is returned as one section,
not page numbers. Images, PowerPoint tables and Word tables are not extracted.
Delete a resource with `DELETE /resources/{id}`; if removal fails or is
interrupted, its status remains `deleting` and the same request can be retried.
Resources referenced by saved lessons or exam questions cannot currently be
deleted; those records must remain available until safe deletion is implemented.
Back up both the database and uploads volume together.
See `deploy/BACKUP.md` for the proposed backup and fresh-project restore
procedure. A disposable restore drill recovered synthetic database and upload
data; repeat the drill in your own deployment before relying on it.

Nightly lesson generation is opt-in via `PUT /topics/{id}/schedule` with
`{"query":"waves","hour_utc":14,"enabled":true}`. The hour is UTC, not
New Zealand local time by default. For NZ local time and automatic daylight-saving
adjustment, include `"timezone":"Pacific/Auckland"` and set `hour_utc` to the
desired local hour (the field keeps its original name for compatibility). Generation sends
matching source excerpts to the configured model providers. Inspect
`GET /topics/{id}/schedule/runs` for failures or interrupted runs; interrupted
runs are not automatically retried.

The API is bound to localhost. Do not expose it to the internet yet: TLS,
deployment hardening and a security review remain outstanding. Upload requests
require Content-Length and have an application-level size check; enforce a
streaming request-body limit at the proxy before any public deployment.

## Test

With Python, the dependencies from `server/requirements.txt`, pytest and httpx installed:

```sh
python -m pytest server/tests -q
```

`server/tests/integration.py` is an HTTP integration check for a **disposable**
Compose database only: it replaces the configured password and revokes sessions.
