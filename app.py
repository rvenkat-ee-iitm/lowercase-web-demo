import os
import time
import json
import random
from flask import Flask, render_template, request, redirect, url_for, session
from google import genai

# =====================================================
# FLASK SETUP
# =====================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

# =====================================================
# GEMINI CLIENT
# =====================================================
client = genai.Client()

# =====================================================
# QUESTION CATEGORIES (CONTROLLER-OWNED)
# =====================================================
QUESTION_CATEGORIES = [
    "grammar",
    "vocabulary_meaning",
    "sentence_paraphrase",
    "inference",
    "error_detection"
]

TOTAL_QUESTIONS = 10

# =====================================================
# SAFE GEMINI CALL
# =====================================================
def call_gemini(prompt):
    delay = 2
    for attempt in range(4):
        try:
            if attempt > 0:
                time.sleep(delay)
                delay *= 2

            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )

            if hasattr(response, "output_text") and response.output_text:
                return response.output_text.strip()

            if response.candidates:
                return response.candidates[0].content.parts[0].text.strip()

        except Exception:
            continue

    raise RuntimeError("Gemini unavailable")

# =====================================================
# NORMALIZE GEMINI OUTPUT (ROBUST)
# =====================================================
def normalize_question(data):
    # Schema A
    if "distractors" in data:
        return {
            "question": data["question"],
            "correct": data["correct_answer"],
            "distractors": data["distractors"],
            "explanation": data.get("explanation", "")
        }

    # Schema B
    if "options" in data:
        label = data["correct_answer"]
        options = data["options"]
        return {
            "question": data["question"],
            "correct": options[label],
            "distractors": [v for k, v in options.items() if k != label],
            "explanation": data.get("explanation", "")
        }

    raise ValueError("Unrecognized Gemini schema")

# =====================================================
# GENERATE QUESTION
# =====================================================
def generate_question(category, difficulty, qno):
    prompt = f"""
You are generating ONE English proficiency multiple-choice question.

Category: {category}
Difficulty Level: {difficulty} (1 = beginner, 10 = expert)

CATEGORY DEFINITIONS:
- grammar
- vocabulary_meaning
- sentence_paraphrase
- inference
- error_detection

DIFFICULTY GUIDELINES:
1–3: easy
4–6: medium
7–8: hard
9–10: expert

Use natural daily-life contexts.

Return JSON ONLY.
"""

    raw = call_gemini(prompt)
    data = json.loads(raw)
    return normalize_question(data)

# =====================================================
# SHUFFLE OPTIONS
# =====================================================
def shuffle_options(correct, distractors):
    options = distractors + [correct]
    random.shuffle(options)
    labels = ["A", "B", "C", "D"]
    option_map = dict(zip(labels, options))
    correct_label = next(k for k, v in option_map.items() if v == correct)
    return option_map, correct_label

# =====================================================
# ROUTES
# =====================================================

@app.route("/", methods=["GET", "POST"])
def start():
    session.clear()
    session["difficulty"] = 4
    session["qno"] = 1
    session["history"] = []
    session["categories"] = random.sample(
        QUESTION_CATEGORIES * 3, TOTAL_QUESTIONS
    )
    return render_template("start.html")

@app.route("/question", methods=["GET"])
def question():
    if session.get("qno", 1) > TOTAL_QUESTIONS:
        return redirect(url_for("result"))

    category = session["categories"][session["qno"] - 1]
    difficulty = session["difficulty"]

    q = generate_question(category, difficulty, session["qno"])
    options, correct_label = shuffle_options(
        q["correct"], q["distractors"]
    )

    session["current"] = {
        "correct_label": correct_label,
        "explanation": q["explanation"]
    }

    return render_template(
        "question.html",
        qno=session["qno"],
        difficulty=difficulty,
        q={"question": q["question"], "options": options}
    )

@app.route("/answer", methods=["POST"])
def answer():
    user_answer = request.form.get("answer")
    correct_label = session["current"]["correct_label"]

    correct = user_answer == correct_label
    session["history"].append((session["difficulty"], correct))

    if correct:
        session["difficulty"] = min(10, session["difficulty"] + 1)
    else:
        session["difficulty"] = max(1, session["difficulty"] - 1)

    session["qno"] += 1

    return render_template(
        "feedback.html",
        correct=correct,
        correct_label=correct_label,
        explanation=session["current"]["explanation"]
    )

@app.route("/result", methods=["GET"])
def result():
    history = session["history"]
    correct = sum(1 for _, c in history if c)
    avg_level = round(sum(d for d, _ in history) / len(history), 1)
    score = min(100, int(avg_level * 8 + correct * 2))

    return render_template(
        "result.html",
        avg_level=avg_level,
        accuracy=round(100 * correct / len(history), 1),
        score=score
    )

# =====================================================
# RENDER PORT BINDING
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

