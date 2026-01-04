import os
import time
import json
import random
from flask import Flask, render_template, request, session, redirect, url_for
from google import genai
from google.api_core.exceptions import ServiceUnavailable, ResourceExhausted

# ==========================================================
# FLASK APP SETUP
# ==========================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

# ==========================================================
# GEMINI CLIENT
# ==========================================================
client = genai.Client()

# ==========================================================
# CONTROLLER-OWNED CONSTANTS (FROM IPYNB)
# ==========================================================
QUESTION_CATEGORIES = [
    "grammar",
    "vocabulary_meaning",
    "sentence_paraphrase",
    "inference",
    "error_detection"
]

TOTAL_QUESTIONS = 10

# ==========================================================
# SAFE GEMINI CALL (UNCHANGED LOGIC)
# ==========================================================
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

            raise ValueError("Empty Gemini response")

        except (ServiceUnavailable, ResourceExhausted):
            continue

    raise RuntimeError("Gemini overloaded")

# ==========================================================
# NORMALIZE GEMINI OUTPUT (IPYNB IDENTICAL)
# ==========================================================
def normalize_question(data):
    if "distractors" in data:
        return {
            "question": data["question"],
            "correct": data["correct_answer"],
            "distractors": data["distractors"],
            "explanation": data["explanation"]
        }

    if "options" in data:
        correct_text = data["options"][data["correct_answer"]]
        distractors = [
            v for k, v in data["options"].items()
            if k != data["correct_answer"]
        ]
        return {
            "question": data["question"],
            "correct": correct_text,
            "distractors": distractors,
            "explanation": data["explanation"]
        }

    raise ValueError("Unrecognized Gemini schema")

# ==========================================================
# QUESTION GENERATOR (PROMPT IS IPYNB-EQUIVALENT)
# ==========================================================
def generate_question(category, difficulty, qno):
    prompt = f"""
You are generating ONE English proficiency multiple-choice question.

Category: {category}
Difficulty Level: {difficulty} (1 = beginner, 10 = expert)
Question number: {qno}

CATEGORY DEFINITIONS:
- grammar: grammatical correctness, tense, agreement, clauses
- vocabulary_meaning: precise word meaning, nuance, near-synonyms
- sentence_paraphrase: selecting closest equivalent meaning
- inference: implied meaning, intent, conclusions
- error_detection: identify the incorrect part of a sentence

DIFFICULTY GUIDELINES:
1–3: simple, short, obvious distractors
4–6: moderate complexity, believable distractors
7–8: subtle nuance, close options
9–10: multi-clause reasoning, deep inference

IMPORTANT:
This question MUST be clearly harder than level {max(1, difficulty-1)}
and clearly easier than level {min(10, difficulty+1)}.
Regenerate internally until this constraint is met.

CONTEXT:
Use natural human contexts: daily life, workplace, travel, conversation.
Avoid academic or lab-style questions.

OUTPUT JSON using ONE of these schemas:

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
    raw = call_gemini(prompt)
    data = json.loads(raw)
    return normalize_question(data)

# ==========================================================
# SHUFFLE OPTIONS (NO BIAS)
# ==========================================================
def shuffle_options(correct, distractors):
    options = distractors + [correct]
    random.shuffle(options)
    labels = ["A", "B", "C", "D"]
    option_map = dict(zip(labels, options))
    correct_label = next(k for k, v in option_map.items() if v == correct)
    return option_map, correct_label

# ==========================================================
# ROUTES
# ==========================================================
@app.route("/")
def start():
    session.clear()
    session["difficulty"] = 4
    session["q_index"] = 0
    session["history"] = []

    seq = random.sample(QUESTION_CATEGORIES, len(QUESTION_CATEGORIES))
    while len(seq) < TOTAL_QUESTIONS:
        seq += random.sample(QUESTION_CATEGORIES, len(QUESTION_CATEGORIES))

    session["categories"] = seq
    return render_template("start.html")

@app.route("/question")
def question():
    i = session["q_index"]
    if i >= TOTAL_QUESTIONS:
        return redirect(url_for("result"))

    category = session["categories"][i]
    difficulty = session["difficulty"]

    q = generate_question(category, difficulty, i + 1)
    options, correct_label = shuffle_options(q["correct"], q["distractors"])

    session["current"] = {
        "correct_label": correct_label,
        "difficulty": difficulty,
        "explanation": q["explanation"]
    }

    return render_template(
        "question.html",
        q_index=i,
        question=q["question"],
        options=options,
        difficulty=difficulty,
        category=category
    )

@app.route("/answer", methods=["POST"])
def answer():
    user_ans = request.form.get("answer")
    correct = session["current"]["correct_label"]
    was_correct = user_ans == correct

    session["history"].append((session["difficulty"], was_correct))

    if was_correct:
        session["difficulty"] = min(10, session["difficulty"] + 1)
    else:
        session["difficulty"] = max(1, session["difficulty"] - 1)

    session["q_index"] += 1

    return render_template(
        "feedback.html",
        correct=was_correct,
        correct_label=correct,
        explanation=session["current"]["explanation"]
    )

@app.route("/result")
def result():
    history = session["history"]
    correct = sum(1 for _, c in history if c)
    avg_level = round(sum(d for d, _ in history) / len(history), 1)
    score = min(100, int(avg_level * 8 + correct * 2))

    return render_template(
        "result.html",
        accuracy=round(100 * correct / len(history), 1),
        avg_level=avg_level,
        score=score
    )

# ==========================================================
# ENTRYPOINT (RENDER-COMPATIBLE)
# ==========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

