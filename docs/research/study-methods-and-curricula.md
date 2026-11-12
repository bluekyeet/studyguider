# Study methods and curricula: research for StudyGuider

Written 2026-11-12 by the research sub-agent. Nothing in the application code was changed. This file is uncommitted.

**How to read the labels.** Every factual claim has a URL next to it.
- **[P]** = read in a primary source (the paper's PubMed/DOI record or full text, or the official NZQA / Ministry / AUT / UoA page or PDF), during this research.
- **[S]** = taken from a secondary summary (a search-result excerpt, a press release, a school or party website). Treat as likely, not proven.
- **[U]** = could not be confirmed. Do not build on it without checking.
- **Judgement** = my recommendation, not a finding. Part D separates evidence-backed items from judgement.

Several publisher sites (SAGE, APA, Springer) refused automated fetches. Where I could not open the paper itself I say so, and I relied on the PubMed abstract or on a named secondary source.

**Facts that expire.** NCEA is being replaced and both universities publish new dates and systems each year. Each university fact below states its year.

---

## 0. What the app does today (read from the repo, 2026-11-12)

These points shape every recommendation.

| Area | What it does now | What it lacks | Where |
|---|---|---|---|
| Review (spaced repetition) | Each completed lesson produces 3 short questions (1-5 accepted). A question gets an interval from a rule: wrong → 1 day; right with confidence ≤2 → 2 days; conf 3 → same interval; conf 4 → ×2; conf 5 → ×3. | **Each question is asked once.** `fresh_due` only returns questions with no answer, so after the first answer a question never returns to "Due now" (it can still be answered early from "All questions"). `interval_days`/`next_due` are computed but never used to re-ask. The interval ignores how long the gap actually was (no retrievability), and ignores the exam date. Near-duplicate questions are deliberately suppressed (`SIMILAR = 0.85`), which works against repeating a concept in different words. | `server/reviews.py:48` (`next_interval`), `:114` (`fresh_due`), `:262` (`answer_question`) |
| Mastery and "estimated grade" | Per-question mastery = `0.75*old + 0.25` if right, `0.75*old` if wrong. Topic mastery = mean over all the topic's questions, including never-answered ones (0). Home shows Not achieved / Achieved / Merit / Excellence at 40/60/80%. | Not a probability of recall; unanswered questions drag the topic score down; the bands are not tied to any NZQA cut score. | `reviews.py:310-318`, `:137` |
| Lessons | One new lesson per active topic per night (NZ time), written from the learner's uploaded sources, reviewed by a second model. Structure: goal, prior-knowledge check, small explanation chunks, one worked example, 3-5 "Your Turn" questions, common mistakes, summary. Revisits up to 12 weak or due review items. A free-text "teaching style" is injected into every prompt. | No pre-questions, no faded worked examples, no interleaving across topics, no use of assessment dates, no distinction between facts / procedures / concepts / writing. Goal text is fixed "Ace the external exam". Content is topic-blocked (one topic's lesson per day). | `server/lessons.py:314-379`, `scheduler.py:172` |
| Exams and rapid practice | Real past-paper questions parsed with schedules, AI marking against the schedule, grade cut scores imported from schedules (`exam_grade_rules`), rapid sessions with feedback withheld until the end, revision packs from mistakes ("a wrong answer returns tomorrow"). | Strong on NCEA external practice. Cut scores exist but are not used in the Home grade estimate. | `server/exams.py:98-143`, `rapid.py`, `docs/website-functions.md` |
| Data model | `subjects(level 1..3 CHECK)` → `topics` → `resources`; `standards(number integer PK)` linked to topics; `courses(topic, goal, active)` (a "course" here means "topic being studied"); `exam_questions.standard_number NOT NULL`. | No programme, no term/semester, no assessment events (date, weight, type), no learning outcomes, no concept-level memory state. NCEA-only by construction (level check, integer standard number). | `server/app.py:87-95`, `lessons.py:68`, `exams.py:98` |

Note the naming clash for the engineer: in this repo `courses` means "a topic the student switched on". Universities use "course"/"paper" for a 15-point unit. Rename one of them in the new design.

---

## Part A: learning science for long-term retention

### A.1 Summary table

Strength is my reading of the evidence, stated per claim.

| Technique | Evidence | Main sources |
|---|---|---|
| Retrieval practice (testing effect) | **Strong**, lab and classroom | Meta-analyses below |
| Spacing | **Strong**, including over months | Cepeda 2006/2008, Bahrick 1993 |
| Successive relearning (retrieval + spacing + criterion) | **Moderate to strong** in real courses; fewer studies | Rawson et al. 2013 |
| Interleaving | **Moderate**, material-dependent (good for maths and visual categories, bad for words) | Brunmair & Richter 2019; Rohrer 2020 |
| Worked examples, then fading | **Moderate to strong** for novices in maths-like procedures | Sweller & Cooper 1985; Barbieri 2023; Kalyuga 2003 |
| Self-explanation / elaborative interrogation | **Moderate** | Dunlosky 2013; Bisra 2018 |
| Pre-testing | **Moderate**, mostly text passages | Richland 2009; Pan & Sana 2021 |
| Corrective feedback after retrieval | **Strong** (feedback is a moderator of the testing effect) | Yang 2021; Butler & Roediger 2008 |
| Confidence calibration | **Moderate**, mostly descriptive | Bjork, Dunlosky & Kornell 2013 |
| Overlearning (massing after mastery) | **Strong evidence that it is inefficient for long retention** | Rohrer et al. 2005 |
| Sleep | **Moderate**, effect sizes small, publication bias | Newbury 2021 |
| Rereading, highlighting, summarising, cramming, learning styles | **Low utility / unsupported** | Dunlosky 2013; Pashler 2008 |

### A.2 Retrieval practice (testing effect)

- Students who took recall tests on prose beat students who restudied once the final test was 2 days or 1 week away, even though restudying left them feeling more confident. Restudy won only at a 5-minute test. [P] https://pubmed.ncbi.nlm.nih.gov/16507066/ (Roediger & Karpicke 2006).
- After a vocabulary item had been recalled once, further studying added nothing to delayed recall, while further testing added a lot. Students' predictions of their own performance were uncorrelated with how they actually did. [P] https://pubmed.ncbi.nlm.nih.gov/18276894/ (Karpicke & Roediger 2008, *Science*).
- Meta-analysis: free-recall type tests give larger benefits than recognition tests, supporting "effortful retrieval". [P] https://pubmed.ncbi.nlm.nih.gov/25150680/ (Rowland 2014).
- Classroom meta-analysis: 222 studies, 48,478 students; quizzing raised achievement by g = 0.499. Moderators include corrective feedback, number of repetitions, and whether the quiz format matches the final test. [P] https://pubmed.ncbi.nlm.nih.gov/33683913/ (Yang et al. 2021).
- Practice tests beat restudy and other comparison conditions across studies. [P] https://doi.org/10.3102/0034654316689306 (Adesope 2017; abstract read via Crossref/Semantic Scholar).
- 50 classroom experiments: 57% showed medium or large benefits; only 6% were outside WEIRD countries. [P, preprint] https://doi.org/10.31234/osf.io/xe9kv (Agarwal et al.).
- Caution: a 10-technique meta-analysis (242 studies, mean effect 0.56) found most outcomes were surface or factual and urged care applying results to deeper outcomes; effects were larger for lower-ability students. [P] https://doi.org/10.3389/feduc.2021.581216 (Donoghue & Hattie 2021).

**Implication.** Every study activity that can be a retrieval attempt should be one (write the answer before seeing it). Re-reading a lesson should not count as study.

### A.3 Spacing: how far apart, as a function of when you need the knowledge

**Cepeda et al. 2008** is the key quantitative source. More than 1,350 people learned facts, had one review after a gap of 0 to 3.5 months, and were tested up to a year later. The best gap rose with the retention interval, but as a share of it fell from about 20-40% of a 1-week delay to about 5-10% of a 1-year delay. [P] https://pubmed.ncbi.nlm.nih.gov/19076480/

From the full text [P] https://www.evullab.org/pdf/CepedaVulRohrerWixtedPashler-PS-2008.pdf :

| Time from review to test (retention interval, RI) | Best gap tested | Interpolated best gap | As % of RI |
|---|---|---|---|
| 7 days | 1 day | ~3 days | 43% |
| 35 days | 11 days | ~8 days | 23% |
| 70 days | 21 days | ~12 days | 17% |
| 350 days | 21 days | ~27 days | 8% |

Using the best gap instead of no gap (the "zero-day gap", i.e. restudy straight away) improved final recall by 10%, 59%, 111% and 77% at the four intervals.

**Cepeda et al. 2006** (839 assessments in 317 experiments): the best gap grows with retention interval. [P] https://pubmed.ncbi.nlm.nih.gov/16719566/

**Limits you must not paper over:** these were trivia/fact items, one learning episode and one review (not a multi-review programme), and adult volunteers. Treat the table as a shape ("final review at roughly 5-25% of the time remaining"), not a law.

**Spacing over years.** Four subjects (the authors) learned 300 foreign-vocabulary pairs. 13 relearning sessions spaced 56 days apart gave retention comparable to 26 sessions spaced 14 days apart; the benefit of extra sessions was independent of the benefit of longer gaps. Retention was tested 1-5 years later. Very small sample (n = 4), but a rare multi-year test. [P] https://www.Gwern.net/doc/psychology/spaced-repetition/1993-bahrick.pdf (DOI 10.1111/j.1467-9280.1993.tb00571.x).

