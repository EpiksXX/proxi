from flask import Flask, jsonify, request
from flask_cors import CORS

from config import APP_PORT

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name": "Gemini Flash Preview Proxy",
        "status": "running"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy"
    })


@app.route("/v1/models", methods=["GET"])
def models():
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": "gemini-3-flash-preview",
                "object": "model",
                "created": 0,
                "owned_by": "google"
            }
        ]
    })


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    return jsonify({
        "error": {
            "message": "Gemini module not implemented yet.",
            "type": "server_error"
        }
    }), 501


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=APP_PORT
    )
