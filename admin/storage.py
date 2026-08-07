import json
import os
import threading
import uuid

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOREBOOKS_FILE = os.path.join(DATA_DIR, "lorebooks.json")
PLUGINS_FILE = os.path.join(DATA_DIR, "plugins.json")

_lock = threading.Lock()


def _ensure():
    os.makedirs(DATA_DIR, exist_ok=True)
    for path in (LOREBOOKS_FILE, PLUGINS_FILE):
        # Создаём файл, если его нет ИЛИ если он существует, но пустой
        # (например, из-за пустого volume/COPY на сервере).
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            with open(path, "w", encoding="utf-8") as fp:
                json.dump([], fp)


def _load(path):
    _ensure()
    with _lock:
        with open(path, "r", encoding="utf-8") as fp:
            raw = fp.read()

    if not raw.strip():
        # файл пустой/повреждён — не роняем приложение, восстанавливаем его
        _save(path, [])
        return []

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # файл содержит мусор — пересоздаём как пустой список,
        # чтобы дашборд и роуты не падали с 500-й ошибкой
        _save(path, [])
        return []


def _save(path, data):
    _ensure()
    with _lock:
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)


# ---------------- Lorebooks ----------------

def list_lorebooks():
    return _load(LOREBOOKS_FILE)


def get_lorebook(entry_id):
    return next((e for e in list_lorebooks() if e["id"] == entry_id), None)


def save_lorebook(entry):
    entries = list_lorebooks()
    if entry.get("id"):
        entries = [entry if e["id"] == entry["id"] else e for e in entries]
    else:
        entry["id"] = uuid.uuid4().hex[:8]
        entries.append(entry)
    _save(LOREBOOKS_FILE, entries)
    return entry


def delete_lorebook(entry_id):
    entries = [e for e in list_lorebooks() if e["id"] != entry_id]
    _save(LOREBOOKS_FILE, entries)


def toggle_lorebook(entry_id):
    entries = list_lorebooks()
    for e in entries:
        if e["id"] == entry_id:
            e["enabled"] = not e.get("enabled", True)
    _save(LOREBOOKS_FILE, entries)


def list_lorebook_sources():
    """Возвращает отсортированный список уникальных источников (названий лорбуков)."""
    sources = {e.get("source", "Без источника") for e in list_lorebooks()}
    return sorted(sources)


def delete_lorebooks_by_source(source):
    entries = [e for e in list_lorebooks() if e.get("source", "Без источника") != source]
    _save(LOREBOOKS_FILE, entries)


def set_enabled_by_source(source, enabled):
    entries = list_lorebooks()
    for e in entries:
        if e.get("source", "Без источника") == source:
            e["enabled"] = enabled
    _save(LOREBOOKS_FILE, entries)


# ---------------- Plugins ----------------

def list_plugins():
    return _load(PLUGINS_FILE)


def get_plugin(plugin_id):
    return next((p for p in list_plugins() if p["id"] == plugin_id), None)


def save_plugin(plugin):
    plugins = list_plugins()
    if plugin.get("id"):
        plugins = [plugin if p["id"] == plugin["id"] else p for p in plugins]
    else:
        plugin["id"] = uuid.uuid4().hex[:8]
        plugins.append(plugin)
    _save(PLUGINS_FILE, plugins)
    return plugin


def delete_plugin(plugin_id):
    plugins = [p for p in list_plugins() if p["id"] != plugin_id]
    _save(PLUGINS_FILE, plugins)


def toggle_plugin(plugin_id):
    plugins = list_plugins()
    for p in plugins:
        if p["id"] == plugin_id:
            p["enabled"] = not p.get("enabled", True)
    _save(PLUGINS_FILE, plugins)
