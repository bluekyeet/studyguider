# NZQA Study Companion: Design Writeup

Oct 31, 2026 · @aa

## Overview and goals

Build one private, password-protected native Android app, backed by a server you run at home, that acts as a personal NZQA tutor: it teaches each topic like a teacher, quizzes you daily, and sets monthly exams built from real NZQA questions. Everything the AI says is grounded in your own uploaded resources, past papers and the standards, so it stays faithful to what you will actually be assessed on.

**Starting scope:** Level 2 Physics and Level 2 Chemistry first, using your slides, PDFs and all three external standards for each subject, then Level 2 and Level 3 Mathematics (algebra and calculus) and the Level 3 sciences. Subjects, levels and topics can be added or removed at any time.

**Guiding principles**

- Grounded, not invented: lessons cite your slides and standards; exam questions are always real, never AI-written.
- Learn fast, retain long: daily review results decide what tomorrow's lesson covers, with spaced repetition behind it.
- Strict marking: answers are compared against the official schedule, with evidence shown, and you can always override.
- Two models for anything important: one writes, a different one reviews (lessons, diagrams, marking).
- Personal use: single user, one password, minimal moving parts.

**Decisions this writeup recommends**

| Question | Recommendation |
| --- | --- |
| Website or app? | A native Android app written in Kotlin with Jetpack Compose, installed on your phone as an APK, plus a small web page for managing resources from a laptop. |
| CSS | Tailwind CSS for the web resource manager page. The Android app is styled with Jetpack Compose and Material 3 theming, since Tailwind is a web framework. |
| Backend | Python with FastAPI, because the AI and document tooling ecosystem is strongest there and it is fully async. |
| Database | PostgreSQL with pgvector for search over your resources. |
| AI access | Your own 9Router, which gives one OpenAI-compatible URL in front of your chosen cloud models, so a model can be swapped per task. |
| Hosting | Docker Compose on your home Proxmox LXC, reached from outside through a Cloudflare Tunnel. |

## Platform and access

The app is a native Android app that talks to your home server over HTTPS. All the AI work and data live on the server, so the app stays small and you rarely need to rebuild it. A connection is required for lessons and AI features, which suits studying at home and at school.

- **Native app**: Kotlin with Jetpack Compose and Material 3, using coroutines and Flow, a ViewModel per screen, and an HTTP client with streaming (server-sent events) so lessons and explanations appear word by word. This gives the fastest, smoothest Android experience. Maths is drawn with KaTeX inside a WebView block, or with an Android LaTeX library for short formulas.
- **Installing**: build and sign the APK in Android Studio and install it over USB or by sideloading. No Play Store listing is needed for personal use. You install each new APK yourself.
- **Password protection**: single user, one password stored as an Argon2id hash on the server. The app exchanges it for a long-lived token kept in Android Keystore storage. Login rate limiting and lockout after repeated failures; optional fingerprint unlock in the app.
- **Reaching the server from home and school**: run a Cloudflare Tunnel (the cloudflared container) so the app connects to a subdomain such as study.yourdomain over normal HTTPS with no router ports opened. Pick one of your two domains and move its DNS to Cloudflare (free plan). This usually works on school networks, where VPNs such as Tailscale are often blocked. Cloudflare Access can add a second login in front.
- **Proxmox LXC**: Docker runs inside an LXC if you enable nesting and keyctl on the container, which works well on an unprivileged LXC with Docker volumes on a mounted disk. Proxmox recommends a VM for Docker, so use a small VM instead if you hit LXC quirks; the compose file is identical. No GPU is needed because all models run in the cloud.
- **Backups**: Proxmox scheduled backups of the container, plus a nightly database dump and copy of uploads to another location.

**Docker Compose services**

| Service | Image or role | Notes |
| --- | --- | --- |
| api | FastAPI app | Handles the app's requests and streams AI replies |
| worker | Same codebase, worker mode | Ingestion, overnight lessons, exam marking, scheduler |
| db | Postgres with pgvector | Named volume on the mounted disk |
| redis | Redis (only if you choose a Redis queue) | Skip it with a Postgres-backed queue |
| tunnel | cloudflared | Outbound-only connection to Cloudflare, no open ports |
| storage | Local volume, or MinIO | Original uploads |
| updater | Optional Watchtower, or a manual command | `docker compose pull && docker compose up -d` |
| 9Router | Your existing instance | Stays where it is; the api and worker call its OpenAI-compatible URL |

