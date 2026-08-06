from flask import Flask, jsonify, request
from flask_cors import CORS
from config import APP_PORT
from schemas import ChatRequest
from gemini import generate
import time
import uuid

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

    try:

        chat = ChatRequest.from_json(request.json)

        gemini_response = generate(chat)

        text = ""

        candidates = gemini_response.get("candidates", [])

        if candidates:

            content = candidates[0].get("content", {})

            parts = content.get("parts", [])

            for part in parts:
                text += part.get("text", "")

        return jsonify({

            "id": f"chatcmpl-{uuid.uuid4().hex}",

            "object": "chat.completion",

            "created": int(time.time()),

            "model": "gemini-3-flash-preview",

            "choices": [

                {

                    "index": 0,

                    "message": {

                        "role": "assistant",

                        "content": text

                    },

                    "finish_reason": "stop"

                }

            ]

        })

    except Exception as e:

        return jsonify({

            "error": {

                "message": str(e),

                "type": "server_error"

            }

        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=APP_PORT
    )
