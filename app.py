from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# -----------------------------
# Route 1: HTML page
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")

# -----------------------------
# Route 2: Lowercase API
# -----------------------------
@app.route("/lowercase", methods=["POST"])
def lowercase_text():
    data = request.get_json()

    if not data or "text" not in data:
        return jsonify({"error": "No text provided"}), 400

    original = data["text"]
    result = original.lower()

    return jsonify({
        "original": original,
        "lowercase": result
    })

# -----------------------------
# Start server
# -----------------------------
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