## Tech stack

Python and FastAPI on the backend, a Kotlin and Jetpack Compose Android app, and Postgres for everything, so you run as few services as possible.

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | Kotlin, Jetpack Compose (Material 3), coroutines and Flow, KaTeX inside a WebView for maths | Fastest native feel on Android, smooth lists and animation, good support for streaming text. |
| Backend API | FastAPI (async Python), Uvicorn | High concurrency, native streaming (SSE) for AI replies, best AI library support. |
| Model gateway | Your own 9Router (OpenAI-compatible endpoint) | The backend talks only to 9Router; model choice, combos and fallbacks are set there, not in code. |
| Database | PostgreSQL + pgvector | Relational data plus semantic search in one place. Optional full-text search for exact matches. |
| Background jobs | A worker with a queue (Postgres-backed queue, or Redis with ARQ/Dramatiq) plus a scheduler | Ingestion, overnight lesson generation, exam marking. |
| File storage | Local disk or S3-compatible (MinIO, Cloudflare R2) | Keeps originals of every upload. |
| Document parsing | PyMuPDF, python-docx, python-pptx, openpyxl, Tesseract or a vision model for scans | Covers PDF, DOCX, PPTX, XLSX, images. |
| Math and science | KaTeX with the mhchem extension | LaTeX for maths and chemistry, rendered in the app. |
| Diagrams | Mermaid, SVG, Graphviz, matplotlib (server side) | Rendered and checked before you see them. |
| Deployment | Docker Compose | One compose file runs API, worker, database and tunnel; updating is pull and restart. |
| Web resource manager | Small web page with Tailwind CSS, served by the API container | Upload and manage large files from a laptop with the same login and no extra container. |

**Why not a faster language?** Go or Rust would shave milliseconds, but the real latency is the AI model call, not the server. FastAPI is fast enough and keeps all the AI and PDF tooling in one language.

## Architecture and data model

The browser talks only to the API; the API reads and writes Postgres and hands slow work to the worker, which is the only part that calls AI models for batch jobs.

```text
Android app (Kotlin, Jetpack Compose, KaTeX)
        |  HTTPS + session cookie, SSE streaming
        v
FastAPI  ----->  Postgres + pgvector  <-----  Worker + scheduler
   |                 (all data, vectors)            |  ingestion, overnight lessons,
   |                                                |  exam build and marking
   +--> File storage (original uploads) <-----------+
   |
   +--> 9Router --> education (teacher, marker) / education-reviewer (reviewer, vision, ingestion)
```

**Core tables**

| Table | Holds |
| --- | --- |
| subject | Name, level (e.g. NCEA L2), teaching-style text, style profile from slides |
| topic | Belongs to a subject; order, status, mastery score, linked standard |
| standard | NZQA standard number, title, credits, internal or external, official text and grade criteria |
| resource | Uploaded file: type (slides, exam paper, answers, extra), topic, processing status |
| chunk | Extracted piece of a resource (slide, page, section) with embedding and source reference |
| exam\_paper | Year, standard, source resource, parsed status |
| question | One real question: marks, parts, figure images, topic and standard tags, source paper |
| answer\_key | Official answer or marking schedule linked to a question |
| lesson | Generated lesson for a topic and date: content, citations, reviewer verdict, version |
| review\_item | Daily review question, your answer, correctness, confidence, next due date |
| exam | Monthly paper: question list, attempt, marks, grade, feedback |
| attempt\_answer | Your answer to one question, AI mark with evidence, your override |
| diagram | Source code, rendered image, reviewer verdict |
| ai\_run | Log of every model call: task, model, tokens, cost (for budgets and debugging) |

## Learning features

The daily loop is: read today's lesson, ask for more detail where you need it, answer review questions, and let the results shape tomorrow.

**Subjects and topics**

- Add, rename, reorder and delete subjects and topics at any time. Each topic can be linked to one or more NZQA standards.
- Each topic shows a mastery score and status (not started, learning, review, secure).

**Lessons that teach like a teacher**

