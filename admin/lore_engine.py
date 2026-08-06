import re

from admin import storage


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


def build_lore_context(messages, max_entries=10):
    """
    Проходит по включённым записям лорбука и возвращает текст тех,
    у которых сработали ключевые слова (или у которых ключевых слов нет —
    такие вставляются всегда).
    """
    text = _recent_text(messages)
    matched = []

    for entry in storage.list_lorebooks():
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


def apply_plugins(system_prompt, messages):
    """
    Прогоняет включённые плагины: те, что триггерятся regex-ом по последним
    сообщениям — проверяются, остальные ("always") применяются всегда.
    """
    text = _recent_text(messages)

    for plugin in storage.list_plugins():
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
                # некорректный regex — просто пропускаем плагин
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
    """Главная точка входа: объединяет базовый системный промпт, лорбук и плагины."""
    prompt = base_system_prompt or ""

    lore_text = build_lore_context(messages)
    if lore_text:
        prompt = f"{prompt}\n\n[Lorebook]\n{lore_text}" if prompt else f"[Lorebook]\n{lore_text}"

    prompt = apply_plugins(prompt, messages)
    return prompt
