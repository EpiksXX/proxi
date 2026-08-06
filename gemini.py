import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from schemas import ChatRequest

# Всегда используем только эту модель
MODEL = "gemini-3-flash-preview"


def convert_messages(chat: ChatRequest):
    """
    Преобразует сообщения OpenAI в формат Gemini.
    """

    contents = []
    system_messages = []

    for message in chat.messages:

        if message.role == "system":
            system_messages.append(message.content)
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

    system_prompt = "\n\n".join(system_messages)

    return system_prompt, contents


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def generate(chat: ChatRequest, api_key: str):

    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={api_key}"
    )

    system_prompt, contents = convert_messages(chat)

    generation_config = {
        "temperature": chat.temperature,
        "topP": chat.top_p,
        "maxOutputTokens": chat.max_tokens,
    }

    if chat.stop:
        generation_config["stopSequences"] = chat.stop

    payload = {
        "contents": contents,
        "generationConfig": generation_config
    }

    if system_prompt:
        payload["systemInstruction"] = {
            "parts": [
                {
                    "text": system_prompt
                }
            ]
        }

    try:
        response = requests.post(
            api_url,
            json=payload,
            timeout=300,
        )

    except requests.exceptions.Timeout:
        raise RuntimeError("Gemini API timeout")

    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to Gemini API")

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Request failed: {e}")

    if response.status_code == 429:
        raise RuntimeError("Gemini rate limit exceeded")

    if response.status_code == 503:
        raise RuntimeError("Gemini service unavailable")

    if response.status_code >= 500:
        raise RuntimeError(
            f"Gemini server error ({response.status_code})"
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Gemini returned {response.status_code}: {response.text}"
        )

    data = response.json()

    if "candidates" not in data:
        raise RuntimeError(
            f"Unexpected Gemini response:\n{data}"
        )

    return data