- A lesson is built step by step: learning goal, prior knowledge check, concept explained in small chunks, worked example, your turn, common mistakes, summary.
- Content is pulled only from your resources and the standard's wording (retrieval), with the source slide or page cited under each section.
- Written in your teacher's style using the style profile (see Resource manager).
- Maths and science use LaTeX; diagrams are generated where they help.

**Explain in detail button**

- Every paragraph, equation and diagram has an Explain in detail button.
- It opens a panel that streams a deeper explanation using that paragraph as context, with extra worked examples, then lets you ask follow-up questions in a short chat.
- Optional Save to notes keeps useful explanations attached to the topic.

**Daily review questions**

- Each lesson ends with a short set of review questions, mixing new material with older topics that are due.
- You record an answer and a confidence level; the AI marks it and explains errors.
- Results update the topic's mastery and each concept's next due date (a spaced-repetition scheduler such as FSRS or SM-2).

**Tomorrow's lesson, generated overnight**

1. A scheduled job runs each night (for example 2 am NZ time) for every active subject.
2. It reads today's review results, weak concepts, due reviews and where you are in the topic list.
3. The teacher model writes tomorrow's lesson from retrieved resources.
4. A different reviewer model checks it against the sources and the standard: factual accuracy, coverage, style match, LaTeX validity. Failures go back for one or two rewrites.
5. The lesson is saved as ready; if it cannot pass review it is flagged instead of shown silently.

A Generate now button runs the same pipeline live, for extra lessons during the day or for testing, with a visible progress view and the reviewer's notes.

## Resource manager

Every subject has a resource manager with four locations per topic, and everything you add is processed so the AI can use it. You can remove any resource and its extracted data is removed with it.

**Where it lives:** in the Android app it sits under Settings, in a Resource manager menu. The same page is on the web at a /manage address on your server, built with Tailwind CSS, for uploading large PDFs and slide decks from a laptop. Both use the same login and the same processing pipeline, and an upload from either shows up in both with its processing status.

| Location | What goes in | What happens to it |
| --- | --- | --- |
| Exam papers | Past NZQA papers (PDF, scans, images) | Questions split out with marks, parts and figures, tagged by standard and topic, stored in the question bank |
| Exam paper answers | NZQA assessment schedules and exemplars | Matched to questions by number and stored as the answer key and grade criteria |
| Slides | Your teacher's slides and notes | Text and images extracted per slide, searchable, used to build the style profile |
| Extra resources | Handouts, textbooks, worksheets, notes | Chunked and indexed for lesson building |

**Accepted file types:** PDF, DOCX, PPTX, XLSX and CSV, TXT, Markdown, HTML, PNG and JPG (read with OCR or a vision model). Google Slides and Google Docs are imported by sharing a link through Google Drive sign-in, which exports them to PPTX or DOCX; or you can download and upload them yourself.

**Processing pipeline**

1. Upload and store the original file untouched.
2. Extract text and images per page or slide; scanned pages go through OCR or a vision model.
3. Split into chunks that keep their source (file, page or slide number).
4. Create embeddings and tag each chunk with topic and standard.
5. Show a status (queued, processing, ready, needs attention) and let you open the result.

**Exam paper check screen:** because parsing errors would feed into marking, a review screen shows each parsed question next to the original page image so you can fix numbering, marks or answer pairing before the paper joins the question bank.

**Teaching style**

- A text box per subject (and optionally per topic) where you write how your teacher teaches: pacing, vocabulary, favourite examples, how they use diagrams, what they emphasise for assessment.
- Upload slides and the AI analyses them into a style profile: slide structure, terminology, kinds of examples, level of detail. The profile is plain text you can read and edit.
- Your text and the profile are injected into the system prompt for every lesson, explanation and exam feedback in that subject.

## Monthly exams and strict marking

Each month the app assembles a paper for each subject from real past-paper questions only, then marks your answers against the official schedule.

**Building the paper**

- Questions are selected from the question bank by the topics you have covered that month, plus a share of older topics.
- The paper mirrors a real exam: similar total marks, question order, and mix of easier and harder questions, with figures and data kept exactly as published.
- Questions already used in a previous monthly exam are not reused until the bank is exhausted. The AI does not write or edit question wording.
- If the bank is thin for a topic, the app tells you what to upload rather than inventing questions.

