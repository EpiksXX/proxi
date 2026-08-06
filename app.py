from flask import Flask, jsonify, request
from flask_cors import CORS

from config import APP_PORT
from schemas import ChatRequest
from gemini import generate

import logging
import time
import uuid


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

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

        chat = ChatRequest.from_json(request.get_json())

        start = time.time()

        logging.info("POST /v1/chat/completions")
        logging.info(f"Messages: {len(chat.messages)}")
        logging.info(f"Temperature: {chat.temperature}")
        logging.info(f"Max tokens: {chat.max_tokens}")

        gemini_response = generate(chat)

        usage_metadata = gemini_response.get("usageMetadata", {})

        prompt_tokens = usage_metadata.get("promptTokenCount", 0)
        completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
        total_tokens = usage_metadata.get("totalTokenCount", 0)

        text = ""

        candidates = gemini_response.get("candidates", [])

        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            for part in parts:
                text += part.get("text", "")

        elapsed = time.time() - start

        logging.info(f"Completed in {elapsed:.2f}s")
        logging.info(
            f"Tokens: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
        )

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
            ],

            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            }
        })

    except Exception as e:

        logging.exception("Gemini request failed")

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
