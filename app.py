from flask import Flask, render_template, request, session, jsonify
import json
import random

app = Flask(__name__)

# SESSION SECRET
app.secret_key = "vocab-secret-key"


# LOAD VOCABULARY FILE
def load_words():

    with open("words.json") as f:

        data = json.load(f)

        return data["words"]


# GET UNIQUE TAGS
def get_tags(words):

    tags = set()

    for item in words:

        for tag in item["tags"]:

            tags.add(tag)

    return sorted(list(tags))

# API: return tags as JSON
@app.route("/api/tags")
def api_tags():
    words = load_words()
    tags = get_tags(words)
    return jsonify(tags)



# GET QUESTION WITHOUT REPEATING
def get_question(tag):

    words = load_words()

    # FILTER BY TAG
    filtered_words = []

    for item in words:

        if tag in item["tags"]:

            filtered_words.append(item)

    # SESSION STORAGE
    asked_words = session.get("asked_words", [])

    # REMOVE ASKED WORDS
    remaining_words = []

    for item in filtered_words:

        if item["word"] not in asked_words:

            remaining_words.append(item)

    # RESET WHEN FINISHED
    if len(remaining_words) == 0:

        asked_words = []

        session["asked_words"] = []

        remaining_words = filtered_words

    # PICK RANDOM QUESTION
    question = random.choice(remaining_words)

    # STORE QUESTION
    asked_words.append(question["word"])

    session["asked_words"] = asked_words

    # CREATE BLANK SENTENCE
    sentence = question["example"].replace(
        question["word"],
        "______"
    )

    # CREATE OPTIONS
    all_words = [
        w["word"]
        for w in words
        if w["word"] != question["word"]
    ]

    wrong_options = random.sample(all_words, 3)

    options = wrong_options + [question["word"]]

    random.shuffle(options)

    return {
        "question": question,
        "sentence": sentence,
        "options": options
    }


# HOME PAGE
@app.route("/")
def home():

    session.clear()

    return render_template(
        "index.html"
    )

# API: return a question for a tag
@app.route("/api/question/<tag>")
def api_question(tag):
    quiz_data = get_question(tag)
    return jsonify({
        "question": quiz_data["question"],
        "sentence": quiz_data["sentence"],
        "options": quiz_data["options"],
        "tag": tag
    })

# API: check answer and get next question
@app.route("/api/check", methods=["POST"])
def api_check():
    data = request.get_json()
    selected = data.get("selected_answer")
    correct = data.get("correct_answer")
    definition = data.get("definition")
    notes = data.get("notes")
    tag = data.get("tag")
    result = "✅ Correct!" if selected == correct else f"❌ Wrong!\nCorrect Answer: {correct}"
    # fetch next question ensuring it's not the same as the just‑answered one
    next_data = get_question(tag)
    attempts = 0
    while next_data["question"]["word"] == correct and attempts < 10:
        next_data = get_question(tag)
        attempts += 1
    return jsonify({
        "result": result,
        "previous_word": correct,
        "definition": definition,
        "notes": notes,
        "next": {
            "question": next_data["question"],
            "sentence": next_data["sentence"],
            "options": next_data["options"],
            "tag": tag
        }
    })


# QUIZ PAGE
@app.route("/quiz/<tag>")
def quiz(tag):

    quiz_data = get_question(tag)

    return render_template(
        "quiz.html",
        question=quiz_data["question"],
        sentence=quiz_data["sentence"],
        options=quiz_data["options"],
        tag=tag,
        result=None,
        previous_word=None,
        definition=None,
        notes=None
    )


# CHECK ANSWER + LOAD NEXT QUESTION
@app.route("/check", methods=["POST"])
def check():

    selected_answer = request.form["selected_answer"]

    correct_answer = request.form["correct_answer"]

    definition = request.form["definition"]

    notes = request.form["notes"]

    tag = request.form["tag"]

    # CHECK RESULT
    if selected_answer == correct_answer:

        result = "✅ Correct!"

    else:

        result = f"""
        ❌ Wrong!<br><br>
        Correct Answer: <b>{correct_answer}</b>
        """

    # GET NEW QUESTION
    quiz_data = get_question(tag)

    # ENSURE DIFFERENT QUESTION
    attempts = 0

    while (
        quiz_data["question"]["word"] == correct_answer
        and attempts < 10
    ):

        quiz_data = get_question(tag)

        attempts += 1

    return render_template(
        "quiz.html",
        question=quiz_data["question"],
        sentence=quiz_data["sentence"],
        options=quiz_data["options"],
        tag=tag,
        result=result,
        previous_word=correct_answer,
        definition=definition,
        notes=notes
    )


# START SERVER
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)