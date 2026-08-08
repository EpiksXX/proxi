import json
import os
import threading
import time
import uuid

# Храним рядом с остальными данными панели, чтобы тот же volume в docker-compose
# (./admin/data:/app/admin/data) автоматически покрывал и комнаты.
DATA_DIR = os.path.join(os.path.dirname(__file__), "admin", "data")
ROOMS_FILE = os.path.join(DATA_DIR, "rooms.json")

_lock = threading.Lock()


def _ensure():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(ROOMS_FILE) or os.path.getsize(ROOMS_FILE) == 0:
        with open(ROOMS_FILE, "w", encoding="utf-8") as fp:
            json.dump({}, fp)


def _load():
    _ensure()
    with _lock:
        with open(ROOMS_FILE, "r", encoding="utf-8") as fp:
            raw = fp.read()

    if not raw.strip():
        _save({})
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        _save({})
        return {}


def _save(data):
    _ensure()
    with _lock:
        with open(ROOMS_FILE, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)


def create_room(character_name, system_prompt, api_key, temperature=1.0, max_tokens=2000):
    rooms = _load()
    room_id = uuid.uuid4().hex[:10]
    rooms[room_id] = {
        "id": room_id,
        "character_name": character_name,
        "system_prompt": system_prompt,
        "api_key": api_key,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "participants": [],   # [{"id":.., "name":.., "joined_at":..}]
        "turn_index": 0,
        "messages": [],        # [{"role":"user"/"assistant", "author":.., "content":.., "ts":..}]
        "locked": False,       # запрещает вход новым участникам
        "created_at": time.time(),
    }
    _save(rooms)
    return rooms[room_id]


def get_room(room_id):
    return _load().get(room_id)


def add_participant(room_id, name):
    rooms = _load()
    room = rooms.get(room_id)
    if not room:
        return None, None
    if room.get("locked"):
        return room, None

    participant = {"id": uuid.uuid4().hex[:8], "name": name[:40], "joined_at": time.time()}
    room["participants"].append(participant)
    rooms[room_id] = room
    _save(rooms)
    return room, participant


def append_message(room_id, role, content, author=None):
    rooms = _load()
    room = rooms.get(room_id)
    if not room:
        return None
    room["messages"].append({
        "role": role,
        "author": author,
        "content": content,
        "ts": time.time(),
    })
    rooms[room_id] = room
    _save(rooms)
    return room


def advance_turn(room_id):
    rooms = _load()
    room = rooms.get(room_id)
    if not room or not room["participants"]:
        return room
    room["turn_index"] = (room["turn_index"] + 1) % len(room["participants"])
    rooms[room_id] = room
    _save(rooms)
    return room


def set_locked(room_id, locked):
    rooms = _load()
    room = rooms.get(room_id)
    if not room:
        return None
    room["locked"] = locked
    rooms[room_id] = room
    _save(rooms)
    return room
