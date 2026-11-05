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
  const tone = grade === 'Excellence' || grade === 'Merit' ? 'ok' : grade === 'Not achieved' ? 'warn' : '';
  return element('span', grade, `chip ${tone}`.trim());
};

// Counts of saved records, plus one labelled rough estimate; no streaks or predicted exam results.
export async function renderHome(container, api) {
  const [summary, lessons] = await Promise.all([api('/study-summary'), api('/lessons')]);
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

  // Headline numbers
  const estimated = topics.filter(topic => topic.estimated_grade).length;
  const strip = element('div', '', 'stat-row');
  strip.append(stat(percent(summary.overall_mastery), 'Overall mastery', { to: summary.overall_mastery * 100, format: n => `${Math.round(n)}%` }),
    stat(`${todays.length - todo.length} / ${todays.length}`, 'Lessons done today', { to: todays.length - todo.length, format: n => `${Math.round(n)} / ${todays.length}` }),
    stat(reviews.due, 'Reviews due', { to: reviews.due, format: n => String(Math.round(n)) }),
    stat(`${estimated} / ${topics.length}`, 'Topics with a grade estimate', { to: estimated, format: n => `${Math.round(n)} / ${topics.length}` }));
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
  if (unfinished) actions.append(link(`Resume exam (${unfinished.answered} of ${unfinished.questions} answered)`, '#exams'));
  if (actions.children.length) container.append(actions);

  // Topics, progress and estimated grade
  container.append(element('h2', 'Topics'));
  if (topics.length) {
    container.append(table(['Topic', 'Mastery', '', 'Estimated grade'], topics.map(topic => {
      const meter = element('div', '', 'bar'); const fill = element('i'); fill.style.setProperty('--v', String(Math.min(1, Math.max(0, topic.mastery)))); meter.append(fill);
      meter.setAttribute('role', 'progressbar'); meter.setAttribute('aria-label', `${topic.topic} mastery`);
      meter.setAttribute('aria-valuemin', '0'); meter.setAttribute('aria-valuemax', '100'); meter.setAttribute('aria-valuenow', String(Math.round(topic.mastery * 100)));
      return [`${topic.subject} · ${topic.topic}`, percent(topic.mastery), meter,
        topic.estimated_grade ? gradeChip(topic.estimated_grade) : element('span', `Needs ${5 - Math.min(topic.review_answers, 5)} more review answers`, 'muted')];
    }), 'Mastery and estimated grade by topic'));
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