**Cramming vs spacing.** Spacing beat cramming for 90% of participants, yet 72% believed massing had worked better after the first session. [P] https://doi.org/10.1002/acp.1537 (Kornell 2009).

**Expanding vs uniform intervals.** Expanding schedules gave a short-term benefit (10 minutes), but equally spaced retrieval gave better retention 2 days later; the factor that mattered was delaying the first retrieval so it is hard. Expanding the interval had little effect on long-term retention in three experiments. [P] https://pubmed.ncbi.nlm.nih.gov/17576148/ (Karpicke & Roediger 2007). Implication: do not agonise over "×2 vs ×2.5". Make the first retrieval after learning a real effort (hours to a day, not minutes), and keep gaps growing.

**Personalised review.** In a semester-long middle-school course, a model-based personalised review schedule gave a 16.5% boost on a cumulative exam over massed study and 10.0% over a one-size-fits-all spaced schedule. [P] https://pubmed.ncbi.nlm.nih.gov/24444515/ (Lindsey et al. 2014).

**Reviews of spacing and policy.** Carpenter, Pan & Butler 2022 (*Nature Reviews Psychology*) and Kang 2016 summarise spacing and retrieval for practitioners. I confirmed the references but could not read the text. https://doi.org/10.1038/s44159-022-00089-1 and https://doi.org/10.1177/2372732215624708 [U on specific numbers].

### A.4 Successive relearning

Practice items to a criterion (answered correctly), then repeat across spaced sessions, relearning those missed. In a real introductory psychology course, successive relearning raised exam performance by about a letter grade (C to B) over spaced restudy and baseline, and students retained relatively high knowledge 24 days after the exam versus poor recall 3 days after for business-as-usual study. [S] https://doi.org/10.1007/s10648-013-9240-4 (Rawson, Dunlosky & Sciartelli 2013; summary via search, paper not opened). The same authors' 2011 *J Exp Psychol: General* paper asks "how much is enough?" (criterion level); I could not read its abstract. https://doi.org/10.1037/a0023956 [U on criterion numbers].

### A.5 Modern schedulers: SM-2 and FSRS

**SM-2** (SuperMemo, 1987) is the algorithm behind most simple flashcard apps. [P] https://super-memory.com/english/ol/sm2.htm
- Items start with E-Factor EF = 2.5. Intervals: I(1) = 1 day, I(2) = 6 days, I(n) = I(n−1) × EF.
- After each repetition, grade q from 0 to 5; `EF' = EF + (0.1 − (5−q)(0.08 + (5−q)·0.02))`, floor 1.3. If q < 3, restart the interval sequence (EF unchanged).
- Weakness for this app: intervals depend only on the previous interval and a fixed multiplier, not on how long the gap really was or how hard the item is; no target retention. Today's `next_interval` is a cruder cousin of this.

**FSRS** (Free Spaced Repetition Scheduler) models each item with three variables. It descends from MaiMemo's DHP model, itself a variant of the DSR (Difficulty, Stability, Retrievability) model. [P] https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm ; papers: Ye, Su & Cao, KDD 2022, https://dblp1.uni-trier.de/rec/conf/kdd/YeSC22.html and the IEEE TKDE extension "Optimizing Spaced Repetition Schedule by Capturing the Dynamics of Memory" (listed at https://www.aminer.cn/pub/648cceffd68f896efa7deb92/optimizing-spaced-repetition-schedule-by-capturing-the-dynamics-of-memory ).

- **R, retrievability:** probability of recall now. **S, stability:** days for R to fall from 100% to 90%. **D, difficulty:** 1 to 10. **G, grade:** 1 Again, 2 Hard, 3 Good, 4 Easy. **desired retention** `r`: the R at which you want the next review to fall due.

The latest formulas documented on that wiki are **FSRS-6 (21 parameters)**. The page lists only the *changes* per version, so the full set below combines FSRS-6 with the unchanged FSRS-5/4.5 formulas on the same page. [P] same URL. (The benchmark README also lists a newer "FSRS-7" with 34 parameters; its formulas were not on the wiki page I read [U].)

```
Default weights w[0..20] (FSRS-6):
[0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722, 0.1666,
 0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014, 1.8729, 0.5425, 0.0912, 0.0658, 0.1542]

Forgetting curve (FSRS-6):  R(t,S) = (1 + factor * t/S) ^ (-w20),  factor = 0.9^(-1/w20) - 1   (so R(S,S) = 0.9)
Interval for desired retention r:  I(r,S) = S / factor * ( r^(-1/w20) - 1 )     (derived from the curve; equals S when r = 0.9)

First review:
  S0(G) = w[G-1]
  D0(G) = w4 - exp(w5 * (G-1)) + 1           (clamp D to [1,10])

After a later review with grade G (the wiki does not state the order; as I recall, the reference libraries compute the new S from the pre-review D, S and R, then update D. [U] Check the `fsrs` package source):
  dD    = -w6 * (G - 3)
  D'    = D + dD * (10 - D) / 9              (linear damping)
  D''   = w7 * D0(4) + (1 - w7) * D'         (mean reversion toward D0(4)); clamp [1,10]

Stability after success (G = 2, 3, 4):
  S'r = S * ( exp(w8) * (11 - D) * S^(-w9) * (exp(w10 * (1 - R)) - 1) * [w15 if G=2] * [w16 if G=4] + 1 )

Stability after a lapse (G = 1):
  S'f = w11 * D^(-w12) * ((S + 1)^w13 - 1) * exp(w14 * (1 - R))

Same-day (short-term) review:
  S' = S * exp(w17 * (G - 3 + w18)) * S^(-w19)       (FSRS-6; keep S' >= S when G >= 2)
```

Properties the wiki states for the recall update: the stability gain is larger when D is low, smaller when S is already high, and larger when R was lower at review time (a spacing effect); it is always ≥ 1 for a successful review. [P] same URL.

**Computed from those formulas by me** (a sanity check for tests, not from the wiki): factor = 0.9803. Interval as a multiple of S: r = 0.70 → 9.29×; 0.80 → 3.32×; 0.85 → 1.91×; 0.90 → 1.00×; 0.95 → 0.40×; 0.97 → 0.22×. First-review stability for Again/Hard/Good/Easy = 0.212 / 1.29 / 2.31 / 8.30 days. D0 = 6.41 / 5.11 / 2.12 / (−4.77 → clamped to 1). An item rated Good first and then Good on time at r = 0.9 each time reviews on days ≈ 2, 14, 64, 238, 766 (my simulation used the updated D in the stability step, which changes little because D stays near 2.1; the point is that intervals explode for easy items, so you need a maximum-interval cap).

**Known gaps in the wiki page** [U]: it does not state clamping rules beyond D ∈ [1,10] (reference implementations also keep S'f from exceeding S and enforce S' ≥ S for passes; check the library source), nor the fuzz applied to intervals.

**Evidence for FSRS over SM-2.** The open benchmark (about 727 million Anki reviews, ~10,000 users, evaluated by predicting future recall on time-split data) ranks FSRS-6 well above older FSRS versions and FSRS-6 has the lower log-loss; the maintainers' ABC page says FSRS needs 20-30% fewer reviews than SM-2 for equal retention, **from simulation**. [P] https://github.com/open-spaced-repetition/srs-benchmark and https://github.com/open-spaced-repetition/awesome-fsrs/wiki/ABC-of-FSRS . It also says: use default weights until there are enough reviews; desired retention 70-97% is "reasonable"; higher retention means more reviews. [P] same ABC URL.

**Caveats.** (1) Benchmarks are on self-graded Anki flashcards, not AI-marked school answers; no evidence yet that the weights transfer. (2) The 4-grade input is user-reported ease. Here grade would be derived (A.5 mapping in Part D). (3) Only one learner, so per-user weight optimisation has little data; defaults are the realistic option.

**Libraries I verified exist:** Python `fsrs` 6.3.2 (21 weights, defaults `desired_retention=0.9`, learning steps 1 min and 10 min, `maximum_interval=36500`, fuzzing on) https://pypi.org/project/fsrs/ and https://github.com/open-spaced-repetition/py-fsrs ; TypeScript `ts-fsrs` 6.0.0 https://www.npmjs.com/package/ts-fsrs [P: versions read from the registries on 2026-11-12].

**Half-life regression (Duolingo).** Settles & Meeder 2016 trained a half-life model for language learning; I confirmed the reference only. https://doi.org/10.18653/v1/p16-1174 [U on details]. Not needed if FSRS is adopted.

### A.6 Interleaving

- Meta-analysis (59 studies): moderate overall effect g = 0.42; **maths tasks g = 0.34**; paintings/visual categories g = 0.67; **words g = −0.39 (blocking was better)**; texts ambiguous. Interleaving helps most when categories are similar to each other and items within a category are dissimilar. [P] https://pubmed.ncbi.nlm.nih.gov/31556629/ (Brunmair & Richter 2019).
- Randomised trial: 54 seventh-grade maths classes did interleaved or blocked homework for 4 months, then both did an interleaved review; an unannounced test a month later: **61% vs 38%, d = 0.83**. Teachers needed no training. [P] https://doi.org/10.1037/edu0000367 (Rohrer et al. 2020; abstract read via Semantic Scholar).
- Learners usually believe blocking works better than interleaving. [P] https://pubmed.ncbi.nlm.nih.gov/31900048/ (finding replicated in a study reusing Kornell & Bjork's task). Expect students to dislike interleaved sets; that is not evidence they work worse.

