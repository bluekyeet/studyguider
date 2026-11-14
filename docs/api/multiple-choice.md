# Multiple-choice questions: API contract

Multiple choice is one more **answer form** (PR #14, `server/answer_forms.py`), so it arrives wherever answer forms already
arrive and needs no new endpoints. Everything here is additive: a client that ignores `"kind": "choice"` still shows the
question text and a text box, and a typed answer such as `B` is still accepted and marked.

## 1. The form

Every place that already returns answer forms can now include one form of kind `choice`:

| Where | Field |
|---|---|
| Review list items (`GET /review-questions/due`, `GET /review-plan` → `items`, `GET /review-questions`) | `answer_forms` (list) |
| Exam questions (`GET /exams/{id}` → `questions[]`) | `answer_forms` (object: `""` for the whole question, `"(a)"`, `"b(ii)"`… per part) |
| Rapid questions (`GET /rapid/{exam_id}/current`, `POST /rapid/{exam_id}/next`) | `answer_forms` (list) |
| Revision packs (`GET /revision/packs/{id}` → sections → `questions[]`) | `answer_forms` (list) |

```json
{
  "kind": "choice",
  "options": [
    {"key": "A", "text": "$2.0\\ \\text{m s}^{-1}$"},
    {"key": "B", "text": "$4.0\\ \\text{m s}^{-1}$"},
    {"key": "C", "text": "", "image": "/resources/6f1c…/pages/3/diagram-image?x0=72&y0=410&x1=250&y1=520"},
    {"key": "D", "text": "None of the above"}
  ],
  "multiple": false,
  "shuffle": false,
  "display_order": ["A", "B", "C", "D"],
  "instructions": "Choose one answer.",
  "group": "",
  "penalty": 0
}
```

| Field | Type | Meaning |
|---|---|---|
| `options` | list, 2–10 | `key` is a capital letter `A`–`J` and is the option's identity. `text` is Markdown with `$…$` LaTeX and `\ce{}`, rendered like question text; it can be empty when `image` is given. |
| `options[].image` | string, optional | A relative, authenticated image URL (the same figure-crop URLs exam figures already use). Shown in place of, or under, `text`. |
| `multiple` | bool | `false`: single best answer (radio buttons). `true`: select all that apply (checkboxes). True/false questions are single answer with two options, `True` and `False`. |
| `shuffle` | bool | Whether the order was shuffled for this attempt. Informational. |
| `display_order` | list of keys | **Show the options in this order.** The server shuffles per attempt when the question allows it (never when an option says "all/none/both of the above" or refers to another option), and keeps the same order for the same attempt. |
| `instructions` | string | Short line to show above the options ("Choose one answer.", "Select all that apply.", "Choose true or false."). |
| `group` | string | Non-empty when several questions share one stem, for example `"Questions 5–7"`. The shared stem itself is already at the start of `question_text`; show `group` as a small caption. |
| `penalty` | number | Marks taken off for a wrong selection when the paper says so (negative marking), for example `0.25`. `0` when there is none. Show it as a warning: "Wrong answers lose 0.25 marks." |

**Labels.** Show each option with a letter by its position in `display_order` (first shown is "A", and so on), but always
send the option's own `key`. Feedback names options by their text, not by letter, so it reads correctly either way.

**The correct answer is never in the form.** It stays on the server until the answer is marked.

A choice form is usually followed by a `text` form. Treat that text box as optional working ("Working or reason
(optional)"), collapsed by default. A question can have a choice form on some parts and other forms on others.

## 2. Sending an answer

An answer is still one piece of text. A choice is written on its own first line:

```
Choice: B
```

Select-all-that-apply sends the keys in alphabetical order, separated by a comma and a space:

```
Choice: A, C
```

Optional working follows after a blank line:

```
Choice: B

Momentum is conserved, so 2 × 3 = 1.5 v.
```

Where it goes is unchanged:

- Review: `POST /review-questions/{id}/answers` with `{"answer": "Choice: B", "confidence": 4}`.
- Exam, a question without parts: `PUT /exams/{exam_id}/answers/{question_id}` with `{"answer": "Choice: B", "revision": 0, "scan_revision": 0}`.
- Exam, a question with parts: the existing parts document, `{"answer": "{\"parts\":{\"(a)\":\"Choice: B\",\"(b)\":\"Choice: A, C\"}}", …}`.
- Rapid: `POST /rapid/{exam_id}/next` and `/end` with `{"answer": "Choice: B", …}` as for any rapid answer.

To show a saved answer again, read the `Choice:` line and pre-select those keys. A missing or unreadable `Choice:` line
means nothing was chosen. The server also accepts a bare letter (`B`, `b`, `(b)`, `B.`) as the whole answer, so a
client that ignores the form still works.

## 3. Marking results

Marking a question whose every answerable part is multiple choice is deterministic: it uses the stored answer key, makes
no model call, and returns at once. Questions that mix choice parts with written parts are marked by the AI marker, which
is given the answer key for the choice parts.

### Review

`POST /review-questions/{id}/answers` returns the usual fields plus `choice_result`:

```json
{
  "correct": false,
  "outcome": "incorrect",
  "feedback": "The answer is 4.0 m s⁻¹. You chose 2.0 m s⁻¹, which forgets to double the speed …",
  "choice_result": {
    "chosen": ["A"],
    "correct_keys": ["B"],
    "options": [
      {"key": "A", "text": "$2.0\\ \\text{m s}^{-1}$", "correct": false, "chosen": true,  "explanation": "This halves the speed instead of doubling it."},
      {"key": "B", "text": "$4.0\\ \\text{m s}^{-1}$", "correct": true,  "chosen": false, "explanation": "Momentum is conserved: 2 × 3 = 1.5 v, so v = 4.0 m s⁻¹."},
      {"key": "C", "text": "", "image": "/resources/…", "correct": false, "chosen": false, "explanation": "…"},
      {"key": "D", "text": "None of the above", "correct": false, "chosen": false, "explanation": "B is correct, so this is not."}
    ],
    "marks_awarded": 0,
    "marks_available": 1,
    "penalty_applied": 0,
    "net_marks": 0,
    "marked_by": "answer-key",
    "key_source": "ai"
  }
}
```

- `correct` is `true` only when exactly the right set was chosen. A review answer never gets part credit.
- `explanation` says why that option is right or wrong; it can be empty for an option the paper's guide does not explain.
- `key_source` is `"official"` (from the paper's own answer key or marking guide), `"ai"` (written by the AI, check it) or
  `"none"` (no key; then the answer is marked by the AI marker as before and `choice_result` is absent).

### Exam and rapid

`POST /exams/{exam_id}/answers/{question_id}/feedback` returns the usual `Feedback` fields (`marks_awarded` stays a
non-negative integer, `outcome`, `feedback`, `evidence` is `[]`, `missing`, `confidence` is `1`), plus:

```json
{
  "marked_by": "answer-key",
  "choice_results": {"": { …same shape as choice_result above… }},
  "net_marks": 0.75,
  "net_marks_available": 2.5,
  "second_review": null,
  "disagreement": false
}
```

- `choice_results` is keyed by part label like `answer_forms` (`""` for a question without parts).
- `net_marks` (a number, possibly fractional or negative) is the marks earned at the paper's printed value minus negative
  marking; `net_marks_available` is the printed value. They differ from the integer `marks_awarded`/`marks_available` when a
  question is printed as worth a fraction (2.5 marks) or the paper states negative marking. `marks_awarded` never goes below 0.
  Show `net_marks`/`net_marks_available` when present.
- Select-all-that-apply in an exam gets part marks only when the paper's guide says so; otherwise all-or-nothing.
- There is no second marker for answer-key marking (`second_review` is `null`).

`GET /exams/{exam_id}/marks` adds `net_marks_awarded` (the paper total after negative marking, never below 0) and
`net_marks_available` beside `marks_awarded`/`marks_available`.

Exam questions from an imported paper also carry (additive, `GET /exams/{id}` → `questions[]`): `paper_title` (the
imported exam or test's name, `null` for NCEA papers), `guide_source` (`"official"`, `"ai"` when the marking guide was
written by AI because none was uploaded, `"mixed"`, or `""` for NCEA schedules and AI practice), `marks_exact` (printed marks
when not whole, else `null`) and `outcome_codes` (learning outcomes the question assesses). Show "AI-written marking guide"
when `guide_source` is `"ai"` or `"mixed"`.

`GET /exams/{exam_id}/answers/{question_id}/feedback` returns the stored result in `marks[]` with the same extra fields.

## 4. Where the questions come from

- **Imported past papers** (NCEA and university): options, the correct option from the answer key or marking guide when one
  was uploaded (`key_source: "official"`), otherwise an AI-written key (`key_source: "ai"`, shown as "AI-written answer").
- **AI practice** (practice exams, rapid questions, revision packs): the model writes the options, the key and an
  explanation per option (`key_source: "ai"`). A paper is "assessed by multiple choice" when its coming test or exam says so
  (assessments carry `question_format`: `"multiple_choice"`, `"mixed"`, `"written"` or `""`, set in Plan or read from the
  outline) or, failing that, when most of its imported past-paper questions are multiple choice. Other papers, and every NCEA
  subject, get written practice.
- **Spaced review** asks an idea as free recall first and uses multiple choice for exam-style practice (research A.2:
  recognition builds weaker long-term memory than recall). Review questions written from lessons stay free recall. A missed
  multiple-choice exam question comes back in review as a written question when its stem stands on its own ("Name the
  volatile storage..."), and as multiple choice only when the stem needs its options ("Which of the following is FALSE?").
  Revision packs keep each section's first question a written check and use multiple choice for the later exam-style ones.

### Other additive fields on review items

- `variant: true` and `variant_id` on a review item mean the question is shown as a fresh version (new numbers, same method)
  of a procedure question being reviewed again. Show "A new version of this question, written by AI". Answer it as usual;
  the answer response then also has `variant: true` and the `expected_answer` it was marked against.
- `GET /review-calibration` (optional `days`, `topic_id`): `levels` (for confidence 1-5: `answers`, `correct`,
  `correct_rate` or `null`), `marked_answers`, `summary` (one sentence), `topics[]` and `confident_misses[]`
  (`question_id`, `question`, `confidence`, `answered_at`, `topic`, `concept`).

## 5. Lessons

Lesson practice is lesson text, not stored questions. A lesson can contain a multiple-choice block in its Markdown:

````
```choice
Which change increases the rate of this reaction?
A. Lowering the temperature
B. Adding a catalyst *
C. Using larger lumps of solid
---
B: A catalyst gives an alternative pathway with a lower activation energy.
A: Lower temperature means fewer collisions with enough energy.
C: Larger lumps have less surface area, so fewer collisions.
```
````

The option marked ` *` is correct (several for select all that apply); lines after `---` explain each option. Clients
that do not render the block show it as a code block; the web app shows selectable options and checks the choice on the
device, with no model call. The block is part of the lesson text, so the key is visible to anyone who reads the source;
that is acceptable for lesson practice, which is not marked.

## 6. Importing a past exam or test (university papers)

All additive; NCEA papers are still paired from the Library by their NZQA file names.

- `POST /subjects/{subject_id}/exam-imports` (multipart): `paper` (PDF, .docx, .txt, .md, PNG or JPEG, up to 30 MiB), optional
  `guide` (marking guide, model answers or answer key), `title`, `year`, `kind` (`exam`, `test`, `quiz`), optional `topic_id`
  (default: a topic "Past exams and tests" in that subject). Returns `202 {"id", "status": "reading", "topic_id"}`. A paper
  already imported returns 409.
- `GET /subjects/{subject_id}/exam-imports` and `GET /exam-imports/{id}`: `status` (`reading`, `imported`,
  `needs_attention`, `failed`), `stage` (progress text while reading), `error`, `warnings[]` (things to check),
  `question_count`, `choice_count`, `total_marks`, `guide` (`official`, `ai`, `mixed`) and `guide_note` (one sentence to
  show). `GET /exam-imports/{id}` adds `questions[]`. Poll every few seconds while `reading`; a paper takes one to three minutes.
- `POST /exam-imports/{id}/retry` reads it again; `DELETE /exam-imports/{id}` removes it and its questions (409 when an
  exam already used them).
- The imported paper is then an "original" paper of its topic: `GET /exam-papers?topic_id=` lists it with `title`, `guide`
  and `kind`, and `POST /exams/start` with `mode: "original"` sits it as for NCEA papers.
