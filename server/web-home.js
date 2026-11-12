import { countUp } from './web-common.js';

const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
const link = (text, href, className = '') => {
  const node = element('a', text, `button ${className}`.trim());
  node.href = href;
  return node;
};
const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`;
const percent = value => `${Math.round(value * 100)}%`;
const day = value => new Intl.DateTimeFormat('en-CA', { timeZone: 'Pacific/Auckland' }).format(new Date(value));

// `count` animates the figure up to its value; `format` shows it (for example as a percentage or a fraction).
function stat(value, label, count = null) {
  const box = element('div', '', 'stat');
  const figure = element('b', String(value));
  if (count) countUp(figure, count.to, { format: count.format });
  box.append(figure, element('span', label));
  return box;
}

function table(headings, rows, label) {
  const node = element('table', '', 'table');
  node.setAttribute('aria-label', label);
  const head = element('tr');
  for (const heading of headings) head.append(element('th', heading));
  const thead = element('thead'); thead.append(head); node.append(thead);
  const body = element('tbody');
  for (const row of rows) {
    const line = element('tr');
    for (const cell of row) {
      const td = element('td');
      td.append(cell instanceof Node ? cell : document.createTextNode(cell));
      line.append(td);
    }
    body.append(line);
  }
  node.append(body);
  return node;
}

const gradeChip = grade => {
  const tone = grade === 'Excellence' || grade === 'Merit' || /^A/.test(grade) ? 'ok' : grade === 'Not achieved' || /^D/.test(grade) ? 'warn' : '';
  return element('span', grade, `chip ${tone}`.trim());
};

// Counts of saved records, plus one labelled rough estimate; no streaks or predicted exam results.
export async function renderHome(container, api) {
  const [summary, lessons, curriculum, plan, estimates] = await Promise.all([api('/study-summary'), api('/lessons'),
    api('/curriculum').catch(() => null), api('/review-plan').catch(() => null), api('/grade-estimates').catch(() => [])]);
  const { reviews, topics, weak_concepts: weak, exams } = summary;
  const today = day(new Date());
  // The same list as the Lessons page: today's lessons, plus the newest unopened lesson from an earlier day for each topic
  // that has none today (one that was started instead gets a fresh lesson, so it is not carried).
  const fresh = lessons.filter(lesson => lesson.created_at && day(lesson.created_at) === today);
  const carried = new Map();
  for (const lesson of lessons) {
    if (lesson.completed_at || lesson.started || fresh.some(f => f.topic_id === lesson.topic_id) || carried.has(lesson.topic_id)) continue;
    carried.set(lesson.topic_id, lesson);
  }
  const todays = [...fresh, ...carried.values()];
  const todo = todays.filter(lesson => !lesson.completed_at);
  const where = await Promise.all(todo.map(lesson => api(`/lessons/${lesson.id}/progress`).catch(() => null)));
  const unfinished = exams.find(exam => exam.unfinished && exam.answered > 0);

  container.classList.add('home');
  const head = element('div', '', 'page-head'); const title = element('div');
  title.append(element('h1', 'Home'),
    element('p', new Intl.DateTimeFormat('en-NZ', { timeZone: 'Pacific/Auckland', weekday: 'long', day: 'numeric', month: 'long' }).format(new Date()), 'muted'));
  head.append(title); container.append(head);
  // Existing learners are offered the new setup; nothing changes until they choose to.
  if (curriculum && !curriculum.set_up) {
    const offer = element('section', '', 'card stack');
    offer.append(element('h2', 'New: plan around your assessment dates'),
      element('p', 'Tell StudyGuider whether you are doing NCEA or university papers (AUT, University of Auckland or elsewhere) and when your assessments are. Reviews then come back on a schedule that keeps what you learn, and lessons switch to exam practice as a date gets close. Everything you already have stays as it is.', 'muted'),
      link('Set up my plan', '#plan', 'primary'));
    container.append(offer);
  }

  // Headline numbers
  const graded = estimates.filter(e => e.estimate);
  const strip = element('div', '', 'stat-row');
  strip.append(stat(percent(summary.overall_mastery), 'Expected recall', { to: summary.overall_mastery * 100, format: n => `${Math.round(n)}%` }),
    stat(`${todays.length - todo.length} / ${todays.length}`, 'Lessons done today', { to: todays.length - todo.length, format: n => `${Math.round(n)} / ${todays.length}` }),
    stat(reviews.due, 'Reviews due', { to: reviews.due, format: n => String(Math.round(n)) }),
    stat(`${graded.length} / ${estimates.length}`, 'Subjects with a grade estimate', { to: graded.length, format: n => `${Math.round(n)} / ${estimates.length}` }));
  container.append(strip);

  // Lessons to do
  container.append(element('h2', 'Lessons to do'));
  if (todo.length) {
    container.append(table(['Topic', 'Lesson', 'Status', ''], todo.map((lesson, position) => {
      const started = (where[position]?.section || 0) > 0;
      return [`${lesson.subject} · ${lesson.topic}`, lesson.query, element('span', started ? 'In progress' : 'To do', `chip ${started ? '' : 'warn'}`.trim()),
        link(started ? 'Continue' : 'Start', `#lessons?lesson=${lesson.id}`, started ? '' : 'primary')];
    }), 'Lessons to do today'));
  } else {
    container.append(element('p', todays.length ? 'All of today’s lessons are done. Well done.' : 'No lessons were prepared today. A new one is made overnight for each topic you are learning.', 'muted'));
  }
  const actions = element('div', '', 'toolbar');
  if (reviews.due) actions.append(link(`Start ${plural(reviews.due, 'review')}`, '#reviews', 'primary'));
  if (reviews.left_out) actions.append(element('span', `${reviews.left_out} more due, kept for another day (daily limit ${reviews.cap})`, 'muted'));
  if (unfinished) actions.append(link(`Resume exam (${unfinished.answered} of ${unfinished.questions} answered)`, '#exams'));
  if (actions.children.length) container.append(actions);

  // Coming assessments, with predicted recall on the day
  const coming = (plan?.assessments || []).slice(0, 5);
  if (coming.length) {
    container.append(element('h2', 'Coming up'));
    container.append(table(['Date', 'Assessment', 'Predicted recall on the day'], coming.map(a => [
      `${day(a.due_date + 'T12:00:00')} (${a.days === 0 ? 'today' : a.days === 1 ? 'tomorrow' : `in ${a.days} days`})`, a.subject ? `${a.subject} · ${a.title}` : a.title,
      a.predicted_recall == null ? element('span', 'No reviews yet', 'muted') : `${percent(a.predicted_recall)}${a.at_risk ? ` · ${a.at_risk} at risk` : ''}`]), 'Coming assessments'));
  }
  if (graded.length) {
    container.append(element('h2', 'Grade estimates'));
    container.append(table(['Subject', 'Estimate', 'From'], graded.map(e => [e.name, gradeChip(e.estimate), e.summary || '']), 'Grade estimates'));
    container.append(element('p', 'NCEA: a full past paper, AI-marked, graded with that paper’s own cut scores. University: the marks you entered, weighted by each assessment. Neither is an official result.', 'muted'));
  }

  // Topics and how much of each is remembered
  container.append(element('h2', 'Topics'));
  if (topics.length) {
    container.append(table(['Topic', 'Recall', '', 'Answered'], topics.map(topic => {
      const meter = element('div', '', 'bar'); const fill = element('i'); fill.style.setProperty('--v', String(Math.min(1, Math.max(0, topic.mastery)))); meter.append(fill);
      meter.setAttribute('role', 'progressbar'); meter.setAttribute('aria-label', `${topic.topic} mastery`);
      meter.setAttribute('aria-valuemin', '0'); meter.setAttribute('aria-valuemax', '100'); meter.setAttribute('aria-valuenow', String(Math.round(topic.mastery * 100)));
      return [`${topic.subject} · ${topic.topic}`, topic.reviewed_questions ? percent(topic.mastery) : '—', meter,
        element('span', `${topic.reviewed_questions ?? 0} of ${plural(topic.questions ?? 0, 'question')}`, 'muted')];
    }), 'Recall by topic'));
    container.append(element('p', summary.estimate_rule, 'muted'));
  } else container.append(element('p', 'Choose topics in Settings to see them here.', 'muted'));

  // Weak concepts and exams side by side on wide screens
  const columns = element('div', '', 'two-col');
  const weakBox = element('section', '', 'stack');
  weakBox.append(element('h2', 'Weak concepts'), element('p', 'Tomorrow’s lesson will revisit these.', 'muted'));
  if (weak.length) { const list = element('ul'); for (const item of weak) list.append(element('li', `${item.concept} (${item.topic})`)); weakBox.append(list); }
  else weakBox.append(element('p', 'None yet. These appear after review answers.', 'muted'));

  const answers = reviews.answers_last_30_days || {};
  const answered = Object.values(answers).reduce((sum, n) => sum + n, 0);
  const reviewBox = element('section', '', 'stack');
  reviewBox.append(element('h2', 'Reviews'));
  reviewBox.append(element('p', answered
    ? `Last 30 days: ${answers.correct || 0} correct, ${answers.incorrect || 0} incorrect${answered - (answers.correct || 0) - (answers.incorrect || 0) ? `, ${answered - (answers.correct || 0) - (answers.incorrect || 0)} not independently marked` : ''}.`
    : 'No review answers yet.'),
    element('p', `${reviews.due} due now, ${reviews.upcoming} coming up, ${reviews.total} in total.`, 'muted'));
  columns.append(weakBox, reviewBox);
  container.append(columns);

  container.append(element('h2', 'Recent exams'), element('p', 'Marks are AI-marked practice, unofficial, and not an NZQA grade.', 'muted'));
  if (exams.length) {
    container.append(table(['Date', 'Kind', 'Result'], exams.map(exam => [
      day(exam.created_at),
      exam.kind === 'ai_practice' ? 'AI practice (unofficial)' : exam.kind === 'mixed' ? 'Mixed practice' : 'Past paper',
      exam.marked_questions
        ? `${exam.marks_awarded} / ${exam.marks_available} marks (${exam.marked_questions} of ${plural(exam.questions, 'question')} marked)`
        : `${exam.answered} of ${plural(exam.questions, 'question')} answered, not marked`,
    ]), 'Recent exams'));
  } else container.append(element('p', 'No exams yet.', 'muted'));
}
