from flask import Flask, render_template, request, session, jsonify, redirect, url_for
import json
import random

app = Flask(__name__)
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


# GET COMPLETED TAGS FROM SESSION
def get_completed_tags():
    return session.get("completed_tags", [])


# MARK TAG AS COMPLETED
def mark_tag_completed(tag):

    completed_tags = get_completed_tags()

    if tag not in completed_tags:

        completed_tags.append(tag)

        session["completed_tags"] = completed_tags


# GET NEXT UNCOMPLETED TAG
def get_next_uncompleted_tag(current_tag=None):

    words = load_words()

    all_tags = get_tags(words)

    completed_tags = get_completed_tags()

    # START FROM FIRST UNCOMPLETED
    if current_tag is None:

        for tag in all_tags:

            if tag not in completed_tags:

                return tag

        return None

    # FIND CURRENT TAG INDEX
    try:

        current_index = all_tags.index(current_tag)

    except ValueError:

        current_index = -1

    # LOOK FOR NEXT UNCOMPLETED TAG
    for i in range(current_index + 1, len(all_tags)):

        tag = all_tags[i]

        if tag not in completed_tags:

            return tag

    # CHECK EARLIER TAGS
    for i in range(0, current_index + 1):

        tag = all_tags[i]

        if tag not in completed_tags:

            return tag

    return None


# API: RETURN TAGS
@app.route("/api/tags")
def api_tags():

    words = load_words()

    tags = get_tags(words)

    return jsonify(tags)


# GET QUESTION WITHOUT REPEATING
def get_question(tag):

    words = load_words()

    # FILTER WORDS BY TAG
    filtered_words = [

        item for item in words

        if tag in item["tags"]
    ]

    # SESSION HISTORY
    attempt_history = session.get("attempt_history", [])

    attempted_words = [

        entry["word"]

        for entry in attempt_history
    ]

    # REMAINING WORDS
    remaining_words = [

        item for item in filtered_words

        if item["word"] not in attempted_words
    ]

    # CATEGORY COMPLETED
    if len(remaining_words) == 0:

        return None

    # PICK RANDOM QUESTION
    question = random.choice(remaining_words)

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


# API: GET QUESTION
@app.route("/api/question/<tag>")
def api_question(tag):

    quiz_data = get_question(tag)

    # CATEGORY FINISHED
    if quiz_data is None:

        mark_tag_completed(tag)

        next_tag = get_next_uncompleted_tag(tag)

        # RESET FOR NEXT CATEGORY
        session["attempt_history"] = []

        if next_tag is None:

            return jsonify({
                "completed": True,
                "message": "🎉 All categories completed!"
            })

        quiz_data = get_question(next_tag)

        return jsonify({

            "question": quiz_data["question"],

            "sentence": quiz_data["sentence"],

            "options": quiz_data["options"],

            "tag": next_tag,

            "category_completed": True
        })

    return jsonify({

        "question": quiz_data["question"],

        "sentence": quiz_data["sentence"],

        "options": quiz_data["options"],

        "tag": tag
    })


# API: CHECK ANSWER
@app.route("/api/check", methods=["POST"])
def api_check():

    data = request.get_json()

    selected_answer = data.get("selected_answer")

    correct_answer = data.get("correct_answer")

    definition = data.get("definition")

    notes = data.get("notes")

    tag = data.get("tag")

    # RESULT
    result = (

        "✅ Correct!"

        if selected_answer == correct_answer

        else f"❌ Wrong!\nCorrect Answer: {correct_answer}"
    )

    # SAVE ATTEMPT
    attempt_history = session.get("attempt_history", [])

    attempt_history.append({

        "word": correct_answer,

        "result": (

            "Correct"

            if selected_answer == correct_answer

            else "Wrong"
        )
    })

    session["attempt_history"] = attempt_history

    # NEXT QUESTION
    next_data = get_question(tag)

    # CATEGORY FINISHED
    if next_data is None:

        mark_tag_completed(tag)

        next_tag = get_next_uncompleted_tag(tag)

        # RESET HISTORY
        session["attempt_history"] = []

        # ALL CATEGORIES DONE
        if next_tag is None:

            return jsonify({

                "completed": True,

                "message": "🎉 All categories completed!"
            })

        next_data = get_question(next_tag)

        return jsonify({

            "result": result,

            "previous_word": correct_answer,

            "definition": definition,

            "notes": notes,

            "category_completed": True,

            "next": {

                "question": next_data["question"],

                "sentence": next_data["sentence"],

                "options": next_data["options"],

                "tag": next_tag
            }
        })

    # NORMAL FLOW
    return jsonify({

        "result": result,

        "previous_word": correct_answer,

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

    # CATEGORY COMPLETED
    if quiz_data is None:

        mark_tag_completed(tag)

        next_tag = get_next_uncompleted_tag(tag)

        # RESET HISTORY
        session["attempt_history"] = []

        # ALL TAGS COMPLETED
        if next_tag is None:

            return render_template(
                "completed.html"
            )

        return redirect(
            url_for(
                "quiz",
                tag=next_tag
            )
        )

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

    # SAVE ATTEMPT
    attempt_history = session.get("attempt_history", [])

    attempt_history.append({

        "word": correct_answer,

        "result": (

            "Correct"

            if selected_answer == correct_answer

            else "Wrong"
        )
    })

    session["attempt_history"] = attempt_history

    # NEXT QUESTION
    quiz_data = get_question(tag)

    # CATEGORY COMPLETED
    if quiz_data is None:

        mark_tag_completed(tag)

        next_tag = get_next_uncompleted_tag(tag)

        # RESET HISTORY
        session["attempt_history"] = []

        # ALL TAGS COMPLETED
        if next_tag is None:

            return render_template(
                "completed.html"
            )

        return redirect(
            url_for(
                "quiz",
                tag=next_tag
            )
        )

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

    app.run(
        host="0.0.0.0",
        port=10000,
        debug=True
    )