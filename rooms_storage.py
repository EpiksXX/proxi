import json
import os
import uuid

DATA_DIR = os.path.join(os.path.dirname(__file__), "data_rooms")
os.makedirs(DATA_DIR, exist_ok=True)


def _get_room_path(room_id):
    return os.path.join(DATA_DIR, f"{room_id}.json")


def _save_room(room):
    filepath = _get_room_path(room["id"])
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(room, f, ensure_ascii=False, indent=2)


def create_room(character_name, system_prompt, api_key, temperature=1.0, max_tokens=2000):
    room_id = uuid.uuid4().hex[:8]
    room = {
        "id": room_id,
        "character_name": character_name,
        "system_prompt": system_prompt,
        "api_key": api_key,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "participants": [],
        "messages": [],
        "memories": [],  # Список воспоминаний/фактов комнаты
        "round_submitted": [],
        "locked": False,
    }
    _save_room(room)
    return room


def get_room(room_id):
    filepath = _get_room_path(room_id)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def delete_room(room_id):
    """Удаляет файл комнаты с диска."""
    filepath = _get_room_path(room_id)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False


def list_rooms():
    """Возвращает список всех созданных комнат."""
    rooms = []
    if not os.path.exists(DATA_DIR):
        return rooms
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".json"):
            room_id = fname[:-5]
            room = get_room(room_id)
            if room:
                rooms.append(room)
    return rooms


def add_participant(room_id, name, persona=""):
    room = get_room(room_id)
    if not room or room.get("locked"):
        return room, None

    participant = {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "persona": persona,
    }
    room["participants"].append(participant)
    _save_room(room)
    return room, participant


def update_participant(room_id, participant_id, name, persona=""):
    """Обновляет имя и описание (персону) участника в комнате."""
    room = get_room(room_id)
    if not room:
        return None, None
    for p in room["participants"]:
        if p["id"] == participant_id:
            if name:
                p["name"] = name
            p["persona"] = persona
            _save_room(room)
            return room, p
    return room, None


def append_message(room_id, role, content, author="", author_id=None):
    """Сохраняет сообщение с указанием автора и его ID."""
    room = get_room(room_id)
    if not room:
        return None
    message = {
        "role": role,
        "content": content,
        "author": author,
        "author_id": author_id,
    }
    room["messages"].append(message)
    _save_room(room)
    return room


def mark_submitted(room_id, participant_id):
    room = get_room(room_id)
    if not room:
        return None
    if "round_submitted" not in room:
        room["round_submitted"] = []
    if participant_id not in room["round_submitted"]:
        room["round_submitted"].append(participant_id)
        _save_room(room)
    return room


def reset_round(room_id):
    room = get_room(room_id)
    if not room:
        return None
    room["round_submitted"] = []
    _save_room(room)
    return room


def set_locked(room_id, locked):
    room = get_room(room_id)
    if not room:
        return None
    room["locked"] = locked
    _save_room(room)
    return room


def update_api_key(room_id, api_key):
    room = get_room(room_id)
    if not room:
        return None
    room["api_key"] = api_key
    _save_room(room)
    return room


def add_room_memory(room_id, memory_text):
    """Добавляет факт в память комнаты."""
    room = get_room(room_id)
    if not room:
        return None
    if "memories" not in room:
        room["memories"] = []
    room["memories"].append(memory_text)
    _save_room(room)
    return room


def delete_room_memory(room_id, index):
    """Удаляет факт из памяти комнаты по индексу."""
    room = get_room(room_id)
    if not room:
        return None
    if "memories" in room and 0 <= index < len(room["memories"]):
        room["memories"].pop(index)
        _save_room(room)
    return room

def update_room_prompt(room_id, system_prompt):
    """Обновляет системный промпт комнаты на лету."""
    room = get_room(room_id)
    if not room:
        return None
    room["system_prompt"] = system_prompt
    _save_room(room)
    return room