**Sitting the exam**

- Optional timer, typed answers or photos of handwritten working (read by a vision model).
- Maths and science answers can be entered with a LaTeX helper.

**Marking**

1. The marker model receives the question, the official answer or schedule, the grade criteria and your answer, and nothing else.
2. It must quote the schedule line each mark is awarded against and say what is missing for the marks not given.
3. Instructions are strict: no benefit of the doubt, no marks for partial ideas unless the schedule allows them, and the same answer must always get the same mark (low temperature, fixed rubric).
4. A second model re-marks a sample, or every borderline answer; a disagreement is flagged for you to look at.
5. Marks roll up to a score and an Achieved, Merit or Excellence style grade where the standard uses those judgements.

**Comparing answers yourself**

A side-by-side view shows your answer, the official answer and the AI's mark and reasoning. You can override any mark with a note; overrides are kept and shown separately from the AI's mark. Wrong answers feed back into the daily review queue as new review items.

## Diagrams and LaTeX

The AI writes diagram source code, the server renders it, and a second model looks at the picture before you do.

**Diagram loop**

1. The teacher model outputs a diagram as Mermaid, SVG, Graphviz, or a matplotlib script (for graphs and plots), with a short description of what it must show.
2. The server renders it to an image. Code that fails to render goes straight back for a fix.
3. A different vision-capable model gets the image and the description and checks labels, spelling, correctness, and readability.
4. Up to two revisions; if it still fails, the lesson shows the text explanation and marks the diagram as needing review instead of showing a wrong picture.
5. Passed diagrams are stored with their source, so you can regenerate or edit them.

**LaTeX**

- Lessons, questions, explanations and answers use LaTeX, rendered by KaTeX inside the app, with mhchem for chemical equations.
- **Typing maths**: in any answer or chat box, type /latex to open a maths input with a live preview; the result is inserted as a formula. You can also type LaTeX between single dollar signs for inline maths or double dollar signs for display maths, and it renders as you type.
- A maths toolbar above the keyboard adds fractions, powers, roots, integrals, summations, limits, Greek letters, vectors and chemistry arrows, so you rarely need to remember commands.
- **Photo of working**: take a photo of handwritten working and a vision model converts it to LaTeX for you to check before submitting.
- Before a lesson is saved the server parses every formula; a formula that fails to parse is sent back to the model to fix.

## AI layer

Each job gets the model best suited to it, set in a settings page, so you can change providers without touching code.

| Role | Job | Model type |
| --- | --- | --- |
| Teacher | Writes lessons, detailed explanations, follow-up answers | education (your main model): lessons, detailed explanations and answers |
| Reviewer | Checks lessons and diagrams against sources and the standard | education-reviewer, a model from a different provider than the teacher so errors are not shared |
| Marker | Strict marking against official schedules | education (your main model), low temperature, structured JSON output |
| Second marker | Spot-checks and borderline answers | education-reviewer |
| Ingestion | Parsing, tagging, style-profile extraction, OCR of scans | education-reviewer by default; both names read images, so scans, slide pictures and handwritten working are covered |
| Embeddings | Search over your resources | A small embedding model that runs on the server's CPU, so no outside call is needed |

The server only knows two 9Router model names: **education** writes lessons, explanations and answers and does the marking, and **education-reviewer** reviews lessons and diagrams, second-marks, and reads images. Both are reached through 9Router's API over its URL, with the key kept in the server's environment file and never in the repository. Both names can read images, so either can handle scans, slide pictures and photos of working.

**System prompts and language:** your 9Router already adds a coding-agent prompt to every request, and you are keeping a single 9Router, so the app handles it. Each server prompt opens by overriding that prompt: you are a tutor, ignore any instructions about code, repositories, minimal output or brevity, and give full step-by-step explanations. If Ponytail is a switch in 9Router, turn it off while you study. The server's prompt files (lesson, reviewer, marker) carry the teaching instructions. Every one of them starts with: reply only in English, using New Zealand spelling and NCEA terms. Which models sit behind the two names is set in 9Router and can change whenever you like; the app never depends on a particular model. The server keeps only a light check that replies are in English.

