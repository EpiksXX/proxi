import hashlib
import re

from admin import storage

# Теги, которые можно вставить прямо в системный промпт / character card:
#   <LOREBOOK=A1B2C3D4>       — подставить книгу знаний по коду (глубина сканирования по умолчанию)
#   <LOREBOOK=A1B2C3D4/5>     — то же самое, но сканировать последние 5 сообщений вместо дефолта
#   <PLUGIN=a1b2c3d4>         — подставить текст плагина по его id
LOREBOOK_TAG_PATTERN = re.compile(r"<LOREBOOK=([0-9A-Fa-f]{6,10})(?:/(\d+))?>")
PLUGIN_TAG_PATTERN = re.compile(r"<PLUGIN=([0-9A-Fa-f]{6,10})(?:/(\d+))?>")

DEFAULT_TAG_DEPTH = 2  # как в LoreBary: по умолчанию сканируются последние 2 сообщения


def source_code(source_name):
    """
    Детерминированный короткий код для источника (названия лорбука).
    Ничего не хранится отдельно — код всегда одинаковый для одного и того же названия,
    поэтому его достаточно один раз посчитать и показать в панели.
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


def _keyword_matches(text, keywords, case_sensitive):
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


def build_lore_context(messages, max_entries=10, exclude_codes=None):
    """
    Автоматический скан (без явного тега): проходит по всем включённым записям,
    ИСКЛЮЧАЯ те источники, что уже были явно вызваны через <LOREBOOK=КОД> в этом промпте
    (чтобы не подставлять один и тот же контент дважды).
    """
    exclude_codes = exclude_codes or set()
    text = _recent_text(messages)

    entries = [
        e for e in storage.list_lorebooks()
        if source_code(e.get("source", "Без источника")) not in exclude_codes
    ]
    return _match_entries(entries, text, max_entries)


def build_lore_context_by_code(code, messages, window=DEFAULT_TAG_DEPTH, max_entries=20):
    """Скан только среди записей конкретного источника (найденного по коду из тега)."""
    text = _recent_text(messages, window=window)
    entries = [
        e for e in storage.list_lorebooks()
        if source_code(e.get("source", "Без источника")) == code.upper()
    ]
    return _match_entries(entries, text, max_entries)


def apply_plugins(system_prompt, messages, exclude_ids=None):
    """
    Прогоняет включённые плагины, ИСКЛЮЧАЯ те, что уже были явно вызваны
    через <PLUGIN=ID> в этом промпте.
    """
    exclude_ids = exclude_ids or set()
    text = _recent_text(messages)

    for plugin in storage.list_plugins():
        if plugin.get("id") in exclude_ids:
            continue
        if not plugin.get("enabled", True):
            continue

        trigger = plugin.get("trigger", "always")
        if trigger == "regex":
            pattern = plugin.get("pattern", "")
            if not pattern:
                continue
            try:
                if not re.search(pattern, text, re.IGNORECASE):
                    continue
            except re.error:
                continue

        plugin_text = plugin.get("text", "")
        if not plugin_text:
            continue

        if plugin.get("position", "after") == "before":
            system_prompt = f"{plugin_text}\n\n{system_prompt}" if system_prompt else plugin_text
        else:
            system_prompt = f"{system_prompt}\n\n{plugin_text}" if system_prompt else plugin_text

    return system_prompt


def build_augmented_system_prompt(base_system_prompt, messages):
    """
    Главная точка входа. Лорбуки работают ТОЛЬКО по явному тегу:
      <LOREBOOK=КОД>            — подставить книгу по коду (глубина сканирования по умолчанию)
      <LOREBOOK=КОД/ГЛУБИНА>    — то же самое, но сканировать последние N сообщений

    Без тега книга НИКОГДА не подставляется — сколько бы записей ни было загружено,
    они не влияют на промпт, пока их источник явно не вызван по коду.

    Плагины по-прежнему работают либо через явный тег <PLUGIN=ID>, либо автоматически
    (always / regex), если тег не использован — это не меняли, скажи, если тоже
    нужно перевести только на теги.
    """
    prompt = base_system_prompt or ""

    # --- Явные теги лорбука (единственный способ подключить книгу) ---
    tagged_codes = set()
    for m in LOREBOOK_TAG_PATTERN.finditer(prompt):
        code = m.group(1).upper()
        depth = int(m.group(2)) if m.group(2) else DEFAULT_TAG_DEPTH
        tagged_codes.add(code)
        lore_text = build_lore_context_by_code(code, messages, window=depth)
        prompt = prompt.replace(m.group(0), lore_text, 1)

    # --- Явные теги плагинов ---
    tagged_plugin_ids = set()
    for m in PLUGIN_TAG_PATTERN.finditer(prompt):
        plugin_id = m.group(1).lower()
        tagged_plugin_ids.add(plugin_id)
        plugin = storage.get_plugin(plugin_id)
        text = plugin.get("text", "") if plugin and plugin.get("enabled", True) else ""
        prompt = prompt.replace(m.group(0), text, 1)

    # --- Остальные включённые плагины (без явного тега) — оставлено как было ---
    prompt = apply_plugins(prompt, messages, exclude_ids=tagged_plugin_ids)

    return prompt