**Implication.** Interleave problem *types* in maths/physics/chemistry practice, after an initial blocked introduction; do not interleave vocabulary or definitions.

### A.7 Worked examples, fading, expertise reversal

- Worked examples substitute for problem solving in algebra learning for novices (Sweller & Cooper 1985): https://doi.org/10.1207/s1532690xci0201_3 [U on the numbers].
- Meta-analysis of the worked-examples effect on maths performance: medium, g = 0.48; correct-only examples beat incorrect or mixed ones; pairing examples with self-explanation prompts was associated with *lower* performance than examples alone. [S] https://doi.org/10.1007/s10648-023-09745-1 (Barbieri et al. 2023; moderator details not verified, study count differs between summaries: 43 vs 55).
- **Expertise reversal:** instruction that helps novices (full worked solutions) becomes redundant or harmful for more expert learners, so examples should fade into problems as skill grows. https://doi.org/10.1207/s15326985ep3801_4 (Kalyuga et al. 2003) [U on the numbers; the principle is well known].

### A.8 Elaboration and self-explanation

Self-explanation prompts: 64 reports, 69 effect sizes, weighted mean g = 0.55, mostly undergraduates. [S] https://doi.org/10.1007/s10648-018-9434-x (Bisra et al. 2018). Dunlosky et al. rate elaborative interrogation and self-explanation "moderate utility". [S] https://www.psychologicalscience.org/news/releases/which-study-strategies-make-the-grade.html

### A.9 Pre-testing

Asking questions before study, even when learners cannot answer, beat extended study time on later tests (analysis restricted to items answered wrongly on the pretest). [P] https://pubmed.ncbi.nlm.nih.gov/19751074/ (Richland, Kornell & Kao 2009). Five experiments (n = 1,573) found pretesting about as good as, or better than, post-testing on 5-minute and 48-hour tests of text passages, with or without feedback. [P] https://pubmed.ncbi.nlm.nih.gov/33793291/ (Pan & Sana 2021). Evidence is mostly text passages and short delays. Not tested for multi-step problem solving [U].

### A.10 Feedback and learning from errors

- Immediate or delayed feedback after multiple-choice tests both increased correct answers and reduced lure intrusions on a later cued-recall test compared with no feedback. [P] https://pubmed.ncbi.nlm.nih.gov/18491500/ (Butler & Roediger 2008).
- Errors followed by corrective feedback help learning; **errors made with high confidence are corrected more readily than low-confidence errors**; feedback that analyses the reasoning matters. [P] https://pubmed.ncbi.nlm.nih.gov/27648988/ (Metcalfe 2017).
- Feedback is among the strongest influences but its type matters (task, process, self-regulation; praise is weak). [P] https://doi.org/10.3102/003465430298487 (Hattie & Timperley 2007).
- Distinguish learning from performance: conditions that make practice feel fluent can reduce later retention. [P] https://pubmed.ncbi.nlm.nih.gov/25910388/ (Soderstrom & Bjork 2015).

### A.11 Calibration and metacognition

People often misjudge how well they have learned and rely on fluency; students did not know repeated testing beat restudying (see A.2). [P] https://pubmed.ncbi.nlm.nih.gov/23020639/ (Bjork, Dunlosky & Kornell 2013). Also Dunlosky & Rawson 2012 on overconfidence and underachievement (reference confirmed, not read): https://doi.org/10.1016/j.learninstruc.2011.08.003 [U]. Delaying judgements of learning improves their accuracy (meta-analysis, reference confirmed, not read): https://doi.org/10.1037/a0021705 [U].

### A.12 Overlearning

After one perfect recall, further study in the same session ("overlearning") greatly helped 1-week recall but the benefit shrank sharply by later tests (up to 9 weeks); 218 students. [P] https://doi.org/10.1002/acp.1083 (Rohrer et al. 2005). Spend that effort on later sessions instead.

### A.13 Sleep and session length

- Sleep after learning supports consolidation of memory (mechanism review). [P] https://pubmed.ncbi.nlm.nih.gov/20046194/ (Diekelmann & Born 2010).
- Meta-analyses of total sleep deprivation: after learning g = 0.277; before learning g = 0.621; the authors flag publication bias and very low power in most studies. [P] https://pubmed.ncbi.nlm.nih.gov/35238586/ (Newbury et al. 2021). Effects come from at least one full night of deprivation, not ordinary short sleep.
- Session length: I found **no solid primary evidence for an optimal session length**. The evidence is for distributing practice across days (A.3). Anything I say about 25-50 minute blocks is judgement.

### A.14 What does not work well (and the evidence)

Dunlosky et al. 2013 reviewed ten techniques. The monograph is [P as a record] https://pubmed.ncbi.nlm.nih.gov/26173288/ ; the ratings below come from the publisher's summary [S] https://www.psychologicalscience.org/news/releases/which-study-strategies-make-the-grade.html :
- **High utility:** practice testing, distributed practice.
- **Moderate:** elaborative interrogation, self-explanation, interleaved practice.
- **Low:** summarisation, highlighting/underlining, rereading, keyword mnemonic, imagery for text.

Later meta-analysis agrees distributed practice and practice testing were the most effective, and underlining and summarisation the least (but still positive). [P] https://doi.org/10.3389/feduc.2021.581216 . Caveat in A.2.

**Learning styles.** The matching hypothesis (teach each student in their preferred modality) lacks the experimental evidence a credible validation needs. [P, abstract truncated in my fetch] https://pubmed.ncbi.nlm.nih.gov/26162104/ (Pashler et al. 2008). **This matters for the app**: the Settings "Teaching style" box (`server/styles.py`) injects free text into every lesson prompt. Keep it for tone, language and pace; do not let it steer by "visual/auditory learner".

**Six strategies with strong support**, for teachers: spaced practice, interleaving, retrieval practice, elaboration, concrete examples, dual coding. [P] https://doi.org/10.1186/s41235-017-0087-y (Weinstein, Madan & Sumeracki 2018).

### A.15 How this differs by type of material

