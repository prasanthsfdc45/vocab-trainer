// ─── State (all owned by client — server is stateless) ────────────────────────
let currentDataset  = null;
let currentTag      = null;
let attemptedWords  = [];   // words answered in the CURRENT tag session
let history         = [];   // full display history across all tags
let isSubmitting    = false;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function el(tag, className, html) {
    const e = document.createElement(tag);
    if (className)       e.className = className;
    if (html !== undefined) e.innerHTML = html;
    return e;
}

function setSubmitEnabled(enabled) {
    const btn = document.querySelector(".submit-btn:not(.restart-btn)");
    if (!btn) return;
    btn.disabled    = !enabled;
    btn.style.opacity = enabled ? "1" : "0.5";
}

function showError(msg) {
    const box = document.getElementById("errorBox");
    box.textContent  = msg;
    box.style.display = "block";
    setTimeout(() => { box.style.display = "none"; }, 4000);
}

function showBanner(msg) {
    const b = document.getElementById("categoryBanner");
    b.textContent   = msg;
    b.style.display = "block";
    setTimeout(() => { b.style.display = "none"; }, 3000);
}

function clearFeedback() {
    document.getElementById("correctWord").textContent = "";
    document.getElementById("definition").textContent  = "";
    document.getElementById("synonyms").textContent    = "";
}

// ─── Dataset / tag loading ────────────────────────────────────────────────────

async function loadDatasets() {
    try {
        const resp     = await fetch("/api/datasets");
        if (!resp.ok)  throw new Error();
        const datasets = await resp.json();
        const bar      = document.getElementById("datasetBar");
        bar.innerHTML  = "";

        datasets.forEach(ds => {
            const btn = el("button", "category-btn", `${ds.icon} ${ds.name}`);
            btn.addEventListener("click", () => {
                document.querySelectorAll("#datasetBar .category-btn")
                    .forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                currentDataset = ds.id;
                currentTag     = null;
                loadTags(ds.id);
            });
            bar.appendChild(btn);
        });
    } catch {
        showError("Could not load datasets. Please refresh.");
    }
}

async function loadTags(datasetId) {
    try {
        const resp  = await fetch(`/api/tags/${datasetId}`);
        if (!resp.ok) throw new Error();
        const tags  = await resp.json();
        const bar   = document.getElementById("categoryBar");
        bar.innerHTML = "";

        document.getElementById("quizPanel").style.display    = "none";
        document.getElementById("historyPanel").style.display = "none";

        tags.forEach(tag => {
            const btn = el("button", "category-btn", tag);
            btn.addEventListener("click", () => {
                document.querySelectorAll("#categoryBar .category-btn")
                    .forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                startQuiz(tag);
            });
            bar.appendChild(btn);
        });
    } catch {
        showError("Could not load categories.");
    }
}

// ─── Quiz flow ────────────────────────────────────────────────────────────────

async function startQuiz(tag) {
    currentTag     = tag;
    attemptedWords = [];        // fresh list — tag click always starts at 0
    isSubmitting   = false;
    clearFeedback();
    document.getElementById("historyPanel").style.display = "none";
    document.getElementById("categoryBanner").style.display = "none";

    await loadFirstQuestion(tag);
}

async function loadFirstQuestion(tag) {
    try {
        const resp = await fetch("/api/question", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({
                dataset_id: currentDataset,
                tag:        tag,
                attempted:  attemptedWords   // [] on first load
            })
        });
        if (!resp.ok) throw new Error();
        const data = await resp.json();

        if (data.completed) {
            showCategoryComplete(tag);
            return;
        }
        renderQuiz(data);
    } catch {
        showError("Could not load question. Please try again.");
    }
}

// ─── Render ───────────────────────────────────────────────────────────────────

function renderQuiz(data) {
    if (!data) return;

    document.getElementById("quizPanel").style.display = "block";
    document.getElementById("currentTag").textContent  = data.tag || currentTag;

    // Progress
    const completed = data.completed_questions ?? 0;
    const total     = data.total_questions     ?? 1;
    const pct       = total > 0 ? Math.round((completed / total) * 100) : 0;
    document.getElementById("progressText").textContent   = `${completed} / ${total} completed`;
    document.getElementById("progressFill").style.width   = `${pct}%`;

    // Sentence
    document.getElementById("sentence").textContent = data.sentence;

    // Options
    const opts    = document.getElementById("optionsContainer");
    opts.innerHTML = "";
    data.options.forEach(opt => {
        const label = el("label", "option-card");
        const input = el("input");
        input.type  = "radio";
        input.name  = "selected_answer";
        input.value = opt;
        input.addEventListener("change", () => {
            document.querySelectorAll(".option-card")
                .forEach(c => c.classList.remove("selected"));
            label.classList.add("selected");
        });
        label.appendChild(input);
        label.appendChild(el("span", null, opt));
        opts.appendChild(label);
    });

    // Store question metadata on the form
    const form            = document.getElementById("answerForm");
    form.dataset.definition = data.question.definition || "";
    form.dataset.synonyms   = (data.question.synonyms  || []).join(", ");
    form.dataset.correct    = data.question.word;
    form.dataset.tag        = data.tag || currentTag;

    setSubmitEnabled(true);
}

// ─── Submit ───────────────────────────────────────────────────────────────────

