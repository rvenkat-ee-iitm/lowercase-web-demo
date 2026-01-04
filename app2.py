import os
from flask import Flask, request, jsonify, render_template, session
from google import genai

app = Flask(__name__)
app.secret_key = "temporary-secret-key"

# --------------------------------
# Gemini client
# --------------------------------
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# --------------------------------
# Helpers
# --------------------------------
def init_session():
    if "index" not in session:
        session["index"] = 0
        session["score"] = 0

def generate_question(difficulty=5):
    prompt = f"""
You are creating ONE multiple-choice English proficiency question.

Difficulty level: {difficulty} (1 = very easy, 10 = very hard)

Rules:
- Focus ONLY on grammar or word meaning
- Everyday contexts (not academic, not research)
- Exactly 4 options labeled A, B, C, D
- Only ONE correct answer

Return EXACTLY in this JSON format:

{{
  "question": "...",
  "options": {{
    "A": "...",
    "B": "...",
    "C": "...",
    "D": "..."
  }},
  "correct": "A",
  "explanation": "..."
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )

    return response.parsed

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

    if session["index"] >= 5:
        return jsonify({"done": True})

    q = generate_question(difficulty=5)

    # store correct answer for this question
    session["current_correct"] = q["correct"]

    return jsonify({
        "done": False,
        "question": q["question"],
        "options": q["options"],
        "number": session["index"] + 1,
        "total": 5
    })

@app.route("/answer", methods=["POST"])
def submit_answer():
    init_session()

    data = request.get_json()
    selected = data.get("answer")

    if selected == session.get("current_correct"):
        session["score"] += 1

    session["index"] += 1
    return jsonify({"ok": True})

@app.route("/result")
def result():
    return jsonify({
        "score": session["score"],
        "total": 5
    })

# --------------------------------
# Run
# --------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