| Material | Best-supported approach | Evidence level | What changes in the app |
|---|---|---|---|
| **Facts and definitions** (vocabulary, formulae to recall, dates, reaction types) | Spaced retrieval of cue → answer, free recall preferred over recognition (Rowland 2014); corrective feedback; successive relearning to criterion. Blocking is not worse than interleaving for words (Brunmair & Richter: words g = −0.39 for interleaving). | Strong | Flashcard-like items, fast, auto-marked or lightly AI-marked, FSRS on each item. |
| **Procedures** (maths, physics, chemistry calculations, programming) | Worked example → completion problems → full problems for novices (fade as skill grows); spaced and interleaved *problem* practice (Rohrer 2020 RCT; Hopkins 2016 spaced retrieval in college maths: https://doi.org/10.1007/s10648-015-9349-8, title read only); retrieve the *method*, not the previous answer. | Moderate to strong for maths; **limited for programming** (see below) | A review item must be a *skill* with generated variants (new numbers/contexts), otherwise the student recalls the old answer. Interleave skill types in mixed sets. |
| **Conceptual understanding** (why, cause and effect, models) | Retrieval of explanations in own words, self-explanation prompts, elaborative interrogation ("why is this true?"), pre-questions, contrasting cases. Retrieval practice beat elaborative study with concept mapping on later tests. Effects measured on surface outcomes more than deep ones, so be cautious (Donoghue & Hattie 2021). | Moderate | Short open questions marked against a rubric of *linked ideas*, not keywords; feedback includes the missing link. |
| **Extended writing** (essays, reports, lab reports) | I found no strong retrieval-practice literature for whole essays. What is supported is explicit strategy instruction, planning and revising with feedback, and feedback on specific features (Hattie & Timperley 2007; Graham & Perin 2007 meta-analysis of writing instruction, reference only, effect sizes not read: https://doi.org/10.1037/0022-0663.99.3.445 [U on numbers]). Retrieval applies to the *ingredients* (argument structure, evidence, quotations, definitions), not the whole essay. | Limited and mostly judgement | Do not schedule essays through FSRS. Schedule drafting/feedback milestones against due dates; use retrieval items for the content that goes into the essay. |

**Programming evidence.** I found small quasi-experiments and course case studies of spaced/retrieval practice in introductory programming, and a 2024 nine-course STEM study stating that evidence on spacing quizzes is mixed. I did not verify effect sizes or random assignment. [S] https://stemeducationjournal.springeropen.com/articles/10.1186/s40594-024-00468-5 . Treat programming as "procedures" with a judgement-level confidence.

### A.16 Keeping knowledge after the exam, and carrying it into university

- Across general and medical education, about two-thirds to three-quarters of knowledge is retained after one year, falling to a little below half the year after. [P] https://pubmed.ncbi.nlm.nih.gov/18274876/ (Custers 2010 review).
- People who learned high-school algebra and geometry and took **no** later maths dropped to near chance over decades; those who took college maths at or above calculus level lost very little over 50 years. 1,726 people aged 19-84. [S] https://doi.org/10.1037/0096-3445.120.1.20 (Bahrick & Hall 1991; via search summaries, abstract not opened; the calculus result may be confounded by STEM students practising algebra). Reading: retention comes from *continued use*, which is exactly what a school-to-university bridge should provide.
- Summer vacation loss is about one month of grade-equivalent achievement in a meta-analysis, larger for maths (computation). [S] https://doi.org/10.3102/00346543066003227 (Cooper et al. 1996). Relevance: NCEA external exams end 2026-12-04 and AUT Semester 1 classes begin 2027-02-22 (UoA 2027-03-01), an ~12-week gap.
- Long-gap spacing works: multi-year retention of vocabulary with sessions spaced ~2 months apart (Bahrick 1993, A.3).
- **Judgement:** after an exam, keep the knowledge the next course will assume in a low-effort maintenance pool (target retention ~0.8-0.85, long intervals), and trigger a refresher about 2-3 weeks before the next course starts (Part D).

---

## Part B: NCEA

### B.1 Structure in 2026 [P unless marked]

- Three levels (1-3), usually Years 11-13. Standards are assessed internally by the school during the year, or externally by national exams at year's end. Grades N / A / M / E. Only A, M, E earn credits and Merit/Excellence earn no extra credits. https://www2.nzqa.govt.nz/ncea/about-ncea/
- Credits: 60 credits for each level (Level 1: 60 at any level; Level 2: 60 at Level 2 or 3; Level 3: 60 at Level 3), plus the 20-credit literacy and numeracy co-requisite (10 + 10), met once for all levels. https://tahatu.govt.nz/school-and-ncea/doing-ncea/how-ncea-works . **Conflict:** NZQA's rules documents still show "80 credit minimum" headings, so treat 60 as the current figure but check NZQA before stating it formally. [S] https://www2.nzqa.govt.nz/assets/About-us/Our-rules-fees-and-policies/NZQA-Rules/2026/Assessment-and-Examination-for-NCEA-and-New-Zealand-Scholarship-Rules-2026.pdf (known only from a search summary).
- Endorsements: certificate endorsement = 50 or more Merit/Excellence credits at that level; course endorsement = 14 or more Merit/Excellence credits in one subject in one year. https://tahatu.govt.nz/school-and-ncea/doing-ncea/how-ncea-works
- University Entrance: NCEA Level 3; 14 credits at Level 3 in each of 3 approved subjects; 10 literacy credits at Level 2+ (5 reading, 5 writing); 20 co-requisite literacy and numeracy credits (numeracy via unit standard 32406 or certain achievement standards). https://www2.nzqa.govt.nz/ncea/understanding-secondary-quals/university-entrance/ and https://tahatu.govt.nz/school-and-ncea/doing-ncea/how-ncea-works . That NZQA page still describes the UE review as current (2023-2025) while a 2024 search-result summary says it was paused until 2029 [S] https://www2.nzqa.govt.nz/ncea/understanding-secondary-quals/university-entrance/requirements-review/ ; treat the review status as [U].
- Co-requisite 2026 events: Literacy/Numeracy event 1 on 18-29 May and event 2 on 7-18 September; co-requisite results released 23 June / 14 October (Reading) and 20 July / 27 October (Writing, Numeracy). https://www2.nzqa.govt.nz/ncea/exam-timetable-and-key-assessment-dates/key-dates-for-secondary-assessment/ . Which routes count for the co-requisite in 2026 differs between sources [U]; use NZQA's co-requisite page when the app needs it.

### B.2 What is changing, with dates

The Ministry of Education's finalised plan (published 16 May 2026) [P] https://tahurangi.education.govt.nz/senior-secondary-quals-finalised and https://www.education.govt.nz/news/more-details-about-new-senior-secondary-qualifications :

- NCEA is replaced by two national qualifications: **NZCE (Year 12)** and **NZACE (Year 13)**, plus a **Foundational Award** (literacy and numeracy, benchmarked at Year 11) that students need in order to be awarded NZCE or NZACE.
- Timeline: **2028**: Foundational Award introduced, **NCEA Level 1 removed**, Year 11 curriculum required. **2029**: NZCE introduced (Year 12 curriculum required). **2030**: NZACE introduced (Year 13).
- Each subject: coursework plus at least one exam, with most students doing 3-4 assessments per subject per year; assessed on the whole subject rather than separate standards; national consistency. New **six-point A+ to E scale**; **C or above to pass a subject**.
- Award: at least 3 passed subjects at the year level plus the Foundational Award; certificates show the subject count (e.g. NZCE 4). Endorsements need at least 5 passed subjects, names and criteria still being finalised.
- Enrolment: at least 5 subjects each year in Years 12-13. From 2028 all Year 11 students take English or Te Reo Rangatira, maths or Pāngarau, science or Pūtaiao.
- Transition: students close to finishing NCEA can finish under transitional arrangements. Still to be finalised: reassessment, grade aggregation, transitional detail, and NZQA's review of University Entrance requirements.

**Which students are affected (my inference from the timeline, not stated as a table by the Ministry [U]):** a student in Year 11, 12 or 13 in 2026 completes NCEA. The first cohort to meet the new system is the one in Year 11 in 2028 (Year 9 in 2026), who then take NZCE in 2029 and NZACE in 2030. A Year 10 student in 2026 (Year 11 in 2027) still sits NCEA Level 1 in 2027 and Level 2 in 2028 (NZCE does not exist until 2029).

**History** [S unless noted]: the 2019-onward NCEA Change Programme was re-phased in April 2023 and again in April 2024 (full Level 1 and 2 by 2028, Level 3 by 2029) https://www.education.govt.nz/news/government-rephase-ncea-change-programme (search listing only; the page returned 404 to me) ; on 4 August 2025 the Government proposed replacing NCEA (proposal then: 5 subjects, pass 4; final: pass 3) https://www.1news.co.nz/2025/08/04/ncea-changes-what-you-need-to-know/ ; Cabinet confirmed on 26 March 2026 https://www.national.org.nz/news/20260326-hob-erica-stanford-government-confirms-new-senior-qualification . Opposition and union criticism exists; the plan could change after an election [U].

**Implication.** The data model must treat "NCEA" as one of several *assessment regimes* with a sunset, not as the base case. Level 1 content in the app has a limited life (last NCEA L1 assessments in 2027).

### B.3 How external exams are marked (the shape that practice must copy)

- NZQA uses **grade score marking** for all achievement standards with one external outcome. Each question gets one of eight scores: N1/N2 (Not Achieved; N0 for no evidence), A3/A4, M5/M6, E7/E8. Markers give one holistic score per question even when it has several parts, and work **top-down**: they look first for Excellence evidence, then Merit, then Achievement; a high-quality answer should not be marked down for a minor error. Question scores are added; senior markers set cut scores each year from a sample of papers; the new cut scores are published with assessment schedules in early February. [P] https://www2.nzqa.govt.nz/ncea/external-assessment/grade-score-marking
- Example, Level 2 Physics 91171 (Mechanics), 2025: three questions, each scored out of 8; **cut scores N 0-7, A 8-13, M 14-18, E 19-24**. [P] https://www.nzqa.govt.nz/nqfdocs/ncea-resource/schedules/2025/91171-ass-2025.pdf . The schedule's grade-scale table maps *counts of achieved/merit/excellence evidence* to scores, e.g. A3 = "majority of the evidence at Achievement", M5 = "some evidence at Merit", E8 = "evidence for most tasks and the Excellence evidence is accurate".
- Cut scores are also on one page for all standards. https://www2.nzqa.govt.nz/ncea/subjects/cut-scores/ [P as listing]. This repo already stores them per past paper in `exam_grade_rules`.
- **Exam format.** Printed answer booklets with a separate resource sheet, calculator, ruler and protractor; formulae and constants supplied. The 2025 L2 Physics booklet is 16 pages with the instruction to use clear numerical working, words and/or diagrams. [P] https://www.nzqa.govt.nz/nqfdocs/ncea-resource/exams/2025/91171-exm-2025.pdf and https://www.nzqa.govt.nz/nqfdocs/ncea-resource/specifications/2026/91171-spc-2026.pdf
- **Timing.** Two sessions a day, 9:30am and 2:00pm; I could not find a published session length. [P for times] https://www2.nzqa.govt.nz/ncea/exam-timetable-and-key-assessment-dates/exam-timetable/ . Duration is [U].
- **Digital exams.** The timetable marks digitally assessed subjects with an icon; in 2026 it shows Level 1 English, Chemistry and Biology, Science and Social Studies as digital, Physics and Earth Space Science as not. [P] same URL. NZQA reportedly stopped issuing personalised paper backups for NCEA digital exams from 2025 [S] https://www2.nzqa.govt.nz/about-us/strategies-projects/digital-external-assessment/ .

### B.4 What Excellence requires compared with Achieved

From the 2025 L2 Physics mechanics schedule (quoted evidence descriptors) [P] https://www.nzqa.govt.nz/nqfdocs/ncea-resource/schedules/2025/91171-ass-2025.pdf :

| Question type | Achievement | Merit | Excellence |
|---|---|---|---|
| Multi-step calculation | One correct step or one calculated value ("ONE of …"); or the final answer with no justification | "Made one error in a correct method", or the correct final value | Correct and with unit/direction, or with "a confirmatory sentence" |
| Explanation | "One correct statement" | "A statement linking cause and effect" / "two linked statements" | "Full explanation" |
| Multi-part reasoning | One piece of evidence | Linked reasoning | Fully justified, accurate |

**What this means for practice questions and marking.**
1. Questions should be multi-part with the last part demanding a linked explanation, since that is where E/M separate from A.
2. Marking should output per-question N/A/M/E scores (1-8) with the *evidence found* at each level, applied top-down, and one holistic score per question. Marking by marks-out-of-N or keyword counts mis-models the real exam.
3. Cut scores differ by paper and year, so only report a *grade estimate* with the paper's own cut scores, as `exam_grade_rules` already supports.

### B.5 The calendar shape (planning horizon)

[P] https://www2.nzqa.govt.nz/ncea/exam-timetable-and-key-assessment-dates/key-dates-for-secondary-assessment/ :
- Internal assessments run through the year in school terms (school-set; term 1 ended 2 April 2026). Internal moderation submissions run to 19 October; final date for withdrawals from internals 1 December.
- **External exams 2026: 10 November to 4 December**, 127 sessions, more than 157,000 students (https://www2.nzqa.govt.nz/about-us/news/thousands-of-students-prepare-to-sit-ncea-and-new-zealand-scholarship-exams/ ). Today (2026-11-12) is inside that window. Admission slips go to schools on 14 October; 2027 external specifications are published on 16 October.
- Externally assessed results are processed from 7 December to 6 January 2027; the exact release date is not stated on the page [U].
- Assessment schedules and cut scores for the exams are published in early February (see B.3).
- Planning horizon: a school year is four terms; internals give dated mini-deadlines, and one big externals window in November, so a "days until exam" horizon is 6-12 months for a student starting in January.

---

## Part C: University (AUT and the University of Auckland)

### C.1 Structure

| | **AUT** | **University of Auckland (UoA)** |
|---|---|---|
| Unit name | Public pages mostly say **"course"** (descriptor headings: "Course Title / Course Code"); "paper" still appears in regulations and URLs. [P] https://www.aut.ac.nz/study/study-options/studying-a-single-course , https://www.aut.ac.nz/university-language-explained . The owner's word "paper" is fine; store as "course/paper". | "Course" (e.g. COMPSCI 110). |
| Points | Most are 15 points; 120 points = 1 EFTS (full-time year); about 60 per semester; bachelor's 360 points. [P] https://www.aut.ac.nz/university-language-explained | Many courses are 15 points; recommended full-time load 120 points/year (eight 15-point courses); enrol in at most 80 points per semester; minimum full-time 100 points over two semesters or 50 in one. [P] https://www.auckland.ac.nz/en/study/applications-and-admissions/enrolment/choosing-your-courses/how-many-courses-to-enrol-in.html . A bachelor's degree is at least 360 points. [S] UoA glossary excerpt via search, not opened: https://www.auckland.ac.nz/en/about-us/about-the-university/the-university/official-publications/university-calendar/current-calendar/general-information/glossary-of-terms.html |
| Course codes | Four letters + three digits, first digit = level (COMP500 level 5, GESC600 level 6). [P] from the descriptors in C.2. | Subject + 3 digits (INFOSYS 110); term codes below. |

**AUT dates** [P] https://www.aut.ac.nz/study/semester-dates (AUT may amend):

| Year | Semester 1 | Semester 2 | Summer school |
|---|---|---|---|
| 2026 | Orientation 16 Feb; classes 23 Feb; mid-sem break 6-17 Apr; study and assessment weeks 2-19 Jun | Orientation 6 Jul; classes 13 Jul; mid-sem break 24 Aug-4 Sep; study and assessment 19 Oct-6 Nov | Classes from 23 Nov 2026; break 25 Dec-4 Jan; assessment week 1-5 Feb 2027 |
| 2027 | Orientation 15 Feb; classes 22 Feb; break 5-16 Apr; study/assessment 31 May-18 Jun | Orientation 5 Jul; classes 12 Jul; break 23 Aug-3 Sep; study/assessment 18 Oct-5 Nov | not given |

Teaching weeks (my arithmetic from those dates): classes run six weeks, break two weeks, six more weeks (12 teaching weeks), then three weeks of "study and assessment". AUT says a semester is "about 15 weeks" (12 + 3). The page does not call the final three weeks an "exam period" in all faculties; assessment may be inside it. Trimesters exist for some business master's programmes. [S/U]

**UoA dates** [P] https://www.auckland.ac.nz/en/about-us/about-the-university/the-university/official-publications/university-calendar/current-calendar/key-university-dates/academic-dates/past/semester-teaching-days-charts-2026.html (2026) and https://www.auckland.ac.nz/en/students/academic-information/important-dates.html (2027):

| Year | Summer School | Semester One | Semester Two |
|---|---|---|---|
| 2026 | 5 Jan-13 Feb; exams 16-18 Feb; 28 teaching days | 2 Mar-5 Jun lectures (57 teaching days); break 3-17 Apr; study break from 8 Jun; exams 11-29 Jun | 20 Jul-23 Oct lectures (60 teaching days); break 31 Aug-11 Sep; study break from 27 Oct; exams 29 Oct-16 Nov |
| 2027 | 6 Jan-12 Feb; exams 15-17 Feb | 1 Mar-4 Jun; break 12-23 Apr; study break 8 Jun; exams 10-28 Jun | 19 Jul-22 Oct; break 30 Aug-10 Sep; study break from 26 Oct; exams 28 Oct-15 Nov |

UoA also runs four **quarters** a year for some programmes (2027 Quarter 1 starts 18 January; Quarter 2 12 April; Quarter 3 5 July; Quarter 4 27 September) on the same 2027 page. Term codes are four digits: `1` + two-digit year + `0` summer, `3` Semester One, `5` Semester Two (2027: 1270, 1273, 1275; the legacy URL for COMPSCI 110 in Semester One 2023 uses 1233). [P] same 2027 page and https://courseoutline.auckland.ac.nz/dco/course/INFOSYS/110/1233 .

### C.2 How a course is assessed and how outcomes are published

**AUT.** Every course has a public **paper/course descriptor** PDF, anonymous, no login (I downloaded several on 2026-11-12):

```
https://paperdescriptorreport.aut.ac.nz/PaperDescriptor/PaperDescriptor?courseCode=COMP500&date=2026-11-12&saveFormat=pdf
```
`date` picks the descriptor version in force; if the code does not exist or has no version at that date the server returns an HTML page saying "Course descriptor does not exist" (MATH604, MATH501, ACCT501 failed). [P] https://paperdescriptorreport.aut.ac.nz/PaperDescriptor/PaperDescriptor?courseCode=COMP500&date=2026-11-12&saveFormat=pdf (and GESC600, ENGE501, PHYS501, CHEM501, COMP501).

Fields (read from COMP500 and GESC600): Points, Level, Prerequisites/Corequisites/Restrictions, **Learning hours ("Total learning hours: 150" for 15 points)**, Prescriptor (description), **numbered Learning Outcomes**, Content list, Learning and teaching strategies, **Assessment Plan (event name, weighting %, learning outcomes assessed)**, Grade Map, **pass requirement**, Learning resources, faculty and programmes. The PDF is a SQL Reporting Services render, so text extraction mixes column order; parse by position, not by line.

Assessment patterns in the descriptors [P]:
- COMP500 Programming Concepts (L5): Lab 50% + Final Practical Test 50%; "students must attempt all summative assessments and achieve a minimum overall grade of C-".
- ENGE501 Engineering Mathematics I: Assignment 30%, Assignment 30%, Final Exam 40%; same pass rule.
- PHYS501 Physics for Scientists and Engineers: three assessments at 30/30/40.
- CHEM501 Principles of Chemistry: Test 1, Laboratory Report, Test 2 at 25/25/50 (order of names garbled in extraction [U]); pass = overall average at least C- across all summative assessments.
- COMP501 Computing Technology in Society: individual assignment 40%, group assignment 60%.
- GESC600 Geospatial Analysis (L6): Portfolio 40%, Written Assessment (3000 words) 40%, Presentation 20%.

So AUT assessment is typically **2-4 summative items**, frequently with no final exam, and a must-pass rule expressed as an overall C- (sometimes "attempt all"). Exam mode (invigilated or online) is not stated in the descriptors; AUT's pages I could reach do not describe it [U]. AUT says exams are held in set periods with no classes, test the whole semester, and some courses have projects instead. [P] https://www.aut.ac.nz/parents-hub/general-advice/how-do-university-exams-and-assessments-work-a-guide-for-parents

**AUT grades.** 9-point scale: A+ 9, A 8, A- 7, B+ 6, B 5, B- 4, C+ 3, C 2, C- 1; D and E 0 (fail). GPA = sum(grade points × course points) / total points, three decimals, rounded to the nearest whole grade (6.5 rounds up to 7, i.e. A-). Document dated May 2021 [P, older] https://www.aut.ac.nz/__data/assets/pdf_file/0004/373351/GPA,-Honours-and-Distinction-information.pdf ; the 2026 descriptors show the grade map A+/A/A- Pass with Distinction, B+/B/B- Merit, C+/C/C- Pass, D Fail [P] (COMP500 URL above).

**UoA.** Official grade scale [P] https://www.auckland.ac.nz/en/staff/education-office/learning-teaching-policies/guidelines-assessments/grade-descriptors-taught-courses.html : A+ 90-100 (9), A 85-89 (8), A- 80-84 (7), B+ 75-79 (6), B 70-74 (5), B- 65-69 (4), C+ 60-64 (3), C 55-59 (2), C- 50-54 (1), D+ 45-49 / D 40-44 / D- 0-39 (0, fail). **Pass mark 50%.** CP = conceded pass, P = ungraded pass. GPA is the points-weighted average (UoA policy wording [S]).

Assessment of Courses Policy (approved 11 Dec 2023, reviewed 24 Mar 2025, next review 24 Mar 2030) [P] https://www.auckland.ac.nz/en/about/the-university/how-university-works/policy-and-administration/teaching-and-learning/assessment/assessment--coursework--tests-and-examinations--policy--from-jan.html :
- Weightings must be published at the start of the semester; courses "would normally include more than one item of assessment".
- A pass is 50% or more. "A minimum level of achievement on specific assessment tasks may be required" (so must-pass rules are per course, not general).
- A test is time-limited controlled assessment, normally invigilated, outside the exam period; digital modes used "where practical".
- The policy does not set exam weighting limits.

Exam modes in 2026 [P] https://www.auckland.ac.nz/en/students/academic-information/exams-and-final-results/about-exams.html : A remote non-invigilated on Inspera, B remote invigilated via Inspera Integrity Browser, C in-person on paper, D in-person on computer. **"Most exams are online and non-invigilated."** So an "invigilated exam" is not the default at UoA. Results come about 10-20 days after the exam period [S] (search summary of UoA pages).

Example UoA weightings in one course (COMPSCI 110, 2023 Semester One): exam 50%, test 20%, assignments 20%, tutorials 2% [S]. Other outlines list coursework/exam splits per course, so no general rule.

**How UoA publishes outcomes (important for an import feature).**
- The old **Digital Course Outlines** (DCO) editor was decommissioned in late 2025; outlines are now just "course outlines", edited in the Curriculum Management System (CMS). "From 2026, the OCC (Online Curriculum Catalogue) will be the default public-facing site." [P] https://teachwell.auckland.ac.nz/?p=59831
- **OCC is public:** https://study.auckland.ac.nz/ loads without login and has a search box ("Code, Name or Keyword") with filters for semester (Summer, One, Two, Most Recent) and year (2024-2028). [P] https://study.auckland.ac.nz/ . I could not confirm the URL pattern of a single course page or what fields each shows [U].
- **Legacy URL pattern** `https://courseoutline.auckland.ac.nz/dco/course/{SUBJECT}/{NNN}/{termcode}` (for example `.../INFOSYS/110/1233`) **redirects to the University single sign-on** when fetched now (HTTP 302 to iam.auckland.ac.nz, checked 2026-11-12), although older copies of these pages appear in search results. Canvas syllabus pages (`canvas.auckland.ac.nz/courses/{id}/assignments/syllabus`) also need a login. [P for the redirect] https://courseoutline.auckland.ac.nz/dco/course/COMPSCI/110/1253
- Old public outlines showed capabilities, learning outcomes, and assessment tables mapping each item and weight to outcomes. [S] https://courseoutline.auckland.ac.nz/dco/course/INFOSYS/110/1233 (via search excerpt).
- Practical consequence: **import of UoA outcomes cannot rely on an anonymous URL.** Offer upload of the PDF/screenshot, paste, or manual entry, and try OCC as a best-effort source.

### C.3 Workload

- AUT: about 150 hours per 15-point course per semester: 30-50 hours of class time and 100-120 hours of independent study and assignments, i.e. 2-3 hours of class and 7-8 hours of study per week; semester about 15 weeks. A full-time student on four courses needs about 40 hours a week. [P] https://www.aut.ac.nz/study/study-options/studying-a-single-course , https://aut.ac.nz/student-life/studying/study-help/assessments-and-exams/what-to-expect-from-university-study , https://www.aut.ac.nz/parents-hub/general-advice/how-do-university-exams-and-assessments-work-a-guide-for-parents . Descriptors confirm "Total learning hours: 150".
- UoA: a 15-point undergraduate course "usually involve[s] around 10 hours of study per week, including lecture and tutorial times". [P] https://learningessentials.auckland.ac.nz/key-study-skills/time-management/scheduling-your-semester . The 2026 glossary's "approximately 150 hours" wording was seen only in a search excerpt [S].
- Lectures, tutorials, labs and workshops make up the class time; students are told they are "responsible for [their] own learning" (AUT). [P] AUT what-to-expect page above.

### C.4 Past exams and course material

- **UoA:** the Library's "Past exam papers" collection has over 7,000 papers from the past six years including this year's, searchable by course code or title, **sign-in with University username and password required**, papers loaded about two months after each exam period. [P] https://www.auckland.ac.nz/en/library/use-our-collections/past-exam-papers.html . Not scrapable for the app; it can only be a link the student opens.
- **AUT:** the Library "doesn't hold past exam papers"; some courses include past exams on Canvas; ask the lecturer. [P] https://aut.ac.nz.libanswers.com/faq/234120 . The AUT parents' page says past exams are "sometimes provided".

### C.5 How university differs from NCEA, for a study app

| NCEA | University (AUT, UoA) | Consequence |
|---|---|---|
| National standards; every standard has the same criteria and the same marking schedule | **No national standard.** Outcomes and assessments are set per course and may change between offerings ("Course descriptors may be amended between teaching periods/semesters": AUT). | Treat the course outline/descriptor as the source of truth and re-import each term; do not assume any bank of past questions. |
| ~6 subjects, many small standards (4-6 credits) | 8 courses/year, each 150 hours; assessments are 2-4 big items (AUT examples above) | Weights drive priority: a 40-50% item deserves the study time, not equal time per topic. |
| Teacher scaffolding, a past-paper culture | Student-directed; AUT: "responsible for your own learning" | The app should offer planning and nudges the teacher used to. |
| Three clear grade bands per standard | 9-point GPA scale, pass 50% (UoA) / C- overall (AUT) | The "Merit/Excellence estimate" must be replaced by "percentage → letter" or must-pass status per course. |
| One external exam window in November | Exam dates per semester, mid-semester tests, assignments through the term, some online non-invigilated exams (UoA) | Planning is per-assessment, with test dates inside the semester. |
| Mostly closed-book written exams | Mixed: labs, portfolios, group work, practical tests, projects (AUT descriptors above) | Practice generation needs more assessment modes than "exam question". |
| Little referencing | Referencing and academic integrity are explicit (AUT uses APA style; plagiarism can mean failing a paper) [P] https://www.aut.ac.nz/parents-hub/general-advice/how-do-university-exams-and-assessments-work-a-guide-for-parents | Assignments need milestone planning, not just memory practice. UoA referencing style varies by department [U]. |
| Cumulative content within a year | Often cumulative finals over a 12-week teaching block | Longer-term spacing inside one course matters. |

---

## Part D: recommendations for the app

Priority order is by value times feasibility. Each item is tagged **[Evidence]** (supported by the studies above) or **[Judgement]**.

### D.1 Fix the retrieval/spacing core first

1. **Make review items repeat. [Evidence]** A review item must come back until its schedule says it is safe. Today `fresh_due` removes any answered question (`server/reviews.py:114`). Spacing and retrieval are the two highest-rated techniques (A.2, A.3, A.14). Change the unit from "a question that is asked once" to a **memory item with a scheduled state**.
2. **Schedule with FSRS-6 using default weights, not SM-2 and not a hand rule. [Evidence for the principle; Judgement for the choice]** Reasons: target-retention control, interval depends on the real gap, handles late reviews, 20-30% fewer reviews than SM-2 in the maintainers' simulation, maintained libraries for Python (`fsrs`) and TypeScript. Risks: validated on Anki flashcards, not on AI-marked short answers. Defaults:
   - `desired_retention = 0.90`; allowed range 0.80-0.95 per course. [Judgement within the range FSRS documents as reasonable, 0.70-0.97]
   - Default weights as listed in A.5. Do not tune per user until there are thousands of reviews. [Judgement; follows the FSRS guidance to use defaults when there are too few reviews]
   - `maximum_interval = 365` days for school/university material (library default is 36500; the Good-Good-Good chain in A.5 reaches 766 days by the fifth review). [Judgement]
   - Fuzz on; learning steps 10 minutes then 1 day for brand-new items if the student reviews within a session. [Judgement; library default is 1 min and 10 min]
3. **Grade mapping from the existing app signals. [Judgement]** The app already has an AI correct/incorrect and a 1-5 confidence (asked *before* the answer is revealed, which is right):

   | Outcome | FSRS grade |
   |---|---|
   | AI marks wrong | 1 Again |
   | Correct, confidence 1-2 | 2 Hard |
   | Correct, confidence 3-4 | 3 Good |
   | Correct, confidence 5 and (optionally) answered fast | 4 Easy |
   | AI marking unavailable | use confidence only, flag as "unmarked" and do not give Easy |

   High-confidence wrong answers should be flagged for an extra near-term retrieval (hypercorrection and calibration evidence, A.10-A.11) [Evidence for the effect, Judgement for the rule].
4. **Successive relearning inside a session. [Evidence]** If a student gets an item wrong, re-ask it later in the same session after other items (not immediately), until it is right once; then hand it to the long-term schedule. Do not drill beyond that (overlearning, A.12).
5. **Items are skills/concepts with variants, not fixed questions. [Evidence + Judgement]** For procedures a repeat of the same numbers tests memory of the answer. Keep the FSRS state on a `memory_item` (a concept or skill) and let it own several `question_variant`s (new values, contexts, wording). Remove or relax the 0.85 near-duplicate filter for variants of the same item. For facts, a variant can be the same question.
6. **Replace the mastery and grade estimate. [Judgement]** Per-item retrievability from FSRS (R now) gives an honest "probability of recall" per topic or outcome. Do not label it as a grade. For NCEA, produce a grade estimate only from marked **past-paper attempts** scored N/A/M/E per question and compared with that paper's own cut scores (`exam_grade_rules`), and say what it is.

### D.2 Interleaving, worked examples, pre-tests, feedback, calibration

7. **Mix practice types. [Evidence for maths/physics/chemistry; none for words]** After a blocked introduction in a lesson, daily Review and "mixed practice" should interleave *problem types* across topics (Rohrer 2020). Do not interleave vocabulary or definitions.
8. **Lesson structure for procedures. [Evidence]** Worked example → completion (partially worked) problem → full problem ("fade"); use correct examples only; do not add heavy self-explanation prompts on top of examples without testing (Barbieri 2023). Fade faster for students with strong prior results (expertise reversal). The current lesson has one worked example and then 3-5 full problems with no completion step.
9. **Open each lesson with 2-3 ungraded pre-questions on the day's content. [Evidence for text; Judgement elsewhere]** They orient attention and help later learning (Richland 2009; Pan & Sana 2021). Pair them with feedback in the lesson. Keep the existing prior-knowledge check, but make it retrieval of yesterday's items, not a rereading prompt.
10. **End each lesson with free recall. [Evidence]** "Write what you can remember from this lesson" before the summary is shown, not a reread of the summary (Karpicke & Roediger).
11. **Feedback. [Evidence]** After every retrieval show the correct answer or worked solution immediately, with the reasoning for errors (Butler & Roediger 2008; Metcalfe 2017; Yang 2021 lists corrective feedback as a moderator). Keep the Rapid-questions rule (no feedback until the end) *only* for exam simulation, where the aim is practising exam conditions.
12. **Calibration screen. [Evidence for the problem; Judgement for the design]** Ask confidence before the answer is revealed (done); show "you rated 5, you were right 60%" per topic over time, and a list of confident misses. Do not use confidence alone to set intervals when AI marking is available.
13. **Narrow "Teaching style". [Evidence]** Replace modality-matching language with tone, language level and pacing options; do not tailor by "visual/auditory/kinesthetic" (Pashler 2008).
14. **Stop recommending or generating**: rereading as a review step, highlighting-style tasks, and "summarise this lesson" as the main review activity (low utility, A.14). Allow them only as optional extras.

### D.3 Planning back from assessment dates without sacrificing retention afterwards

15. **Add assessment events and plan against them. [Judgement, informed by Cepeda 2008]** For each item, `T_exam` = the next event that covers it. For an event that is RI days away, schedule the *last full retrieval pass* about `0.2 × RI` before it, clamped to 1-28 days (this reproduces Cepeda's best gaps roughly: ~1.4 d at RI 7, ~7 d at 35, ~14 d at 70, 28 d at a year), and raise desired retention toward 0.95 in the last two weeks. Implementation sketch (pseudo-code, to be tuned):

    ```
    due = now + I(r_base, S)                      # FSRS interval at 0.90
    if T_exam:
        RI = T_exam - now
        gap_final = clamp(0.2 * RI, 1 day, 28 days)
        due = min(due, T_exam - gap_final)        # make sure a review lands before the exam window
        R_exam = R(T_exam - last_review, S)       # predicted recall on exam day if nothing else happens
        at_risk = R_exam < 0.85                   # surface in the daily plan
    due = max(due, now)                           # if already late: due now, never negative
    ```
    These numbers are a fit to one set of fact-learning data (A.3), so mark them as defaults the engineer can change.
16. **Daily plan from capacity. [Judgement]** Ask hours per week at onboarding. Convert to a daily review cap (the unit cost of a review is roughly 30-60 seconds in my judgement; measure it in the app and use the measured value). Fill the day by priority = (assessment weight) × (1 − R now) × (closeness of the event), and show what was left out.
17. **After the assessment: keep, don't drop. [Evidence + Judgement]** When `T_exam` passes, keep the same FSRS state but switch the item to a *maintenance* target: retention 0.80-0.85, longer intervals, cap 365 days. This avoids the loss seen when practice stops (Custers 2010; Bahrick & Hall 1991). Items tagged as **prerequisites for a later course** stay at 0.85 until that course finishes. Everything else may go to archive after one year with no failures, but is never deleted.
18. **Bridge school to university. [Judgement]** NCEA externals end 2026-12-04, AUT Semester 1 2027 classes begin 22 February and UoA's 1 March 2027, about 12 weeks later. Provide a "bridge" plan: a light January daily mix of prerequisite items (maths, writing, the subject the degree builds on) and a refresher pass 2-3 weeks before the first class, using the course's prerequisite list from its descriptor/outline.
19. **Lesson cadence follows horizon. [Judgement]** Early in the term new-topic lessons dominate; as the event nears, shift the nightly generation from "new content" to "mixed retrieval and weakest outcomes". Today the scheduler always writes a new stage lesson per topic per night with a fixed goal ("Ace the external exam"); make the goal a per-course setting.

### D.4 Data model that serves NCEA and university

20. **Proposed concepts. [Judgement]** Generalise today's `subjects → topics`, `standards`, `courses`:

    ```
    institution        id, kind ('nzqa','aut','uoa','other'), name
    programme          id, institution_id, name, level_or_stage ('NCEA L2','Year 1 BSc'), start_year, regime ('ncea','new_nzce','uni')
    course             id, programme_id, code ('PHYS 91171 subject' / 'COMP500' / 'COMPSCI 110'), title,
                       points_or_credits, level, term_code ('1273'/'S1-2026'), start_date, end_date,
                       expected_hours (150), grade_scale ('ncea_nmae','uoa9','aut9','nzce_a_to_e'),
                       pass_rule_text, outline_url, outline_fetched_at, source ('aut_descriptor','upload','manual')
    outcome            id, course_id, kind ('standard','learning_outcome'), code ('AS91171','LO3'), text, credits
    topic              (keep) id, course_id, name  ->  topic_outcome(topic_id, outcome_id) many-to-many
    assessment_event   id, course_id, kind (internal|external_exam|test|assignment|lab|quiz|project|presentation|final_exam|practical|other),
                       title, opens_at, due_at / sits_at, duration_min, weight_pct (university) or credits (NCEA),
                       mode (paper_invigilated|digital_invigilated|online_open|take_home|in_class), grade_scale,
                       covers_topic_ids / covers_outcome_ids, is_must_pass, status, result (nullable)
    memory_item        id, topic_id, outcome_id, material_type ('fact','procedure','concept','writing_component'),
                       fsrs_state (S, D, last_review, reps, lapses), retention_goal ('exam_only','next_course','long_term')
    question_variant   id, memory_item_id, text, expected_answer, rubric, source ('past_paper','ai','uploaded')
    review_log         id, memory_item_id, variant_id, answered_at, confidence, correct, grade, elapsed_days, R_before
    plan_target        course_id, target_grade_or_gpa, horizon_date
    ```
    - NCEA fits: course = a subject (or one standard), outcome = the achievement standard (`code` is text, so "AS91171" replaces the integer `standards.number`), assessment events = internal deadlines plus the November external; `subjects.level CHECK 1..3` becomes a programme attribute, not a constraint. `exam_questions.standard_number NOT NULL` becomes an optional `outcome_id`.
    - University fits: course = AUT descriptor / UoA course, outcome = numbered learning outcome, assessment events = descriptor assessment plan rows with weight, `is_must_pass` from the pass rule.
    - The new-NZCE regime (2028+) can be added as another `regime` without changing structure: subject-based, 3-4 assessments a year, A+ to E.
21. **Imports. [Evidence of availability]**
    - **AUT:** build a fetch-by-code importer on the public descriptor URL (C.2); parse Points, Level, prerequisites, learning hours, numbered outcomes, assessment plan rows and pass rule. Parse the PDF by layout, not by line order. Re-fetch each term.
    - **UoA:** try the public OCC; otherwise ask the student to upload the outline PDF or paste its text; do not depend on `courseoutline.auckland.ac.nz` or Canvas (login).
    - **NCEA:** keep the current pairing of papers and schedules; add the NZQA exam timetable (sessions at 9:30 and 14:00; 2026 window 10 Nov-4 Dec) as dated assessment events per standard.
    - Store calendar templates per institution and year (the dates in C.1) so semester and break dates can pre-fill; mark them "check against the institution calendar".

### D.5 How lesson and review generation should differ

| | Facts / definitions | Procedures | Concepts | Extended writing |
|---|---|---|---|---|
| Lesson | Short; cues and examples; no long text | Worked example → completion problem → full problem; faded for stronger students | Explanation chunks with "why" prompts and a contrasting case | Model answer with annotations tied to the marking criteria; a planning template |
| Review item | Cue → answer, recall not recognition | Isomorphic problem variant; mark the method and the answer separately | Short explanation against a rubric of linked ideas | Retrieval items for the *ingredients* (key evidence, structure, definitions); schedule drafts as plan events |
| Marking | Exact/near-exact | Method, units, answer; partial credit | Linked-ideas rubric (top-down A→M→E for NCEA) | Rubric-based comment with the next step; no FSRS grade on the whole essay |
| Spacing/interleaving | Spaced; block is fine | Spaced and interleaved | Spaced; mix with procedures | Milestones against the due date |

**NCEA vs university generation. [Judgement]**
- *NCEA:* anchor every question to a standard and to the A/M/E evidence descriptors; use real past papers first and clearly-labelled AI practice second (the app already separates these); mark per question 1-8 top-down; compare with that paper's cut scores.
- *University:* anchor to numbered learning outcomes from the course outline and weight priority by assessment weight; generate from the student's own lecture slides/readings (no past-paper bank is available: AUT's library holds none, UoA's needs a login); support assessment kinds beyond exams (lab report, portfolio, practical test, presentation) by turning rubrics into checklists and planning milestones; treat referencing and academic integrity as part of assignment guidance (AUT uses APA style).
- Keep the existing honesty rules: AI marks and estimates are never presented as official grades; imports are marked unverified.

### D.6 Onboarding questions

Ask once, allow later edits. [Judgement]
1. Where do you study: NCEA (which level and year) / AUT / University of Auckland / other? (Selects regime, grade scale, calendar templates.)
2. Which courses/subjects this term or year? For each, paste or upload the outline or enter the code (AUT descriptor fetch). For NCEA, which standards, internal or external?
3. Key dates: tests, assignment due dates, and final exam or assessment dates (pre-fill from the institution calendar; confirm).
4. What do you want from each course: pass, a target grade or GPA, or Excellence in specific standards?
5. How long do you need to remember it: for this assessment only / until the next course builds on it / long term? (Sets `retention_goal`.)
6. Does a later course or exam depend on this one (for example Level 3 calculus → first-year maths)? Which?
7. Hours per week available, and which days or times you usually study. (Sets daily cap and nightly generation time.)
8. A 3-5 question ungraded check per course to find the starting level (also a pre-test, A.9).
9. Do you handwrite or type answers? (The app has photo upload for handwriting.)
10. Tone/language/pace preferences for explanations (not "learning style").
11. For Year 13 or a school leaver: expected university and start date (to schedule the bridge plan).

### D.7 What is strongly evidence-backed and what is judgement

**Strongly evidence-backed (build these with confidence):**
- Repeated retrieval with growing gaps, answer-before-feedback, corrective feedback after every attempt (A.2-A.4, A.10).
- Spacing with final-review gap depending on how long the knowledge is needed (Cepeda); spacing beats cramming (A.3).
- Stop massed over-practice once an item is learned (A.12).
- Interleaving for maths-type problem sets (A.6); worked examples for novices with fading (A.7).
- Drop rereading, highlighting, summarising as core study, and drop learning-style matching (A.14).
- Practice marked the way NZQA marks: per question, top-down, with A/M/E evidence descriptors and the paper's own cut scores (B.3, B.4).
- Per-course assessment weights, learning outcomes and must-pass rules are published and differ per course (C.2).

**Judgement (reasoned, not directly tested):**
- FSRS-6 defaults for AI-marked school answers; grade mapping from correctness and confidence; maximum interval and daily caps.
- The `0.2 × RI` clamp for final-review gap and ramp of desired retention to 0.95; the maintenance targets 0.80-0.85.
- The January bridge plan and "prerequisite" tagging.
- Treating extended writing as milestones rather than FSRS items; session lengths; the lesson changes (pre-questions, free recall, completion problems) beyond the cited studies.
- All data-model names above.

---

## Unanswered questions and unconfirmed items (check before relying)

1. **NCEA exam length** in 2026 per standard: not found. NZQA gives 9:30 and 14:00 start times only. https://www2.nzqa.govt.nz/ncea/exam-timetable-and-key-assessment-dates/exam-timetable/
2. **Results release date** for 2026 externals: NZQA says results are processed 7 December to 6 January 2027, with no release date stated.
3. **NCEA credit rule wording** (60 vs 80) and **UE review status**: NZQA documents conflict (B.1).
4. **UoA public course-page URL and fields in the new Online Curriculum Catalogue** (https://study.auckland.ac.nz/): not confirmed; the legacy outline site redirects to login.
5. **AUT exam modes** (invigilated vs online) and whether the final 3 "study and assessment" weeks always contain exams: not found.
6. **Whether FSRS-6 weights work well for AI-marked school answers**: no published evidence. A small pilot against the app's own review log would answer it.
7. **FSRS-7** (34 parameters) exists in the benchmark but its formulas were not on the documentation page I read. FSRS-6 is documented, matches the verified Python package (6.3.2) and the TypeScript package.
8. **Rawson & Dunlosky criterion level** ("how many correct recalls is enough"): abstract not accessible; take 1-3 correct recalls per session as a starting range, which is judgement.
9. **Programming-specific** retention evidence is thin.
10. **Exact figures I only saw in secondary summaries:** Dunlosky 2013 ratings, Barbieri 2023 g = 0.48, Bisra 2018 g = 0.55, Bahrick & Hall 1991, Cooper 1996, Rawson 2013, UoA glossary (360 points, 150 hours), UoA results timing.
11. **The NCEA replacement could change** (election or consultation outcomes), including the University Entrance rules still being worked on.

## Source list (alphabetical by topic)

Learning science (primary records): https://pubmed.ncbi.nlm.nih.gov/16719566/ · /19076480/ · /16507066/ · /18276894/ · /25150680/ · /33683913/ · /31556629/ · /17576148/ · /24444515/ · /19751074/ · /33793291/ · /18491500/ · /27648988/ · /25910388/ · /23020639/ · /26162104/ · /26173288/ · /20046194/ · /35238586/ · /18274876/ · https://www.evullab.org/pdf/CepedaVulRohrerWixtedPashler-PS-2008.pdf · https://www.Gwern.net/doc/psychology/spaced-repetition/1993-bahrick.pdf · https://super-memory.com/english/ol/sm2.htm · https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm · https://github.com/open-spaced-repetition/srs-benchmark · https://pypi.org/project/fsrs/ · https://www.npmjs.com/package/ts-fsrs

NCEA: https://www2.nzqa.govt.nz/ncea/about-ncea/ · https://tahatu.govt.nz/school-and-ncea/doing-ncea/how-ncea-works · https://www2.nzqa.govt.nz/ncea/understanding-secondary-quals/university-entrance/ · https://www2.nzqa.govt.nz/ncea/external-assessment/grade-score-marking · https://www.nzqa.govt.nz/nqfdocs/ncea-resource/schedules/2025/91171-ass-2025.pdf · https://www.nzqa.govt.nz/nqfdocs/ncea-resource/specifications/2026/91171-spc-2026.pdf · https://www2.nzqa.govt.nz/ncea/exam-timetable-and-key-assessment-dates/key-dates-for-secondary-assessment/ · https://www2.nzqa.govt.nz/ncea/exam-timetable-and-key-assessment-dates/exam-timetable/ · https://tahurangi.education.govt.nz/senior-secondary-quals-finalised · https://www.education.govt.nz/news/more-details-about-new-senior-secondary-qualifications

AUT: https://www.aut.ac.nz/study/semester-dates · https://paperdescriptorreport.aut.ac.nz/PaperDescriptor/PaperDescriptor?courseCode=COMP500&date=2026-11-12&saveFormat=pdf · https://www.aut.ac.nz/__data/assets/pdf_file/0004/373351/GPA,-Honours-and-Distinction-information.pdf · https://www.aut.ac.nz/study/study-options/studying-a-single-course · https://www.aut.ac.nz/university-language-explained · https://aut.ac.nz.libanswers.com/faq/234120

UoA: https://www.auckland.ac.nz/en/about-us/about-the-university/the-university/official-publications/university-calendar/current-calendar/key-university-dates/academic-dates/past/semester-teaching-days-charts-2026.html · https://www.auckland.ac.nz/en/students/academic-information/important-dates.html · https://www.auckland.ac.nz/en/staff/education-office/learning-teaching-policies/guidelines-assessments/grade-descriptors-taught-courses.html · https://www.auckland.ac.nz/en/about/the-university/how-university-works/policy-and-administration/teaching-and-learning/assessment/assessment--coursework--tests-and-examinations--policy--from-jan.html · https://www.auckland.ac.nz/en/students/academic-information/exams-and-final-results/about-exams.html · https://www.auckland.ac.nz/en/library/use-our-collections/past-exam-papers.html · https://teachwell.auckland.ac.nz/?p=59831 · https://study.auckland.ac.nz/ · https://learningessentials.auckland.ac.nz/key-study-skills/time-management/scheduling-your-semester
