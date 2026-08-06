import os
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from schemas import ChatRequest

# Всегда используем только эту модель
MODEL = "gemini-3-flash-preview"

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "Переменная окружения GEMINI_API_KEY не найдена."
    )

API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent?key={API_KEY}"
)


def convert_messages(chat: ChatRequest):
    """
    Преобразует сообщения OpenAI в формат Gemini.
    """

    contents = []
    system_prompt = None

    for message in chat.messages:

        if message.role == "system":
            system_prompt = message.content
            continue

        role = "user"

        if message.role == "assistant":
            role = "model"

        contents.append({
            "role": role,
            "parts": [
                {
                    "text": message.content
                }
            ]
        })

    return system_prompt, contents


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
def generate(chat: ChatRequest):

    system_prompt, contents = convert_messages(chat)

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": chat.temperature,
            "maxOutputTokens": chat.max_tokens,
        }
    }

    if system_prompt:
        payload["systemInstruction"] = {
            "parts": [
                {
                    "text": system_prompt
                }
            ]
        }

    response = requests.post(
        API_URL,
        json=payload,
        timeout=300,
    )

    response.raise_for_status()

    return response.json()
