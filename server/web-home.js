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

function stat(value, label) {
  const box = element('div', '', 'stat');
  box.append(element('b', String(value)), element('span', label));
  return box;
}

// Counts of saved records only; no predicted grades, readiness scores or streaks.
export async function renderHome(container, api) {
  const summary = await api('/study-summary');
  const { lessons, reviews, topics, weak_concepts: weak, exams } = summary;
  const left = lessons.today - lessons.completed_today;
  const unfinished = exams.find(exam => exam.unfinished && exam.answered > 0);

  const head = element('div', '', 'page-head'); const title = element('div');
  title.append(element('h1', 'Home'),
    element('p', new Intl.DateTimeFormat('en-NZ', { timeZone: 'Pacific/Auckland', weekday: 'long', day: 'numeric', month: 'long' }).format(new Date()), 'muted'));
  head.append(title); container.append(head);

  // What to do today
  const parts = [];
  if (lessons.today) parts.push(left ? `${lessons.completed_today} of ${lessons.today} lessons done` : 'all of today’s lessons are done');
  if (reviews.due) parts.push(`${plural(reviews.due, 'review')} due`);
  container.append(element('p', parts.length ? parts.join(', ') : 'Nothing is waiting for you today.', 'muted'));

  const today = element('div', '', 'card-grid wide');
  const lessonCard = element('article', '', 'card stack');
  lessonCard.append(element('h2', 'Today’s lessons'),
    element('p', lessons.today ? (left ? `${plural(left, 'lesson')} still to do.` : 'All done. Well done.') : 'No lessons were prepared today. A new one is made overnight for each topic you are learning.', 'muted'),
    link(left && lessons.completed_today ? 'Continue lessons' : left ? 'Start lessons' : 'See lessons', '#lessons', left ? 'primary' : ''));
  const reviewCard = element('article', '', 'card stack');
  reviewCard.append(element('h2', 'Reviews due now'),
    element('p', reviews.due ? `${plural(reviews.due, 'question')} ready.` : 'Nothing is due.', 'muted'),
    link(reviews.due ? 'Start reviews' : 'Browse questions', '#reviews', reviews.due ? 'primary' : ''));
  today.append(lessonCard, reviewCard);
  if (unfinished) {
    const examCard = element('article', '', 'card stack');
    examCard.append(element('h2', 'Unfinished exam'),
      element('p', `${unfinished.answered} of ${plural(unfinished.questions, 'question')} answered.`, 'muted'),
      link('Resume exam', '#exams', 'primary'));
    today.append(examCard);
  }
  container.append(today);

  // How you're doing
  container.append(element('h2', 'How you’re doing'));
  const answers = reviews.answers_last_30_days || {};
  const answered = Object.values(answers).reduce((sum, n) => sum + n, 0);
  const row = element('div', '', 'stat-row');
  row.append(stat(lessons.completed_on_day, 'Lessons done today'), stat(lessons.completed_last_7_days, 'Lessons done, 7 days'),
    stat(reviews.due, 'Reviews due'), stat(reviews.upcoming, 'Reviews coming up'), stat(reviews.total, 'Review questions'));
  container.append(row);

  const reviewBox = element('section', '', 'card stack');
  reviewBox.append(element('h2', 'Review answers, last 30 days'));
  if (answered) {
    const counts = element('div', '', 'stat-row');
    counts.append(stat(answers.correct || 0, 'Correct'), stat(answers.incorrect || 0, 'Incorrect'));
    const other = answered - (answers.correct || 0) - (answers.incorrect || 0);
    if (other) counts.append(stat(other, 'Not independently marked'));
    reviewBox.append(counts);
  } else reviewBox.append(element('p', 'No review answers yet.', 'muted'));
  container.append(reviewBox);

  const masteryBox = element('section', '', 'card stack');
  masteryBox.append(element('h2', 'Mastery by topic'),
    element('p', 'An estimate from your review answers, not a grade.', 'muted'));
  if (topics.length) {
    const list = element('div', '', 'stack');
    for (const topic of topics) {
      const line = element('div', '', 'toolbar');
      const meter = element('progress'); meter.max = 100; meter.value = Math.round(topic.mastery * 100);
      meter.setAttribute('aria-label', `${topic.topic} mastery`);
      line.append(element('span', `${topic.subject} · ${topic.topic}`, 'chip'), meter,
        element('span', topic.status === 'not_started' ? 'Not started' : `${Math.round(topic.mastery * 100)}%`, 'muted'));
      list.append(line);
    }
    masteryBox.append(list);
  } else masteryBox.append(element('p', 'Choose topics in Settings to see them here.', 'muted'));
  container.append(masteryBox);

  const weakBox = element('section', '', 'card stack');
  weakBox.append(element('h2', 'Weak concepts'),
    element('p', 'Tomorrow’s lesson will revisit these.', 'muted'));
  if (weak.length) {
    const list = element('ul');
    for (const item of weak) list.append(element('li', `${item.concept} (${item.topic})`));
    weakBox.append(list);
  } else weakBox.append(element('p', 'None yet. These appear after review answers.', 'muted'));
  container.append(weakBox);

  const examBox = element('section', '', 'card stack');
  examBox.append(element('h2', 'Recent exams'),
    element('p', 'Marks are AI-marked practice, unofficial, and not an NZQA grade.', 'muted'));
  if (exams.length) {
    const list = element('div', '', 'stack');
    for (const exam of exams) {
      const line = element('div', '', 'toolbar');
      const kind = exam.kind === 'ai_practice' ? 'AI practice (unofficial)' : exam.kind === 'mixed' ? 'Mixed practice' : 'Past paper';
      const result = exam.marked_questions
        ? `${exam.marks_awarded} / ${exam.marks_available} marks (${exam.marked_questions} of ${plural(exam.questions, 'question')} marked)`
        : `${exam.answered} of ${plural(exam.questions, 'question')} answered, not marked`;
      line.append(element('span', new Intl.DateTimeFormat('en-CA', { timeZone: 'Pacific/Auckland' }).format(new Date(exam.created_at)), 'chip'),
        element('span', kind, 'muted'), element('span', result));
      list.append(line);
    }
    examBox.append(list, link('Open exams', '#exams'));
  } else examBox.append(element('p', 'No exams yet.', 'muted'));
  container.append(examBox);
}
