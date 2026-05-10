// SPA logic for Vocabulary Trainer
// Assumes the HTML in templates/index.html defines the following IDs:
//   categoryBar  – container for category buttons
//   quizPanel    – panel showing the current question
//   feedbackPanel – panel showing previous result
//   currentTag   – badge displaying the current tag
//   sentence     – the fill‑in‑the‑blank sentence
//   optionsContainer – container for answer option cards
//   answerForm   – the form element handling answer submission

// Helper to create an element with optional classes and innerHTML
function el(tag, className, html) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (html) e.innerHTML = html;
  return e;
}

// Global state
let currentTag = null;
let previousResult = null; // {result, previous_word, definition, notes}

async function loadTags() {
  console.log('Loading tags...');
  const resp = await fetch('/api/tags');
  const tags = await resp.json();
  const bar = document.getElementById('categoryBar');
  bar.innerHTML = '';
  tags.forEach(tag => {
    const btn = el('button', 'category-btn', tag);
    btn.addEventListener('click', () => startQuiz(tag));
    bar.appendChild(btn);
  });
}

async function startQuiz(tag) {
  currentTag = tag;
  previousResult = null;
  // hide history panel until first answer
  document.getElementById('historyPanel').style.display = 'none';
  await loadQuestion(tag);
}

async function loadQuestion(tag) {
  const resp = await fetch(`/api/question/${encodeURIComponent(tag)}`);
  const data = await resp.json();
  renderQuiz(data);
}

function renderQuiz(data) {
  document.getElementById('quizPanel').style.display = 'block';
  document.getElementById('currentTag').textContent = data.tag;
  document.getElementById('sentence').textContent = data.sentence;
  const opts = document.getElementById('optionsContainer');
  opts.innerHTML = '';
  data.options.forEach(opt => {
    const label = el('label', 'option-card');
    const input = el('input');
    input.type = 'radio';
    input.name = 'selected_answer';
    input.value = opt;
    input.required = true;
    const span = el('span', null, opt);
    label.appendChild(input);
    label.appendChild(span);
    opts.appendChild(label);
  });

  // Store hidden data for the next API call
  document.getElementById('answerForm').dataset.definition = data.question.definition || '';
  document.getElementById('answerForm').dataset.notes = data.question.notes || '';
  document.getElementById('answerForm').dataset.correct = data.question.word;
  document.getElementById('answerForm').dataset.tag = data.tag;
}

async function submitAnswer(event) {
  event.preventDefault();
  const form = event.target;
  const selected = form.elements['selected_answer'].value;
  const payload = {
    selected_answer: selected,
    correct_answer: form.dataset.correct,
    definition: form.dataset.definition,
    notes: form.dataset.notes,
    tag: form.dataset.tag,
  };
  const resp = await fetch('/api/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await resp.json();
  // Show feedback
  showFeedback(result);
  // Load next question
  renderQuiz(result.next);
}

let history = [];
function renderHistory() {
  const list = document.getElementById('historyList');
  list.innerHTML = '';
  // Keep only latest 20 entries
  if (history.length > 20) {
    history = history.slice(-20);
  }
  // Show most recent first
  for (let i = history.length - 1; i >= 0; i--) {
    const item = history[i];
    const div = document.createElement('div');
    div.className = 'history-item';
    div.innerHTML = `<strong>${item.word}</strong> – ${item.result}<br><em>${item.definition}</em><br><small>${item.notes}</small>`;
    list.appendChild(div);
  }
}

function showFeedback(data) {
  // Add attempted word to history (displayed in Attempt History)
  history.push({
    word: data.previous_word,
    definition: data.definition,
    notes: data.notes,
    result: data.result
  });
  renderHistory();
  // Ensure history panel is visible
  document.getElementById('historyPanel').style.display = 'block';
}

// Attach handler
document.getElementById('answerForm').addEventListener('submit', submitAnswer);

// Initialise on page load
loadTags();
