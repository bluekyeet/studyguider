import { mathText } from './web-common.js';

export async function renderReviews(container, api) {
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const button = (text, className) => {
    const node = element('button', text, className);
    node.type = 'button';
    return node;
  };
  const heading = element('h1', 'Daily review');
  const toolbar = element('div', undefined, 'toolbar');
  const count = element('p', '', 'muted');
  const refresh = button('Refresh');
  const status = element('p');
  status.setAttribute('role', 'status');
  const content = element('div', undefined, 'stack');
  toolbar.append(count, refresh);
  container.replaceChildren(heading, toolbar, status, content);
  let questions = [];
  let loading = false;
  let submitting = false;
  const drafts = new Map();
  const labels = new Map();
  let labelsLoaded = false;

  async function loadLabels() {
    if (labelsLoaded) return;
    const subjects = await api('/subjects');
    await Promise.all(subjects.map(async subject => {
      const topics = await api(`/subjects/${subject.id}/topics`);
      for (const topic of topics) labels.set(topic.id, `${subject.name} / ${topic.name}`);
    }));
    labelsLoaded = true;
  }

  function showQuestion(focus = false) {
    content.replaceChildren();
    count.textContent = `${questions.length} question${questions.length === 1 ? '' : 's'} remaining`;
    if (!questions.length) {
      content.append(element('p', 'No questions are due. Come back later or refresh.', 'card'));
      return;
    }
    const question = questions[0];
    const card = element('section', undefined, 'card stack');
    const label = labels.get(question.topic_id) || `Topic ${question.topic_id}`;
    card.append(element('p', `${label} · Due ${question.due_date}`, 'muted'));
    if (question.concept) card.append(element('p', question.concept, 'muted'));
    const prompt = element('div');
    mathText(prompt, question.question);
    card.append(prompt);
    const form = element('form', undefined, 'stack');
    const answerLabel = element('label', 'Your answer', 'stack');
    const answer = element('textarea');
    answer.addEventListener('input', () => { container.dataset.dirty = String(!!answer.value.trim()); });
    answer.required = true;
    answer.maxLength = 50000;
    answer.rows = 6;
    const draft = drafts.get(question.id) || { answer: '', confidence: '' };
    answer.value = draft.answer;
    answerLabel.append(answer);
    const confidence = element('fieldset', undefined, 'fields');
    confidence.append(element('legend', 'How confident are you?'));
    const descriptions = ['Not confident', 'Slightly confident', 'Somewhat confident', 'Confident', 'Very confident'];
    for (let value = 1; value <= 5; value++) {
      const label = element('label');
      const input = element('input');
      input.type = 'radio';
      input.name = 'confidence';
      input.value = String(value);
      input.required = true;
      input.checked = draft.confidence === input.value;
      label.append(input, document.createTextNode(` ${value} — ${descriptions[value - 1]}`));
      confidence.append(label);
    }
    const saveDraft = () => {
      drafts.set(question.id, {
        answer: answer.value,
        confidence: form.querySelector('input[name="confidence"]:checked')?.value || '',
      });
    };
    form.addEventListener('input', saveDraft);
    form.addEventListener('change', saveDraft);
    const submit = button('Submit answer', 'primary');
    submit.type = 'submit';
    const feedback = element('div', undefined, 'stack');
    feedback.setAttribute('role', 'status');
    form.append(answerLabel, confidence, submit);
    card.append(form, feedback);
    content.append(card);
    if (focus) answer.focus();

    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (submitting || loading) return;
      answer.setCustomValidity(answer.value.trim() ? '' : 'Please enter an answer.');
      if (!form.reportValidity()) return;
      saveDraft();
      const selected = Number(drafts.get(question.id).confidence);
      if (!Number.isInteger(selected) || selected < 1 || selected > 5) return;
      submitting = true;
      container.dataset.busy = 'true';
      submit.disabled = true;
      refresh.disabled = true;
      answer.disabled = true;
      confidence.disabled = true;
      status.textContent = 'Saving and checking your answer…';
      try {
        const result = await api(`/review-questions/${question.id}/answers`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ answer: answer.value, confidence: selected }),
        });
        drafts.delete(question.id);
        container.dataset.dirty = 'false';
        const judgement = result.outcome === 'correct' ? 'AI judgement: correct (advisory).'
          : result.outcome === 'incorrect' ? 'AI judgement: incorrect (advisory).'
            : 'Not independently marked. Scheduled using your confidence.';
        feedback.append(element('p', judgement));
        if (result.feedback) {
          const explanation = element('div');
          mathText(explanation, result.feedback);
          feedback.append(explanation);
        }
        feedback.append(element('p', `Next due: ${result.next_due || 'not provided'}`));
        const mastery = typeof result.mastery === 'number' && Number.isFinite(result.mastery)
          ? `${Math.round(result.mastery * 100)}%` : 'not provided';
        feedback.append(element('p', `Topic mastery estimate: ${mastery}. This is a scheduling estimate, not proof of mastery.`, 'muted'));
        const next = button(questions.length > 1 ? 'Next question' : 'Finish review', 'primary');
        next.addEventListener('click', () => {
          questions.shift();
          status.textContent = '';
          showQuestion(true);
        });
        feedback.append(next);
        status.textContent = 'Answer saved.';
        next.focus();
      } catch (error) {
        status.textContent = `${error.message || 'Could not save your answer.'} Your draft is preserved. If the connection failed, the answer may already have been saved; refreshing checks the due list before you retry.`;
        submit.disabled = false;
        answer.disabled = false;
        confidence.disabled = false;
      } finally {
        submitting = false;
        container.dataset.busy = 'false';
        refresh.disabled = false;
      }
    });
    answer.addEventListener('input', () => answer.setCustomValidity(''));
  }

  async function load() {
    if (loading || submitting) return;
    loading = true;
    refresh.disabled = true;
    status.textContent = 'Loading due questions…';
    // ponytail: drafts live for this mounted view; persist only if cross-navigation recovery is needed.
    const date = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Pacific/Auckland', year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(new Date());
    const part = type => date.find(item => item.type === type).value;
    const asOf = `${part('year')}-${part('month')}-${part('day')}`;
    try {
      const [due, names] = await Promise.allSettled([
        api(`/review-questions/due?as_of=${asOf}`), loadLabels(),
      ]);
      if (due.status === 'rejected') throw due.reason;
      if (!Array.isArray(due.value)) throw new Error('Invalid due-question response.');
      questions = due.value;
      showQuestion();
      status.textContent = names.status === 'rejected' ? 'Some topic names could not be loaded. Questions are still available.' : '';
    } catch (error) {
      status.textContent = `${error.message || 'Could not load reviews.'} Any current draft is unchanged. Use Refresh to retry.`;
    } finally {
      loading = false;
      refresh.disabled = false;
    }
  }
  refresh.addEventListener('click', load);
  await load();
}
