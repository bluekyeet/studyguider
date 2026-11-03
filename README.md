# StudyGuider

![StudyGuider](server/branding/wordmark.png)

A personal NCEA study companion for one learner (Physics and Chemistry so far). A FastAPI + PostgreSQL
server, an Android app and a website all share the same data, so lessons, answers and reading position
follow you between devices.

AI output is study help, not an official NZQA result. Lessons, marks and explanations are labelled as
unverified, and AI-written practice is kept separate from real past papers.

## What it does

- **Library:** upload past papers, schedules, slides and notes per topic. Files are stored as-is, text is
  extracted in the background (including OCR for scanned pages) and searched with PostgreSQL full text.
- **Lessons:** one lesson per topic you are learning is prepared overnight (New Zealand time) from your own
  sources, reviewed by a second model and bounded rewrites. Practice sections save your answers and give
  AI feedback. Explain answers questions about a section and can save the reply to topic notes.
- **Review:** short spaced-repetition questions made from completed lessons and wrong exam answers, with
  confidence ratings, due dates and a mastery estimate per topic.
- **Exams:** original past-paper questions, mixed practice, or clearly unofficial AI practice. Typed or
  scanned answers, evidence-linked AI marking checked against the schedule, and your own override.
- **Rapid questions:** pick a topic and flash through exam questions (past-paper and AI-written, prepared ahead), with no
  feedback until you end the session. Answers are marked in the background and the results are a grade breakdown. Misses go to
  **Exam revision** and to your lessons. Both live under Exams.
- **Home:** today's lessons, reviews due, mastery per topic and a rough estimated grade (from review
  answers only, not an NZQA grade), weak concepts and recent exams.

Clients: the website at `/` (Home, Lessons, Review, Exams, Library, Settings), the Android app (same
areas), and `/manage`, a developer-style "Advanced tools" page for diagram review, question parsing and
checks, exam assembly and schedule runs.

## Run the server

Install Docker and Docker Compose, then:

```sh
cp .env.example .env          # set POSTGRES_PASSWORD and POSTGRES_PASSWORD_URLENCODED
docker compose up --build
docker compose exec api python set_password.py    # login password, at least 12 characters
```

Open http://localhost:8000. `/health` only checks that the API process is up.

The AI features need an OpenAI-compatible gateway: set `ROUTER_BASE_URL` and `ROUTER_API_KEY` in `.env`.
The server calls the model aliases `education` and `education-reviewer`; your uploaded material is sent
to those providers when you generate or review anything.

The API is bound to `127.0.0.1` on purpose. Do not expose it to the internet without TLS, a streaming
request-body limit at the proxy, per-client login throttling and a security review. Back up the database
and the uploads volume together (`deploy/BACKUP.md`).

## Android app

Open `android/` in Android Studio, or build from a terminal with JDK 17 or 21 (not 25) and Android SDK 36:

```sh
cd android
./gradlew assembleDebug      # gradlew.bat on Windows
```

Sign in with the server address and password. On the Android emulator the host machine is
`http://10.0.2.2:8000`. The login token is kept in the Android Keystore. Debug builds allow cleartext
HTTP for local testing; do not use real passwords over HTTP, and use HTTPS for anything else.

Do not run the connected/instrumentation tests against a device that has the app you use: the test runner
can remove it.

## Tests

The server suite runs in a throwaway container and touches no running containers or data:

```sh
scripts/run-server-tests.sh
```

Without Docker, install `server/requirements.txt`, `pytest` and `httpx`, then
`PYTHONPATH=server python -m pytest server/tests -q`. CI (`.github/workflows/ci.yml`) also builds the debug
APK and runs integration checks against a disposable Compose stack.

Scripts in `server/tests/` named `live_*` call the real model gateway and are opt-in (they cost model
calls). `server/tests/integration.py` replaces the login password and must only be pointed at a
disposable database.

## Layout

```
server/      FastAPI app, background worker, the website (web*.html/css/js) and its tests
android/     Android app (Kotlin, Jetpack Compose)
docs/        task list, progress log, job-recovery notes, website functional spec
deploy/      backup and restore procedure
scripts/     test runner and resource import helper
tests/       small Node checks used by CI
assets/      branding source images
```

The website has no build step: plain ES modules and one stylesheet, served by the Python server. A new
`web-*.js` file must be added to the allow-list in `server/app.py`.

## More documentation

- `docs/task-list.md`: the working task list, with what is verified and what is still open.
- `docs/progress.md`: dated log of checks and results, including what was not tested.
- `docs/website-functions.md`: what each website screen must do.
- `docs/job-recovery.md`: how interrupted lesson jobs are handled.
- `DESIGN.md` and the top of `docs/task-list.md`: scope and rules (no automatic monthly exams, no Google
  Drive import, one app-wide teaching method, and so on).

Uploaded resources, real papers, credentials and database dumps must never be committed.