async function submitAnswer(event) {
    event.preventDefault();
    if (isSubmitting) return;

    const form          = event.target;
    const selectedInput = form.elements["selected_answer"];
    if (!selectedInput?.value) { showError("Please select an answer."); return; }

    const selected     = selectedInput.value;
    const correctWord  = form.dataset.correct;

    isSubmitting = true;
    setSubmitEnabled(false);
    highlightOption(selected, correctWord);

    // Add to attempted BEFORE sending so server gets the updated list
    if (!attemptedWords.includes(correctWord)) {
        attemptedWords.push(correctWord);
    }

    const payload = {
        dataset_id:      currentDataset,
        tag:             form.dataset.tag,
        selected_answer: selected,
        correct_answer:  correctWord,
        definition:      form.dataset.definition,
        notes:           form.dataset.notes,
        synonyms:        form.dataset.synonyms,
        question:    document.getElementById("sentence").textContent,
        attempted:       [...attemptedWords],   // full list including just-answered word
    };

    try {
        const resp = await fetch("/api/check", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify(payload)
        });
        if (!resp.ok) throw new Error();
        const result = await resp.json();

        if (result.completed) {
            showFeedback(result);
            showAllComplete(result.message);
            return;
        }

        if (result.category_completed) {
            // Moving to a new tag — reset attempted list
            attemptedWords = [];
            currentTag     = result.next.tag;
            showBanner(`✅ Category done! Moving to: ${result.next.tag}`);
        }

        // Render next question FIRST, then paint feedback so right panel is never overwritten
        renderQuiz(result.next);
        showFeedback(result);
        isSubmitting = false;

    } catch {
        showError("Could not submit. Please try again.");
        // Roll back the attempted word we optimistically added
        attemptedWords = attemptedWords.filter(w => w !== correctWord);
        setSubmitEnabled(true);
        isSubmitting = false;
    }
}

// ─── Feedback ─────────────────────────────────────────────────────────────────

function showFeedback(data) {
    history.push({
        word:       data.previous_word,
        definition: data.definition,
        notes:      data.notes     || "",
        result:     data.result,
        synonyms:   data.synonyms  || ""
    });
    renderHistory();

    document.getElementById("correctWord").textContent = data.result       || "";
    document.getElementById("definition").textContent  = data.definition   || "";
    document.getElementById("prevQuestion").textContent  = data.previous_question  || "";
    document.getElementById("synonyms").textContent    = data.synonyms     || "";
    document.getElementById("historyPanel").style.display = "block";
}

function highlightOption(selected, correct) {
    document.querySelectorAll(".option-card").forEach(label => {
        const input = label.querySelector("input");
        if (!input) return;
        if (input.value === correct)                        label.classList.add("correct");
        else if (input.value === selected && selected !== correct) label.classList.add("wrong");
        input.disabled = true;
    });
}

function showCategoryComplete(tag) {
    document.getElementById("quizPanel").style.display  = "block";
    document.getElementById("sentence").textContent     = `✅ All words in "${tag}" completed!`;
    document.getElementById("optionsContainer").innerHTML = "";
    setSubmitEnabled(false);
}

function showAllComplete(message) {
    document.getElementById("quizPanel").style.display  = "block";
    document.getElementById("sentence").textContent     = message || "🎉 All categories completed!";
    document.getElementById("optionsContainer").innerHTML = "";
    clearFeedback();
    setSubmitEnabled(false);

    let btn = document.getElementById("restartBtn");
    if (!btn) {
        btn            = el("button", "submit-btn restart-btn", "🔄 Start Over");
        btn.id         = "restartBtn";
        btn.type       = "button";
        btn.addEventListener("click", restartQuiz);
        document.getElementById("answerForm").appendChild(btn);
    }
    btn.style.display = "inline-block";
}

// ─── History ──────────────────────────────────────────────────────────────────

function renderHistory() {
    const list     = document.getElementById("historyList");
    list.innerHTML = "";
    for (let i = history.length - 1; i >= 0; i--) {
        const item      = history[i];
        const isCorrect = item.result.startsWith("✅");
        const div       = document.createElement("div");
        div.className   = `history-item ${isCorrect ? "history-correct" : "history-wrong"}`;
        div.innerHTML   = `
            <strong>${item.word}</strong> — ${item.result}
            <br><br>${item.definition}
            ${item.synonyms ? `<br><br><strong>Synonyms:</strong> ${item.synonyms}` : ""}
            ${item.notes    ? `<br><em>${item.notes}</em>`                          : ""}
        `;
        list.appendChild(div);
    }
}

// ─── Restart ──────────────────────────────────────────────────────────────────

function restartQuiz() {
    attemptedWords = [];
    history        = [];
    currentTag     = null;
    currentDataset = null;
    isSubmitting   = false;

    document.getElementById("quizPanel").style.display    = "none";
    document.getElementById("historyPanel").style.display = "none";
    document.getElementById("categoryBar").innerHTML      = "";
    document.querySelectorAll("#datasetBar .category-btn")
        .forEach(b => b.classList.remove("active"));

    const restartBtn = document.getElementById("restartBtn");
    if (restartBtn) restartBtn.style.display = "none";
}

// ─── Init ─────────────────────────────────────────────────────────────────────

document.getElementById("answerForm").addEventListener("submit", submitAnswer);
loadDatasets();