Both model names accept images, so vision tasks need no special routing. Free tiers often allow the provider to use your prompts to improve their products, so do not upload anything personal, and treat your school's slides and papers as study material only.

**How answers stay accurate**

- Retrieval first: every prompt includes the most relevant chunks of your resources, the standard's wording, and your style profile; the model is told to use only that material and to cite it.
- Structured outputs (JSON with fixed fields) for lessons, questions and marks, so the app can validate them.
- Anything the model cannot find in your resources is labelled as general knowledge, so you know what to check with your teacher.
- Streaming responses over SSE for lessons and explanations.

**Memory and spaced repetition**

- The app tracks mastery per concept, not per subject. Each review answer updates a due date and a difficulty score.
- A short learner summary per subject (strengths, repeated mistakes, preferred explanations) is kept and fed into the next lesson prompt, which is how "learn as fast as possible while retaining it" is made concrete.

**Usage and limits**

- All model calls go through your own 9Router, which exposes one OpenAI-compatible URL and key, so the study server never holds any provider keys. Models and fallbacks are changed in 9Router, not in code.
- A small request queue with retries stays in place as a safety net, since providers can still throttle bursts.
- Overnight generation still makes sense: lessons are ready each morning and the daytime stays free for explanations.
- Every call is logged with tokens and outcome on a usage page, and lessons, explanations, embeddings and parsed papers are cached once generated.
- Heavy coding use of the same keys can eat the quota, so the usage page warns when failures rise.

## Repository and GitHub setup

