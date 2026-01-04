import os
import time
import json
import random
from flask import Flask, render_template, request, redirect, url_for, session

from google import genai

# ======================================================
# FLASK APP SETUP
# ======================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

TOTAL_QUESTIONS = 10

QUESTION_CATEGORIES = [
    "grammar",
    "vocabulary_meaning",
    "sentence_paraphrase",
    "inference",
    "error_detection"
]

# ======================================================
# GEMINI CLIENT
# ======================================================
client = genai.Client()

# ======================================================
# SAFE GEMINI CALL
# ======================================================
def call_gemini(prompt):
    delay = 2
    for attempt in range(4):
        try:
            if attempt > 0:
                time.sleep(delay)
                delay *= 2

            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )

            if hasattr(response, "output_text") and response.output_text:
                return response.output_text.strip()

            if (
                hasattr(response, "candidates")
                and response.candidates
                and response.candidates[0].content.parts
            ):
                return response.candidates[0].content.parts[0].text.strip()

        except (ServiceUnavailable, ResourceExhausted):
            continue

    return None

# ======================================================
# NORMALIZE GEMINI OUTPUT (NEVER RAISES)
# ======================================================
def normalize_question(data):
    question = data.get("question") or data.get("prompt")
    explanation = data.get("explanation", "No explanation provided.")

    # Schema A
    if "correct_answer" in data and "distractors" in data:
        return {
            "question": question,
            "correct": data["correct_answer"],
            "distractors": data["distractors"],
            "explanation": explanation
        }

    # Schema B
    if "options" in data and "correct_answer" in data:
        opts = data["options"]
        label = data["correct_answer"]
        if label in opts:
            return {
                "question": question,
                "correct": opts[label],
                "distractors": [v for k, v in opts.items() if k != label],
                "explanation": explanation
            }

    return None

# ======================================================
# QUESTION GENERATOR (REGENERATES SAFELY)
# ======================================================
def build_prompt(category, difficulty, qno):
    return f"""
You are generating ONE English proficiency multiple-choice question.

Category: {category}
Difficulty Level: {difficulty} (1 = beginner, 10 = expert)
Question number: {qno}

CATEGORY DEFINITIONS:
- grammar
- vocabulary_meaning
- sentence_paraphrase
- inference
- error_detection

DIFFICULTY:
1–3 simple
4–6 moderate
7–8 subtle
9–10 expert

Use everyday human contexts (not academic).

Return JSON using ONE of these schemas:

Schema A:
{{
  "question": "...",
  "correct_answer": "...",
  "distractors": ["...", "...", "..."],
  "explanation": "..."
}}

Schema B:
{{
  "question": "...",
  "options": {{
    "A": "...",
    "B": "...",
    "C": "...",
    "D": "..."
  }},
  "correct_answer": "A/B/C/D",
  "explanation": "..."
}}
"""

def generate_question(category, difficulty, qno):
    for _ in range(3):
        raw = call_gemini(build_prompt(category, difficulty, qno))
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        q = normalize_question(data)
        if q:
            return q

    # Absolute fallback (never crash)
    return {
        "question": "Choose the correct sentence.",
        "correct": "I am ready.",
        "distractors": [
            "I am read.",
            "I ready am.",
            "I being ready."
        ],
        "explanation": "Fallback question due to generation issues."
    }

# ======================================================
# SHUFFLE OPTIONS
# ======================================================
def shuffle_options(correct, distractors):
    options = distractors + [correct]
    random.shuffle(options)
    labels = ["A", "B", "C", "D"]
    option_map = dict(zip(labels, options))
    correct_label = next(k for k, v in option_map.items() if v == correct)
    return option_map, correct_label

# ======================================================
# ROUTES
# ======================================================
@app.route("/")
def home():
    return render_template("start.html")

@app.route("/start")
def start():
    session.clear()
    session["q_index"] = 0
    session["difficulty"] = 4
    session["history"] = []
    session["categories"] = random.sample(
        QUESTION_CATEGORIES, len(QUESTION_CATEGORIES)
    )
    return redirect(url_for("question"))

@app.route("/question")
def question():
    if "q_index" not in session:
        return redirect(url_for("start"))

    if session["q_index"] >= TOTAL_QUESTIONS:
        return redirect(url_for("result"))

    if "current_q" not in session:
        category = session["categories"][session["q_index"] % len(QUESTION_CATEGORIES)]
        difficulty = session["difficulty"]

        q = generate_question(category, difficulty, session["q_index"] + 1)
        options, correct_label = shuffle_options(q["correct"], q["distractors"])

        session["current_q"] = {
            "question": q["question"],
            "options": options,
            "correct_label": correct_label,
            "explanation": q["explanation"]
        }

    return render_template(
        "question.html",
        q=session["current_q"],
        qno=session["q_index"] + 1,
        difficulty=session["difficulty"]
    )

@app.route("/answer", methods=["POST"])
def answer():
    if "current_q" not in session:
        return redirect(url_for("question"))

    user_ans = request.form.get("answer")
    q = session["current_q"]

    is_correct = (user_ans == q["correct_label"])
    session["history"].append((session["difficulty"], is_correct))

    if is_correct:
        session["difficulty"] = min(10, session["difficulty"] + 1)
    else:
        session["difficulty"] = max(1, session["difficulty"] - 1)

    session["q_index"] += 1
    session.pop("current_q", None)

    return render_template(
        "feedback.html",
        correct=is_correct,
        correct_label=q["correct_label"],
        explanation=q["explanation"]
    )

@app.route("/result")
def result():
    history = session.get("history", [])
    if not history:
        return redirect(url_for("start"))

    correct = sum(1 for _, c in history if c)
    avg_level = round(sum(d for d, _ in history) / len(history), 1)
    score = min(100, int(avg_level * 8 + correct * 2))

    return render_template(
        "result.html",
        avg_level=avg_level,
        accuracy=round(100 * correct / len(history), 1),
        score=score
    )

# ======================================================
# RUN LOCAL
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

