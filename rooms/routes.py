import os

import requests
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, make_response
from tenacity import retry, stop_after_attempt, wait_exponential

import rooms_storage as storage
from admin.lore_engine import build_augmented_system_prompt

rooms = Blueprint(
    "rooms",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/rp",
)

MODEL = "gemini-3-flash-preview"
VISITOR_COOKIE = "rp_visitor_id"


class _Msg:
    """
    Лёгкая обёртка вокруг сообщения комнаты — build_augmented_system_prompt
    (движок лорбуков/плагинов) читает только атрибут .content, поэтому
    полноценная Pydantic-модель ChatRequest.Message тут не нужна.
    """
    def __init__(self, content):
        self.content = content


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def _call_gemini(system_prompt, contents, api_key, temperature, max_tokens):
    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={api_key}"
    )
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    response = requests.post(api_url, json=payload, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f"Gemini returned {response.status_code}: {response.text}")

    data = response.json()
    if "candidates" not in data:
        raise RuntimeError(f"Unexpected Gemini response: {data}")

    return data["candidates"][0]["content"]["parts"][0]["text"]


def _get_cookie_name(room_id):
    """Формирует уникальное имя Cookie для каждой комнаты."""
    return f"{VISITOR_COOKIE}_{room_id}"


def _current_participant(room):
    """
    Получает текущего участника.
    Сначала проверяется Cookie конкретной комнаты, затем общий Cookie.
    """
    cookie_name = _get_cookie_name(room["id"])
    visitor_id = request.cookies.get(cookie_name) or request.cookies.get(VISITOR_COOKIE)
    if not visitor_id:
        return None
    return next((p for p in room["participants"] if p["id"] == visitor_id), None)


def _current_turn(room):
    """Первый участник (по порядку присоединения), кто ещё не написал в этом раунде."""
    submitted = set(room.get("round_submitted", []))
    for p in room["participants"]:
        if p["id"] not in submitted:
            return p
    return None  # все уже написали — раунд обрабатывается / комната без участников


def _build_final_system_prompt(room):
    """
    Собирает системный промпт для запроса к Gemini: сначала прогоняет базовый
    системный промпт комнаты через движок лорбуков/плагинов (<LOREBOOK=...>,
    <PLUGIN=...>), затем добавляет описания персонажей всех участников —
    чтобы ИИ понимал, кто есть кто в общем чате.
    """
    history_msgs = [_Msg(m["content"]) for m in room["messages"]]
    system_prompt = build_augmented_system_prompt(room["system_prompt"], history_msgs)

    persona_lines = [
        f"— {p['name']}: {p['persona']}"
        for p in room["participants"]
        if p.get("persona")
    ]
    if persona_lines:
        persona_block = "\n".join(persona_lines)
        system_prompt = (
            f"{system_prompt}\n\n[Персонажи участников]\n{persona_block}"
            if system_prompt else f"[Персонажи участников]\n{persona_block}"
        )

    return system_prompt


@rooms.route("/new", methods=["GET", "POST"])
def new_room():
    if request.method == "POST":
        character_name = request.form.get("character_name", "").strip() or "Персонаж"
        system_prompt = request.form.get("system_prompt", "").strip()
        api_key = request.form.get("api_key", "").strip() or os.environ.get("GEMINI_API_KEY", "")
        temperature = float(request.form.get("temperature") or 1.0)
        max_tokens = int(request.form.get("max_tokens") or 2000)

        room = storage.create_room(character_name, system_prompt, api_key, temperature, max_tokens)
        return redirect(url_for("rooms.room_page", room_id=room["id"]))

    return render_template("new_room.html")


@rooms.route("/<room_id>")
def room_page(room_id):
    room = storage.get_room(room_id)
    if not room:
        return render_template("room_not_found.html"), 404

    participant = _current_participant(room)
    if not participant:
        return render_template("join_room.html", room=room, error=None)

    return render_template("room.html", room=room, participant=participant)


@rooms.route("/<room_id>/join", methods=["POST"])
def join_room(room_id):
    name = request.form.get("name", "").strip()
    persona = request.form.get("persona", "").strip()
    room = storage.get_room(room_id)
    if not room:
        return render_template("room_not_found.html"), 404

    if not name:
        return render_template("join_room.html", room=room, error="Введи имя, чтобы присоединиться.")

    room, participant = storage.add_participant(room_id, name, persona)
    if participant is None:
        return render_template("join_room.html", room=room, error="Комната закрыта для новых участников.")

    resp = make_response(redirect(url_for("rooms.room_page", room_id=room_id)))
    
    cookie_name = _get_cookie_name(room_id)
    resp.set_cookie(cookie_name, participant["id"], max_age=60 * 60 * 24 * 30, path="/")
    resp.set_cookie(VISITOR_COOKIE, participant["id"], max_age=60 * 60 * 24 * 30, path="/")
    
    return resp