The project lives in one public repository, [bluekyeet/studyguider](https://github.com/bluekyeet/studyguider), so it must hold code only: no API keys, no slides, no NZQA papers and no database dumps.

**Suggested layout**

```text
studyguider/
  server/    FastAPI api and worker
  app/       Kotlin and Jetpack Compose Android project
  web/       Tailwind CSS resource manager page
  deploy/    docker-compose.yml and .env.example
  docs/      this design writeup
  README.md  LICENSE  .gitignore
```

**What stays out of the repository**

| Item | Where it lives instead |
| --- | --- |
| 9Router URL and key, password hash, tunnel token | .env file on the server, listed in .gitignore; the repo only has .env.example with empty values |
| Uploaded slides, papers, schedules | The server's uploads volume and your Proxmox backups |
| Database files and dumps | Docker volume and backups |
| Android signing keystore and its password | Your own machine, listed in .gitignore |
| Test files that are real NZQA papers or school slides | Your machine only; the repo's automated tests use small sample files you write yourself |

**Set up with the GitHub CLI**

If the repository already exists on GitHub, clone it:

```bash
gh auth login
gh repo clone bluekyeet/studyguider
cd studyguider
```

If you are starting from a local folder instead:

```bash
gh auth login
git init -b main
gh repo create bluekyeet/studyguider --public --source=. --remote=origin
```

Then add the skeleton and push, and give the repository a description and topics:

```bash
git add .
git commit -m "Initial project skeleton"
git push -u origin main
gh repo edit bluekyeet/studyguider --description "Personal NCEA study tutor: Android app, FastAPI server, AI lessons and exam marking" --add-topic ncea --add-topic fastapi --add-topic jetpack-compose
```

Because the repository is public, check each commit for secrets before pushing, and rotate a key straight away if one is ever committed. Optionally, GitHub Actions can build the server image and publish it to the GitHub Container Registry, so the Proxmox container only needs to pull and restart.

The repository uses the MIT licence: choose MIT when creating the repository on github.com, or add a LICENSE file with the MIT text to the first commit. Only code is committed, which includes the server, the Android app and the web page; resources, keys and test data never are.

## Testing plan

Test with all three Level 2 external standards in both Physics and Chemistry from the first build, so every feature runs across several standards and two subjects before more content is added. That is six standards in total, each with its slides, past papers and answer schedules.

| Subject | Standard | Title |
| --- | --- | --- |
| Physics | 91170 | Waves |
| Physics | 91171 | Mechanics |
| Physics | 91173 | Electricity and electromagnetism |
| Chemistry | 91164 | Structure and bonding |
| Chemistry | 91165 | Organic chemistry |
| Chemistry | 91166 | Chemical reactivity |

Load past papers and answer schedules for 2017 to 2025, nine years per standard, which gives the monthly exams a deep pool of real questions without repeats.

| Area | What to test | Pass when |
| --- | --- | --- |
| Ingestion | Upload slides, papers and schedules for all six standards, from both the app and the web page | Every file reaches ready; page and slide counts match the originals; the same file from either route appears once |
| Tagging | Spot-check 10 chunks and 10 questions per standard | Each carries the right subject and standard |
| Question parsing | Use the check screen on one paper per standard | Question numbers, marks and answer pairing match the original after your fixes |
| Retrieval isolation | Ask for a Physics topic, then a Chemistry topic | Lessons cite only resources from the right subject and standard |
| Multi-standard lessons | Generate a lesson for a topic in each of the three standards of one subject | Each lesson uses its own standard's wording and no other standard's content |
| Multi-subject nightly job | Run Physics and Chemistry overnight generation in the same night | Style profiles, review history and lessons stay separate |
| Monthly exam | Build a paper for each subject | Questions are real, come from all three standards, are not repeated from earlier papers, and total marks look like a real exam |
| Marking consistency | Mark the same answers three times | Identical marks every time; education-reviewer disagreements are flagged |
| Marking strictness | Mark exemplar answers at Achieved, Merit and Excellence level | Each lands on the expected grade, with the schedule line quoted |
| Reviewer | Seed lessons with deliberate errors such as a wrong formula or unit | education-reviewer catches them |
| Maths and diagrams | Type with /latex and generate diagrams for Physics and Chemistry topics | Formulas render; diagrams pass the review loop or are flagged |
| Daily loop | Answer review questions wrongly on purpose | The next night's lesson revisits those concepts |
| Failure handling | Stop 9Router, then restore it | The app shows a clear error and recovers without losing work |
| Prompt override | Ask both models to explain a topic and to mark an answer, through 9Router with its coding prompt on | Explanations are full and step by step, marking feedback is complete, and the language is English |

Automated tests (pytest for the server) use small sample files you write yourself, never the real papers, so the public repository stays clean. The full six-standard run is done by hand on your own data.

## Project skeleton

The skeleton is the smallest set of folders, files and services that lets you run `docker compose up`, sign in from your phone through the tunnel, create a subject and upload a file, with every later feature slotting into a place that already exists.

**Repository tree**

```text
studyguider/
  README.md  LICENSE (MIT)  .gitignore  .editorconfig
  .github/workflows/ci.yml
  deploy/
    docker-compose.yml
    .env.example
  server/
    Dockerfile  pyproject.toml  alembic.ini
    migrations/                 database versions, seed of the six standards
    app/
      main.py                   FastAPI app, routers, startup checks
      config.py                 settings read from the environment
      db.py                     async database engine and session
      auth.py                   password hash, login, tokens, rate limit
      cli.py                    set-password and other admin commands
      models/                   subject, topic, standard, resource, chunk,
                                exam_paper, question, answer_key, lesson,
                                review_item, exam, attempt_answer, diagram, ai_run
      routers/                  auth, subjects, topics, resources, lessons,
                                reviews, exams, usage, health
      services/
        llm.py                  one client for 9Router (education, education-reviewer)
        ingest/                 pdf.py pptx.py docx.py image.py, chunking, embeddings
        retrieval.py            search over chunks by subject, standard, topic
        lessons.py              write, review, revise, save
        marking.py              strict marker and second marker
        exams.py                collate real questions into a paper
        diagrams.py             render and review loop
      prompts/                  lesson.md reviewer.md marker.md style_profile.md
      worker.py                 job runner and nightly schedule
    tests/                      pytest with small self-written sample files
  web/
    package.json  tailwind.config.js
    src/input.css  src/manage.html  src/login.html
    dist/                       built CSS and pages, served by the API
  app/
    settings.gradle.kts  build.gradle.kts  gradle/libs.versions.toml
    app/src/main/java/.../
      data/                     API client, token storage, repositories
      domain/                   models and use cases
      ui/                       login, subjects, topics, lesson, review, exam,
                                settings/resourcemanager, math input
    app/src/main/assets/katex/  KaTeX files for maths rendering
  docs/design.md                this writeup, exported
```

The prompts live in plain text files so you can read and tune them without touching code.

**Libraries**

| Part | Choice |
| --- | --- |
| Server | FastAPI, Uvicorn, Pydantic Settings, SQLAlchemy 2 (async) with asyncpg, Alembic, pgvector, argon2-cffi |
| 9Router client | The official OpenAI Python SDK pointed at 9Router's URL, so streaming and image input work as normal |
| Background jobs | Procrastinate, a queue that uses Postgres, with periodic tasks for the nightly run; this removes the need for Redis |
| Parsing and embeddings | PyMuPDF, python-pptx, python-docx, and a small CPU embedding model through fastembed |
| Quality | ruff, pytest, and pre-commit with a secrets scanner so keys are never committed |
| Web page | Tailwind CSS built with its CLI, plain HTML and a little JavaScript |
| Android | Kotlin, Jetpack Compose with Material 3, Navigation Compose, Hilt, OkHttp and Retrofit with server-sent events, kotlinx.serialization, WorkManager for uploads, Android Keystore for the token |
| Android SDK | minSdk 26, targetSdk set to the current stable release |

**Compose services**

The skeleton starts with four containers: db (Postgres with pgvector), api, worker and tunnel. 9Router stays where it is.

**.env.example** (names only, no values)

```text
DATABASE_URL=
SECRET_KEY=
ROUTER_BASE_URL=
ROUTER_API_KEY=
MODEL_TEACHER=education
MODEL_REVIEWER=education-reviewer
TUNNEL_TOKEN=
UPLOAD_DIR=/data/uploads
EMBEDDING_MODEL=
NIGHTLY_HOUR=2
TZ=Pacific/Auckland
```

**Day-one checklist**

1. Repository with MIT licence, .gitignore, README and the empty folder structure above.
2. `docker compose up` starts db, api and tunnel, and a health endpoint answers through your domain.
3. First migration creates the core tables and seeds the six standards.
4. A command sets your password; the login endpoint returns a token and locks out repeated failures.
5. Subject and topic endpoints work, with tests.
6. A debug endpoint sends a tiny text prompt and a tiny image to both `education` and `education-reviewer` and shows the replies.
7. The upload endpoint stores the original file and a stub job marks it ready; real parsing comes later.
8. The web page at /manage has login, the subject and topic lists, and an upload form with status.
9. The Android app has login, subject list, topic list, and Settings with a Resource manager that uploads through the file picker and shows status.
10. GitHub Actions runs ruff and pytest for the server and builds the debug app, using no secrets.

**Done when:** from your phone you sign in through the tunnel, create Physics with standard 91171, upload a PDF from the app and another from the web page, and both show as ready.

## Build roadmap, risks and open questions

Build in five phases, each ending with something you can study with.

1. **Foundation**: Docker Compose stack on the Proxmox LXC with tunnel and login, Android app shell (Kotlin and Jetpack Compose), subjects and topics, database, model gateway.
2. **Resources and lessons**: uploads, parsing, embeddings, teaching-style box, lesson generation with citations, KaTeX, Explain in detail.
3. **Daily loop**: review questions, mastery and spaced repetition, overnight generation with the reviewer model, Generate now.
4. **Exam system**: past-paper and schedule ingestion with the check screen, question bank, monthly paper builder, strict marker, side-by-side comparison and overrides.
5. **Polish**: diagram generation and review loop, slide style profiles, daily reminder notification, backups, cost dashboard.

**Risks and how they are handled**

| Risk | Mitigation |
| --- | --- |
| AI states something wrong | Retrieval from your resources with citations, a reviewer model, and general-knowledge labelling |
| Exam parsing errors corrupt marking | Human check screen before a paper enters the bank |
| Marking drifts or is too lenient | Fixed rubric, low temperature, quoted schedule lines, second marker, your override |
| Copyright of papers and slides | Personal study use only; check NZQA's and your school's terms before uploading, and keep the site private and unshared |
| Standards and qualification changes | Standards are editable records with a year, so updates do not need code changes; confirm current requirements on the NZQA website |
| Free quota runs out or changes | Request queue with rate limiting, fallback between providers set in 9Router, overnight generation, caching, usage page |
| Password leak or exposure | Argon2id, rate limits, Cloudflare Tunnel with Access, keystore token in the app, backups |

**Open questions**

- None right now: the design is settled enough to start building the skeleton.
