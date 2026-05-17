function el(tag, className, html) {
  const e = document.createElement(tag);

  if (className) {
      e.className = className;
  }

  if (html) {
      e.innerHTML = html;
  }

  return e;
}

let currentDataset = null;

let currentTag = null;

let history = [];

async function loadDatasets() {

  const resp = await fetch("/api/datasets");

  const datasets = await resp.json();

  const bar = document.getElementById("datasetBar");

  bar.innerHTML = "";

  datasets.forEach(dataset => {

      const btn = el(
          "button",
          "category-btn",
          `${dataset.icon} ${dataset.name}`
      );

      btn.addEventListener("click", () => {

          currentDataset = dataset.id;

          loadTags(dataset.id);
      });

      bar.appendChild(btn);
  });
}

async function loadTags(datasetId) {

  const resp = await fetch(
      `/api/tags/${datasetId}`
  );

  const tags = await resp.json();

  const bar = document.getElementById("categoryBar");

  bar.innerHTML = "";

  tags.forEach(tag => {

      const btn = el(
          "button",
          "category-btn",
          tag
      );

      btn.addEventListener("click", () => {
          startQuiz(tag);
      });

      bar.appendChild(btn);
  });
}

async function startQuiz(tag) {

  currentTag = tag;

  document.getElementById(
      "historyPanel"
  ).style.display = "none";

  await loadQuestion(tag);
}

async function loadQuestion(tag) {

  const resp = await fetch(
      `/api/question/${currentDataset}/${encodeURIComponent(tag)}`
  );

  const data = await resp.json();

  renderQuiz(data);
}

function renderQuiz(data) {

  document.getElementById(
      "quizPanel"
  ).style.display = "block";

  document.getElementById(
      "currentTag"
  ).textContent = data.tag;
  const completed =
    data.completed_questions;

    const total =
        data.total_questions;

    const percent =
        Math.round(
            (completed / total) * 100
        );

    document.getElementById(
        "progressText"
    ).textContent =
        `${completed} / ${total} completed`;

    document.getElementById(
        "progressFill"
    ).style.width =
        `${percent}%`;

  document.getElementById(
      "sentence"
  ).textContent = data.sentence;

  const opts = document.getElementById(
      "optionsContainer"
  );

  opts.innerHTML = "";

  data.options.forEach(opt => {

      const label = el(
          "label",
          "option-card"
      );

      const input = el("input");

      input.type = "radio";

      input.name = "selected_answer";

      input.value = opt;

      input.required = true;

      const span = el(
          "span",
          null,
          opt
      );

      label.appendChild(input);

      label.appendChild(span);

      opts.appendChild(label);
  });

  const form = document.getElementById(
      "answerForm"
  );

  form.dataset.definition =
      data.question.definition || "";

  form.dataset.notes =
      data.question.notes || "";
  form.dataset.synonyms =
      (data.question.synonyms || []).join(", ");
  form.dataset.correct =
      data.question.word;

  form.dataset.tag =
      data.tag;
}

async function submitAnswer(event) {

  event.preventDefault();

  const form = event.target;

  const selected =
      form.elements["selected_answer"].value;

  const payload = {

      dataset_id: currentDataset,

      selected_answer: selected,

      correct_answer: form.dataset.correct,

      definition: form.dataset.definition,

      notes: form.dataset.notes,

      tag: form.dataset.tag,
      synonyms: form.dataset.synonyms
  };

  const resp = await fetch(
      "/api/check",
      {
          method: "POST",

          headers: {
              "Content-Type": "application/json"
          },

          body: JSON.stringify(payload)
      }
  );

  const result = await resp.json();
  result["synonyms"] = form.dataset.synonyms;
  showFeedback(result);

  renderQuiz(result.next);
}

function renderHistory() {

  const list = document.getElementById(
      "historyList"
  );

  list.innerHTML = "";

  for (
      let i = history.length - 1;
      i >= 0;
      i--
  ) {

      const item = history[i];

      const div = document.createElement("div");

      div.className = "history-item";

      div.innerHTML = `
          <strong>${item.word}</strong>
          – ${item.result}
          <br><br>
          ${item.definition}
          <br><br>
          <strong>Synonyms: ${item.synonyms}</strong>
      `;

      list.appendChild(div);
  }
}

function showFeedback(data) {

  history.push({

      word: data.previous_word,

      definition: data.definition,

      notes: data.notes,

      result: data.result,
      
      synonyms : data.synonyms
  });

  renderHistory();
    document.getElementById(
        "correctWord"
    ).textContent = data.result;
    document.getElementById(
        "definition"
    ).textContent = data.definition;
    document.getElementById(
        "synonyms"
    ).textContent = data.synonyms || "";

  document.getElementById(
      "historyPanel"
  ).style.display = "block";
}

document
  .getElementById("answerForm")
  .addEventListener(
      "submit",
      submitAnswer
  );

loadDatasets();