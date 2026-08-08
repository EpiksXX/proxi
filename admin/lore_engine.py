import hashlib
import random
import re

from admin import storage

# Теги, которые можно вставить прямо в системный промпт / character card:
#   <LOREBOOK=A1B2C3D4>       — подставить книгу знаний по коду (глубина сканирования по умолчанию)
#   <LOREBOOK=A1B2C3D4/5>     — то же самое, но сканировать последние 5 сообщений вместо дефолта
#   <PLUGIN=A1B2C3D4>         — подставить набор плагинов по коду источника
LOREBOOK_TAG_PATTERN = re.compile(r"<LOREBOOK=([0-9A-Fa-f]{6,10})(?:/(\d+))?>")
PLUGIN_TAG_PATTERN = re.compile(r"<PLUGIN=([0-9A-Fa-f]{6,10})>")

DEFAULT_TAG_DEPTH = 2  # как в LoreBary: по умолчанию сканируются последние 2 сообщения


def source_code(source_name):
    """
    Детерминированный короткий код для источника (названия лорбука/набора плагинов).
    Ничего не хранится отдельно — код всегда одинаковый для одного и того же названия.
    """
    source_name = source_name or "Без источника"
    return hashlib.md5(source_name.encode("utf-8")).hexdigest()[:8].upper()


def _recent_text(messages, window=6):
    """Склеивает текст последних N сообщений чата в одну строку для поиска совпадений."""
    chunks = []
    for m in messages[-window:]:
        content = getattr(m, "content", None)
        if content:
            chunks.append(content)
    return " ".join(chunks)


def _keyword_matches(text, keywords, case_sensitive=False):
    haystack = text if case_sensitive else text.lower()
    for kw in keywords:
        needle = kw if case_sensitive else kw.lower()
        if needle and needle in haystack:
            return True
    return False


def _match_entries(entries, text, max_entries):
    matched = []
    for entry in entries:
        if not entry.get("enabled", True):
            continue
        keywords = entry.get("keywords", [])
        if not keywords or _keyword_matches(text, keywords, entry.get("case_sensitive", False)):
            matched.append(entry)

    matched.sort(key=lambda e: e.get("priority", 0), reverse=True)
    matched = matched[:max_entries]

    if not matched:
        return ""
    return "\n\n".join(e["content"] for e in matched if e.get("content"))


def build_lore_context_by_code(code, messages, window=DEFAULT_TAG_DEPTH, max_entries=20):
    """Скан только среди записей конкретного источника лорбука (найденного по коду из тега)."""
    text = _recent_text(messages, window=window)
    entries = [
        e for e in storage.list_lorebooks()
        if source_code(e.get("source", "Без источника")) == code.upper()
    ]
    return _match_entries(entries, text, max_entries)


# ---------------- Плагины ----------------

def _pool_pick(pool):
    """Случайно выбирает один вариант текста из пула (как chance-пул в LoreBary)."""
    pool = [p for p in (pool or []) if p]
    if not pool:
        return ""
    return random.choice(pool)


def _plugin_entry_triggers(entry, text, msg_count):
    """
    Проверяет, должно ли конкретное правило плагина сработать в этом запросе.
    Поддерживаемые типы триггера:
      - always     — срабатывает всегда
      - keyword    — срабатывает, если в последних сообщениях есть одно из ключевых слов
      - regex      — срабатывает по регулярному выражению (продвинутый вариант keyword)
      - interval   — срабатывает каждые N сообщений, начиная с start_after
    """
    trigger = entry.get("trigger", "always")

    if trigger == "always":
        return True

    if trigger == "keyword":
        keywords = entry.get("keywords", [])
        return bool(keywords) and _keyword_matches(text, keywords, entry.get("case_sensitive", False))

    if trigger == "regex":
        pattern = entry.get("pattern", "")
        if not pattern:
            return False
        try:
            return bool(re.search(pattern, text, re.IGNORECASE))
        except re.error:
            return False

    if trigger == "interval":
        interval = int(entry.get("interval") or 0)
        if interval <= 0:
            return False
        start_after = int(entry.get("start_after") or interval)
        if msg_count < start_after:
            return False
        return (msg_count - start_after) % interval == 0

    return False


def build_plugin_text_by_code(code, messages):
    """
    Собирает текст всех сработавших в этом запросе правил плагина
    из набора, найденного по коду источника.
    """
    text = _recent_text(messages)
    msg_count = len(messages)
    code = code.upper()

    parts = []
    for entry in storage.list_plugins():
        if not entry.get("enabled", True):
            continue
        if source_code(entry.get("source", "Без источника")) != code:
            continue
        if not _plugin_entry_triggers(entry, text, msg_count):
            continue

        chosen = _pool_pick(entry.get("pool", []))
        if chosen:
            parts.append(chosen)

    return "\n\n".join(parts)


def build_augmented_system_prompt(base_system_prompt, messages):
    """
    Главная точка входа. И лорбуки, и плагины работают ТОЛЬКО по явному тегу:
      <LOREBOOK=КОД>          — подставить книгу по коду (глубина сканирования по умолчанию)
      <LOREBOOK=КОД/ГЛУБИНА>  — то же самое, но сканировать последние N сообщений
      <PLUGIN=КОД>            — подставить сработавшие в этом запросе правила плагина по коду

    Без тега ничего НЕ подставляется — сколько бы книг/плагинов ни было загружено,
    они не влияют на промпт, пока их источник явно не вызван по коду.
    """
    prompt = base_system_prompt or ""

    for m in LOREBOOK_TAG_PATTERN.finditer(prompt):
        code = m.group(1).upper()
        depth = int(m.group(2)) if m.group(2) else DEFAULT_TAG_DEPTH
        lore_text = build_lore_context_by_code(code, messages, window=depth)
        prompt = prompt.replace(m.group(0), lore_text, 1)

    for m in PLUGIN_TAG_PATTERN.finditer(prompt):
        code = m.group(1)
        plugin_text = build_plugin_text_by_code(code, messages)
        prompt = prompt.replace(m.group(0), plugin_text, 1)

    return prompt
