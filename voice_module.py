import base64
import os
from flask import Blueprint, jsonify, request
from google import genai
from google.genai import types

voice_bp = Blueprint("voice_bp", __name__)

# Инициализируем клиент Google GenAI
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


@voice_bp.route("/api/chat", methods=["POST"])
def voice_chat():
  data = request.get_json() or {}
  messages = data.get("messages", [])
  system_prompt = data.get(
      "system_prompt",
      (
          "Ты — живой саркастичный, но дружелюбный собеседник. Отвечай кратко"
          " (1-2 предложения) и используй аудио-теги [cheerful], [sighs],"
          " [giggles], [whispers], [sarcastic]."
      ),
  )
  voice_name = data.get("voice", "Puck")

  if not messages:
    return jsonify({"error": "История сообщений пуста"}), 400

  try:
    # 1. Генерация текстовой реплики с учетом контекста и характера
    text_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=messages,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.85,
        ),
    )
    reply_text = text_response.text

    # 2. Синтез речи через Gemini 3.1 Flash TTS Preview
    tts_interaction = client.interactions.create(
        model="gemini-3.1-flash-tts-preview",
        input=reply_text,
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": voice_name}]},
    )

    audio_base64 = tts_interaction.output_audio.data

    return jsonify({
        "status": "success",
        "reply_text": reply_text,
        "audio_base64": audio_base64,
    })

  except Exception as e:
    return jsonify({"error": str(e)}), 500
