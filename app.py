from flask import Flask, render_template, request, session, jsonify
import json
import random
import os

app = Flask(__name__)
app.secret_key = "vocab-secret-key"

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

    file_path = dataset["file"]

    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("words", [])

def get_tags(words):

    tags = set()

    for item in words:
        for tag in item["tags"]:
            tags.add(tag)

    return sorted(list(tags))

def get_question(dataset_id, tag):
    words = load_words(dataset_id)

    filtered_words = [
        item for item in words
        if tag in item["tags"]
    ]

    full_history = session.get(
        "full_history",
        []
    )

    attempted_words = [
        entry["word"]
        for entry in full_history
        if entry.get("tag") == tag
        and entry.get("dataset") == dataset_id
    ]

    remaining_words = [
        item for item in filtered_words
        if item["word"] not in attempted_words
    ]
    total_questions = len(filtered_words)
    completed_questions = len(attempted_words)
    if len(remaining_words) == 0:
        return None

    question = random.choice(
        remaining_words
    )

    sentence = question[
        "example"
    ].replace(
        question["word"],
        "______"
    )

    all_words = [
        w["word"]
        for w in words
        if w["word"] != question["word"]
    ]

    wrong_options = random.sample(
        all_words,
        min(3, len(all_words))
    )

    options = (
        wrong_options
        + [question["word"]]
    )

    random.shuffle(options)

    return {
        "question": question,
        "sentence": sentence,
        "options": options,
        "completed_questions":completed_questions,
        "total_questions":total_questions
    }

def get_completed_tags(dataset_id):
    completed = session.get(
        "completed_tags",
        {}
    )

    return completed.get(
        dataset_id,
        []
    )


def mark_tag_completed(dataset_id, tag):

    completed = session.get(
        "completed_tags",
        {}
    )

    dataset_completed = completed.get(
        dataset_id,
        []
    )

    if tag not in dataset_completed:
        dataset_completed.append(tag)

    completed[dataset_id] = (
        dataset_completed
    )

    session["completed_tags"] = (
        completed
    )


def get_next_uncompleted_tag(
    dataset_id,
    current_tag=None
):

    words = load_words(
        dataset_id
    )

    all_tags = get_tags(words)

    completed_tags = (
        get_completed_tags(
            dataset_id
        )
    )

    if current_tag is None:

        for tag in all_tags:

            if tag not in completed_tags:
                return tag

        return None

    try:

        current_index = (
            all_tags.index(current_tag)
        )

    except ValueError:

        current_index = -1

    for i in range(
        current_index + 1,
        len(all_tags)
    ):

        tag = all_tags[i]

        if tag not in completed_tags:
            return tag

    for i in range(
        0,
        current_index + 1
    ):

        tag = all_tags[i]

        if tag not in completed_tags:
            return tag

    return None

@app.route("/")
def home():

    session.clear()

    return render_template("index.html")

@app.route("/api/datasets")
def api_datasets():

    datasets = []

    for dataset_id, dataset in DATASETS.items():

        datasets.append({
            "id": dataset_id,
            "name": dataset["name"],
            "icon": dataset["icon"]
        })

    return jsonify(datasets)

@app.route("/api/tags/<dataset_id>")
def api_tags(dataset_id):

    words = load_words(dataset_id)

    tags = get_tags(words)

    return jsonify(tags)

@app.route("/api/question/<dataset_id>/<tag>")
def api_question(dataset_id, tag):

    quiz_data = get_question(
        dataset_id,
        tag
    )

    if quiz_data is None:

        return jsonify({
            "completed": True
        })

    return jsonify({
        "question": quiz_data["question"],
        "sentence": quiz_data["sentence"],
        "options": quiz_data["options"],
        "tag": tag,
        "completed_questions":quiz_data["completed_questions"],
        "total_questions":quiz_data["total_questions"]
    })

@app.route("/api/check", methods=["POST"])
def api_check():
    data = request.get_json()
    selected_answer = data.get("selected_answer")
    correct_answer = data.get("correct_answer")
    definition = data.get("definition")
    tag = data.get("tag")
    synonyms = data.get("synonyms").upper()
    dataset_id = data.get("dataset_id")

    result = (
        f"✅ Correct!   {correct_answer.upper()}"
        if selected_answer == correct_answer
        else f"❌ {selected_answer} - {correct_answer.upper()}"
    )

    full_history = session.get(
        "full_history",
        []
    )

    full_history.append({
        "word": correct_answer,
        "definition": definition,
        "synonyms": synonyms.upper(),
        "result": result,
        "tag": tag,
        "dataset": dataset_id
    })

    session["full_history"] = full_history

    next_data = get_question(
        dataset_id,
        tag
    )

    if next_data is None:

        mark_tag_completed(
            dataset_id,
            tag
        )

        next_tag = get_next_uncompleted_tag(
            dataset_id,
            tag
        )

        if next_tag is None:

            return jsonify({
                "completed": True,
                "message":
                    "🎉 All categories completed!"
            })

        next_data = get_question(
            dataset_id,
            next_tag
        )

        return jsonify({
            "result": result,
            "previous_word": correct_answer,
            "definition": definition,
            "category_completed": True,
            "next": {
                "question": next_data["question"],
                "sentence": next_data["sentence"],
                "options": next_data["options"],
                "tag": next_tag,
                 "completed_questions": next_data["completed_questions"],
                 "total_questions": next_data["total_questions"]
            }
        })

    return jsonify({
        "result": result,
        "previous_word": correct_answer,
        "definition": definition,
        "next": {
            "question": next_data["question"],
            "sentence": next_data["sentence"],
            "options": next_data["options"],
            "tag": tag,
            "completed_questions":next_data["completed_questions"],
            "total_questions": next_data["total_questions"]
        }
    })
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000,
        debug=True
    )