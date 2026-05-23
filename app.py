from flask import Flask, render_template, request, jsonify
import json
import random
import os

app = Flask(__name__)
app.secret_key = "vocab-secret-key"

# ─── No session used anywhere. Server is fully stateless. ────────────────────
# The client tracks all attempted words and sends them with every request.
# This eliminates: cookie overflow, multi-worker desync, session mutation bugs,
# stale progress, and duplicate questions — permanently.

DATASETS = {
    "vocabulary": {
        "name": "Vocabulary Trainer",
        "icon": "📘",
        "file": "data/vocab_words.json"
    },
    "leadership": {
        "name": "Personal Vocabulary",
        "icon": "👔",
        "file": "data/personal_words.json"
    },
    "architecture": {
        "name": "Architecture Vocabulary",
        "icon": "🏗️",
        "file": "data/architecture_words.json"
    }
}


def load_words(dataset_id):
    dataset = DATASETS.get(dataset_id)
    if not dataset:
        return []
    file_path = os.path.join(os.path.dirname(__file__), dataset["file"])
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data if isinstance(data, list) else data.get("words", [])


def get_tags(words):
    tags = set()
    for item in words:
        for tag in item.get("tags", []):
            tags.add(tag)
    return sorted(list(tags))


def pick_question(words, tag, attempted_set):
    """
    Pick a random unanswered question for the given tag.
    attempted_set: set of word strings already answered by the client.
    Returns dict or None if all done.
    """
    filtered = [w for w in words if tag in w.get("tags", [])]
    if not filtered:
        return None

    remaining = [w for w in filtered if w["word"] not in attempted_set]
    total     = len(filtered)
    completed = len(attempted_set & {w["word"] for w in filtered})

    if not remaining:
        return None

    question = random.choice(remaining)
    sentence = question.get("example", "")

    same_tag_pool  = [w["word"] for w in filtered   if w["word"] != question["word"]]
    all_other_pool = [w["word"] for w in words       if w["word"] != question["word"]]
    pool           = same_tag_pool if len(same_tag_pool) >= 3 else all_other_pool
    wrong_options  = random.sample(pool, min(3, len(pool)))

    options = wrong_options + [question["word"]]
    random.shuffle(options)

    return {
        "question":            question,
        "sentence":            sentence,
        "options":             options,
        "completed_questions": completed,
        "total_questions":     total,
    }


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/datasets")
def api_datasets():
    return jsonify([
        {"id": did, "name": d["name"], "icon": d["icon"]}
        for did, d in DATASETS.items()
    ])


@app.route("/api/tags/<dataset_id>")
def api_tags(dataset_id):
    return jsonify(get_tags(load_words(dataset_id)))


@app.route("/api/question", methods=["POST"])
def api_question():
    """
    Body: { dataset_id, tag, attempted: ["word1", "word2", ...] }
    attempted is the client's full list of answered words for this tag.
    Returns the next question or {completed: true}.
    """
    body       = request.get_json()
    dataset_id = body.get("dataset_id", "")
    tag        = body.get("tag", "")
    attempted  = set(body.get("attempted", []))   # client owns this list

    words = load_words(dataset_id)
    data  = pick_question(words, tag, attempted)

    if data is None:
        return jsonify({"completed": True})

    return jsonify({
        "question":            data["question"],
        "sentence":            data["sentence"],
        "options":             data["options"],
        "tag":                 tag,
        "completed_questions": data["completed_questions"],
        "total_questions":     data["total_questions"],
    })


@app.route("/api/check", methods=["POST"])
def api_check():
    """
    Body: {
        dataset_id, tag,
        selected_answer, correct_answer,
        definition, notes, synonyms,question,
        attempted: ["word1", ...]     <- already includes correct_answer
    }
    Server picks the next question using the updated attempted list sent by client.
    """
    body            = request.get_json()
    selected_answer = body.get("selected_answer", "")
    correct_answer  = body.get("correct_answer", "")
    definition      = body.get("definition", "")
    question           = body.get("question", "gfgf")
    notes           = body.get("notes", "")
    tag             = body.get("tag", "")
    synonyms        = (body.get("synonyms") or "").upper()
    dataset_id      = body.get("dataset_id", "")
    # Client sends attempted list that ALREADY includes correct_answer
    attempted       = set(body.get("attempted", []))

    is_correct = selected_answer == correct_answer
    result = (
        f"✅ Correct!  {correct_answer.upper()}"
        if is_correct
        else f"❌ {selected_answer.upper()} → {correct_answer.upper()}"
    )

    words    = load_words(dataset_id)
    all_tags = get_tags(words)

    feedback = {
        "result":        result,
        "previous_word": correct_answer,
        "previous_question": question,
        "definition":    definition,
        "notes":         notes,
        "synonyms":      synonyms,
    }

    # Try next question in same tag
    next_data = pick_question(words, tag, attempted)

    if next_data is not None:
        return jsonify({
            **feedback,
            "next": {
                "question":            next_data["question"],
                "sentence":            next_data["sentence"],
                "options":             next_data["options"],
                "tag":                 tag,
                "completed_questions": next_data["completed_questions"],
                "total_questions":     next_data["total_questions"],
            }
        })

    # Current tag exhausted — find next tag that still has unanswered words.
    # Client sends attempted words for current tag only, so for other tags
    # attempted is empty (they haven't started them). That's correct — we
    # want to start the next tag from scratch.
    try:
        current_idx = all_tags.index(tag)
    except ValueError:
        current_idx = -1

    search_order = (
        list(range(current_idx + 1, len(all_tags))) +
        list(range(0, current_idx + 1))
    )

    for i in search_order:
        next_tag  = all_tags[i]
        if next_tag == tag:
            continue
        next_data = pick_question(words, next_tag, set())   # fresh start for new tag
        if next_data is not None:
            return jsonify({
                **feedback,
                "category_completed": True,
                "next": {
                    "question":            next_data["question"],
                    "sentence":            next_data["sentence"],
                    "options":             next_data["options"],
                    "tag":                 next_tag,
                    "completed_questions": next_data["completed_questions"],
                    "total_questions":     next_data["total_questions"],
                }
            })

    # Every tag is done
    return jsonify({**feedback, "completed": True,
                    "message": "🎉 All categories completed!"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)