@rooms.route("/<room_id>/api_key", methods=["POST"])
def update_api_key(room_id):
    """Обновление API-ключа комнаты прямо из чата."""
    room = storage.get_room(room_id)
    if not room:
        return jsonify({"error": "Комната не найдена"}), 404

    api_key = request.form.get("api_key", "").strip()
    storage.update_api_key(room_id, api_key)

    return redirect(url_for("rooms.room_page", room_id=room_id))


@rooms.route("/<room_id>/delete", methods=["POST"])
def delete_room(room_id):
    """Удаление комнаты и перенаправление на создание нового чата."""
    storage.delete_room(room_id)
    return redirect(url_for("rooms.new_room"))


@rooms.route("/<room_id>/state")
def room_state(room_id):
    room = storage.get_room(room_id)
    if not room:
        return jsonify({"error": "not found"}), 404

    current_turn = _current_turn(room)

    return jsonify({
        "character_name": room["character_name"],
        "messages": room["messages"],
        "participants": room["participants"],
        "round_submitted": room.get("round_submitted", []),
        "current_turn": current_turn["id"] if current_turn else None,
        "locked": room["locked"],
    })


@rooms.route("/<room_id>/message", methods=["POST"])
def send_message(room_id):
    room = storage.get_room(room_id)
    if not room:
        return jsonify({"error": "Комната не найдена"}), 404

    participant = _current_participant(room)
    if not participant:
        return jsonify({"error": "Сначала присоединись к комнате"}), 403

    current = _current_turn(room)
    if not current or current["id"] != participant["id"]:
        name = current["name"] if current else "—"
        return jsonify({"error": f"Сейчас очередь: {name}"}), 403

    text = request.form.get("message", "").strip()
    if not text:
        return jsonify({"error": "Пустое сообщение"}), 400

    if not room.get("api_key"):
        return jsonify({"error": "Для этой комнаты не задан Gemini API-ключ"}), 400

    storage.append_message(room_id, "user", f"{participant['name']}: {text}", author=participant["name"])
    room = storage.mark_submitted(room_id, participant["id"])

    if len(room["round_submitted"]) < len(room["participants"]):
        return jsonify({"ok": True, "round_complete": False})

    system_prompt = _build_final_system_prompt(room)

    contents = []
    for m in room["messages"]:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    try:
        reply_text = _call_gemini(
            system_prompt, contents, room["api_key"], room["temperature"], room["max_tokens"]
        )
    except Exception as e:
        return jsonify({"error": f"Ошибка Gemini: {e}"}), 502

    storage.append_message(room_id, "assistant", reply_text, author=room["character_name"])
    storage.reset_round(room_id)

    return jsonify({"ok": True, "round_complete": True})


@rooms.route("/<room_id>/retry", methods=["POST"])
def retry_round(room_id):
    room = storage.get_room(room_id)
    if not room:
        return jsonify({"error": "Комната не найдена"}), 404

    if not room["participants"] or len(room["round_submitted"]) < len(room["participants"]):
        return jsonify({"error": "Раунд ещё не завершён — сначала должны написать все участники"}), 400

    if not room.get("api_key"):
        return jsonify({"error": "Для этой комнаты не задан Gemini API-ключ"}), 400

    system_prompt = _build_final_system_prompt(room)

    contents = []
    for m in room["messages"]:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    try:
        reply_text = _call_gemini(
            system_prompt, contents, room["api_key"], room["temperature"], room["max_tokens"]
        )
    except Exception as e:
        return jsonify({"error": f"Ошибка Gemini: {e}"}), 502

    storage.append_message(room_id, "assistant", reply_text, author=room["character_name"])
    storage.reset_round(room_id)

    return jsonify({"ok": True})


@rooms.route("/<room_id>/lock", methods=["POST"])
def lock_room(room_id):
    locked = request.form.get("locked") == "1"
    storage.set_locked(room_id, locked)
    return redirect(url_for("rooms.room_page", room_id=room_id))


@rooms.route("/list")
def list_rooms_page():
    """Отображает страницу со списком всех созданных комнат."""
    all_rooms = storage.list_rooms()
    return render_template("list_rooms.html", rooms=all_rooms)
