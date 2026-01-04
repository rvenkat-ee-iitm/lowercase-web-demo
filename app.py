import os
import time
import random
import json
from flask import Flask, render_template, request, redirect, url_for, session

from google import genai

# ======================================================
# Flask setup
# ======================================================
app = Flask(__name__)
app.secret_key = "change-this-secret-key"

# ======================================================
# Gemini client
# ======================================================
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# ======================================================
# Constants
# ======================================================
QUESTION_CATEGORIES = [
    "grammar",
    "vocabulary_meaning",
    "sentence_paraphrase",
    "inference",
    "error_detection"
]

TOTAL_QUESTIONS = 10

# ======================================================
# Gemini call (robust)
# ======================================================
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

            if response.candidates and response.candidates[0].content.parts:
                return response.candidates[0].content.parts[0].text.strip()

        except Exception as e:
            print("Gemini error:", e)
            continue

    return None


# ======================================================
# Normalize Gemini output (CRITICAL)
# ======================================================
def normalize_question(data):
    # Schema A
    if "distractors" in data:
        return {
            "question": data["question"],
            "correct_answer": data["correct_answer"],
            "distractors": data["distractors"],
            "explanation": data.get("explanation", "")
        }

    # Schema B (options + label)
    if "options" in data:
        label = data.get("correct_answer") or data.get("correct")
        options = data["options"]

        return {
            "question": data["question"],
            "correct_answer": options[label],
            "distractors": [v for k, v in options.items() if k != label],
            "explanation": data.get("explanation", "")
        }

    raise ValueError("Unrecognized Gemini schema")


# ======================================================
# Question generator
# ======================================================
def generate_question(category, difficulty, qno):
    prompt = f"""
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

DIFFICULTY GUIDELINES:
1–3: simple
4–6: moderate
7–8: subtle
9–10: expert

Use natural human contexts. Avoid academic tone.

OUTPUT JSON ONLY.

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
  "correct": "A/B/C/D",
  "explanation": "..."
}}
"""

    raw = call_gemini(prompt)
    if not raw:
        raise RuntimeError("Gemini unavailable")

    data = json.loads(raw)
    return normalize_question(data)


# ======================================================
# Shuffle options
# ======================================================
def shuffle_options(correct, distractors):
    options = distractors + [correct]
    random.shuffle(options)

    labels = ["A", "B", "C", "D"]
    option_map = dict(zip(labels, options))
    correct_label = next(k for k, v in option_map.items() if v == correct)

    return option_map, correct_label


# ======================================================
# Routes
# ======================================================
@app.route("/", methods=["GET", "POST"])
def start():
    if request.method == "POST":
        session.clear()
        session["qno"] = 0
        session["difficulty"] = 4
        session["history"] = []
        session["categories"] = random.sample(
            QUESTION_CATEGORIES, len(QUESTION_CATEGORIES)
        )
        return redirect(url_for("question"))

    return render_template("start.html")


@app.route("/question")
def question():
    if session["qno"] >= TOTAL_QUESTIONS:
        return redirect(url_for("result"))

    category = session["categories"][session["qno"] % len(QUESTION_CATEGORIES)]
    difficulty = session["difficulty"]

    q = generate_question(category, difficulty, session["qno"] + 1)

    options, correct_label = shuffle_options(
        q["correct_answer"], q["distractors"]
    )

    session["current_correct"] = correct_label
    session["current_explanation"] = q["explanation"]
    session["qno"] += 1

    return render_template(
        "question.html",
        qno=session["qno"],
        difficulty=difficulty,
        q={"question": q["question"], "options": options}
    )


@app.route("/answer", methods=["POST"])
def answer():
    user_ans = request.form.get("answer")
    correct_label = session.get("current_correct")

    correct = user_ans == correct_label
    session["history"].append((session["difficulty"], correct))

    if correct:
        session["difficulty"] = min(10, session["difficulty"] + 1)
    else:
        session["difficulty"] = max(1, session["difficulty"] - 1)

    return render_template(
        "feedback.html",
        correct=correct,
        correct_label=correct_label,
        explanation=session.get("current_explanation", "")
    )


@app.route("/result")
def result():
    history = session.get("history", [])

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
# Run
# ======================================================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

