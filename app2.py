from flask import Flask, request, jsonify, render_template, session

app = Flask(__name__)

# --------------------------------
# REQUIRED for sessions
# --------------------------------
app.secret_key = "temporary-secret-key"  # replace later for production

# --------------------------------
# Static Question Bank
# --------------------------------
QUESTIONS = [
    {
        "question": "Choose the correct sentence.",
        "options": {
            "A": "She don't like coffee.",
            "B": "She doesn't like coffee.",
            "C": "She didn't likes coffee.",
            "D": "She don't likes coffee."
        },
        "correct": "B"
    },
    {
        "question": "What does 'meticulous' most nearly mean?",
        "options": {
            "A": "Careless",
            "B": "Quick",
            "C": "Very careful",
            "D": "Aggressive"
        },
        "correct": "C"
    },
    {
        "question": "Identify the correct usage.",
        "options": {
            "A": "He is senior than me.",
            "B": "He is senior to me.",
            "C": "He is senior from me.",
            "D": "He is senior over me."
        },
        "correct": "B"
    },
    {
        "question": "Choose the best replacement: 'She spoke ______.'",
        "options": {
            "A": "confident",
            "B": "confidence",
            "C": "confidently",
            "D": "confidencing"
        },
        "correct": "C"
    },
    {
        "question": "Which sentence is grammatically correct?",
        "options": {
            "A": "Neither of the answers are correct.",
            "B": "Neither of the answers is correct.",
            "C": "Neither answers are correct.",
            "D": "Neither answer were correct."
        },
        "correct": "B"
    }
]

# --------------------------------
# Helpers
# --------------------------------
def init_session():
    if "index" not in session:
        session["index"] = 0
        session["score"] = 0

# --------------------------------
# Routes
# --------------------------------
@app.route("/")
def home():
    init_session()
    return render_template("quiz.html")

@app.route("/question")
def get_question():
    init_session()

    idx = session["index"]
    if idx >= len(QUESTIONS):
        return jsonify({"done": True})

    q = QUESTIONS[idx]
    return jsonify({
        "done": False,
        "question": q["question"],
        "options": q["options"],
        "number": idx + 1,
        "total": len(QUESTIONS)
    })

@app.route("/answer", methods=["POST"])
def submit_answer():
    init_session()

    data = request.get_json()
    selected = data.get("answer")

    idx = session["index"]
    correct = QUESTIONS[idx]["correct"]

    if selected == correct:
        session["score"] += 1

    session["index"] += 1
    return jsonify({"ok": True})

@app.route("/result")
def result():
    init_session()
    return jsonify({
        "score": session["score"],
        "total": len(QUESTIONS)
    })

# --------------------------------
# Run
# --------------------------------
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

