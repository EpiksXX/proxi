import json

from flask import Blueprint, render_template, request, redirect, url_for, jsonify

from admin import storage
from admin.lore_engine import source_code

admin = Blueprint(
    "admin",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/admin"
)


@admin.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        lorebooks_count=len(storage.list_lorebooks()),
        plugins_count=len(storage.list_plugins()),
    )


# ---------------- Lorebooks ----------------

@admin.route("/lorebooks", methods=["GET", "POST"])
def lorebooks_list():
    if request.method == "POST":
        # 1. Обработка импорта JSON файла через модальное окно
        file = request.files.get("file")
        if file and file.filename.endswith(".json"):
            try:
                raw = file.read().decode("utf-8")
                data = json.loads(raw)
                if isinstance(data, dict) and "entries" in data:
                    source_name = data.get("name") or file.filename
                    new_entries = _convert_sillytavern_lorebook(data, source_name)
                elif isinstance(data, list):
                    source_name = file.filename
                    new_entries = _convert_own_format_lorebook(data, source_name)
                else:
                    new_entries = []
                
                for entry in new_entries:
                    storage.save_lorebook(entry)
                return redirect(url_for("admin.lorebooks_list", imported=len(new_entries)))
            except Exception:
                pass

        # 2. Обработка создания новой записи вручную через модальное окно
        keywords_raw = request.form.get("keywords", "").strip()
        content = request.form.get("content", "").strip()
        if keywords_raw and content:
            keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
            entry = {
                "id": None,
                "name": keywords[0] if keywords else "Новая запись",
                "keywords": keywords,
                "content": content,
                "priority": 0,
                "case_sensitive": False,
                "enabled": True,
                "source": "Добавлено вручную",
            }
            storage.save_lorebook(entry)
            return redirect(url_for("admin.lorebooks_list"))

        return redirect(url_for("admin.lorebooks_list"))

    # GET-запрос: отображение списка лорбуков
    entries = storage.list_lorebooks()

    groups_map = {}
    for e in entries:
        src = e.get("source") or "Без источника"
        groups_map.setdefault(src, []).append(e)

    groups = []
    for src in sorted(groups_map.keys(), key=lambda s: s.lower()):
        group_entries = groups_map[src]
        groups.append({
            "source": src,
            "name": src,
            "code": source_code(src),
            "entries": group_entries,
            "total": len(group_entries),
            "enabled_count": sum(1 for e in group_entries if e.get("enabled", True)),
        })

    return render_template(
        "lorebooks.html",
        groups=groups,
        lorebooks=groups,
        imported=request.args.get("imported"),
        open_source=request.args.get("open", ""),
    )


@admin.route("/lorebooks/bulk-delete", methods=["POST"])
def lorebooks_bulk_delete():
    source = request.form.get("source", "")
    if source:
        storage.delete_lorebooks_by_source(source)
    return redirect(url_for("admin.lorebooks_list"))


@admin.route("/lorebooks/bulk-toggle", methods=["POST"])
def lorebooks_bulk_toggle():
    source = request.form.get("source", "")
    enabled = request.form.get("enabled") == "1"
    if source:
        storage.set_enabled_by_source(source, enabled)
    return redirect(url_for("admin.lorebooks_list", open=source))


@admin.route("/lorebooks/import", methods=["GET", "POST"])
def lorebooks_import():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            return render_template("lorebook_import.html", error="Файл не выбран.")

        try:
            raw = file.read().decode("utf-8")
            data = json.loads(raw)
        except UnicodeDecodeError:
            return render_template("lorebook_import.html", error="Не удалось прочитать файл (неверная кодировка).")
        except json.JSONDecodeError:
            return render_template("lorebook_import.html", error="Файл не является корректным JSON.")

        if isinstance(data, dict) and "entries" in data:
            source_name = data.get("name") or file.filename
            new_entries = _convert_sillytavern_lorebook(data, source_name)
        elif isinstance(data, list):
            source_name = file.filename
            new_entries = _convert_own_format_lorebook(data, source_name)
        else:
            return render_template(
                "lorebook_import.html",
                error="Формат файла не распознан. Ожидается экспорт SillyTavern/World Info "
                      "(объект с полем 'entries') или список записей в формате этой панели.",
            )

        if not new_entries:
            return render_template("lorebook_import.html", error="В файле не найдено ни одной записи.")

        for entry in new_entries:
            storage.save_lorebook(entry)

        return redirect(url_for("admin.lorebooks_list", imported=len(new_entries)))

    return render_template("lorebook_import.html", error=None)


def _convert_sillytavern_lorebook(data, source_name="Импортированный лорбук"):
    """Конвертирует экспорт SillyTavern / World Info в формат этой панели."""
    result = []
    for entry in data.get("entries", {}).values():
        enabled = not entry.get("disable", False)
        keywords = [] if entry.get("constant") else list(entry.get("key", []))
        name = entry.get("comment") or (keywords[0] if keywords else f"entry-{entry.get('uid', '')}")
        result.append({
            "id": None,
            "name": name,
            "keywords": keywords,
            "content": entry.get("content", ""),
            "priority": entry.get("order", 0),
            "case_sensitive": False,
            "enabled": enabled,
            "source": source_name,
        })
    return result


def _convert_own_format_lorebook(data, source_name="Импортированный лорбук"):
    """Принимает список записей уже в формате этой панели."""
    result = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        result.append({
            "id": None,
            "name": entry.get("name", "Без названия"),
            "keywords": entry.get("keywords", []),
            "content": entry.get("content", ""),
            "priority": entry.get("priority", 0),
            "case_sensitive": entry.get("case_sensitive", False),
            "enabled": entry.get("enabled", True),
            "source": entry.get("source") or source_name,
        })
    return result


@admin.route("/lorebooks/new", methods=["GET", "POST"])
def lorebooks_new():
    if request.method == "POST":
        entry = _entry_from_form(request.form)
        entry["source"] = "Добавлено вручную"
        storage.save_lorebook(entry)
        return redirect(url_for("admin.lorebooks_list"))
    return render_template("lorebook_edit.html", entry=None)


@admin.route("/lorebooks/<entry_id>/edit", methods=["GET", "POST"])
def lorebooks_edit(entry_id):
    existing = storage.get_lorebook(entry_id)
    if request.method == "POST":
        entry = _entry_from_form(request.form, entry_id=entry_id)
        entry["source"] = existing.get("source", "Добавлено вручную") if existing else "Добавлено вручную"
        storage.save_lorebook(entry)
        return redirect(url_for("admin.lorebooks_list"))
    return render_template("lorebook_edit.html", entry=existing)


@admin.route("/lorebooks/<entry_id>/delete", methods=["POST"])
def lorebooks_delete(entry_id):
    entry = storage.get_lorebook(entry_id)
    source = entry.get("source", "") if entry else ""
    storage.delete_lorebook(entry_id)
    return redirect(url_for("admin.lorebooks_list", open=source))


@admin.route("/lorebooks/<entry_id>/toggle", methods=["POST"])
def lorebooks_toggle(entry_id):
    entry = storage.get_lorebook(entry_id)
    source = entry.get("source", "") if entry else ""
    storage.toggle_lorebook(entry_id)
    return redirect(url_for("admin.lorebooks_list", open=source))


def _entry_from_form(form, entry_id=None):
    return {
        "id": entry_id,
        "name": form.get("name", "").strip(),
        "keywords": [k.strip() for k in form.get("keywords", "").split(",") if k.strip()],
        "content": form.get("content", "").strip(),
        "priority": int(form.get("priority") or 0),
        "case_sensitive": form.get("case_sensitive") == "on",
        "enabled": form.get("enabled") == "on",
    }


# ---------------- Plugins ----------------

@admin.route("/plugins")
def plugins_list():
    plugins = storage.list_plugins()

    groups_map = {}
    for p in plugins:
        src = p.get("source") or "Без источника"
        groups_map.setdefault(src, []).append(p)

    groups = []
    for src in sorted(groups_map.keys(), key=lambda s: s.lower()):
        group_plugins = groups_map[src]
        groups.append({
            "source": src,
            "code": source_code(src),
            "plugins": group_plugins,
            "total": len(group_plugins),
            "enabled_count": sum(1 for p in group_plugins if p.get("enabled", True)),
        })

    return render_template(
        "plugins.html",
        groups=groups,
        imported=request.args.get("imported"),
        open_source=request.args.get("open", ""),
    )


@admin.route("/plugins/bulk-delete", methods=["POST"])
def plugins_bulk_delete():
    source = request.form.get("source", "")
    if source:
        storage.delete_plugins_by_source(source)
    return redirect(url_for("admin.plugins_list"))


@admin.route("/plugins/bulk-toggle", methods=["POST"])
def plugins_bulk_toggle():
    source = request.form.get("source", "")
    enabled = request.form.get("enabled") == "1"
    if source:
        storage.set_plugins_enabled_by_source(source, enabled)
    return redirect(url_for("admin.plugins_list", open=source))


@admin.route("/plugins/import", methods=["GET", "POST"])
def plugins_import():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            return render_template("plugin_import.html", error="Файл не выбран.")

        try:
            raw = file.read().decode("utf-8")
            data = json.loads(raw)
        except UnicodeDecodeError:
            return render_template("plugin_import.html", error="Не удалось прочитать файл (неверная кодировка).")
        except json.JSONDecodeError:
            return render_template("plugin_import.html", error="Файл не является корректным JSON.")

        if isinstance(data, dict) and "entries" in data:
            source_name = data.get("name") or file.filename
            new_plugins = _convert_lorebary_plugin(data, source_name)
        elif isinstance(data, list):
            source_name = file.filename
            new_plugins = _convert_own_format_plugin(data, source_name)
        else:
            return render_template(
                "plugin_import.html",
                error="Формат файла не распознан. Ожидается экспорт плагина LoreBary "
                      "(объект с полем 'entries') или список правил в формате этой панели.",
            )

        if not new_plugins:
            return render_template("plugin_import.html", error="В файле не найдено ни одного правила.")

        for plugin in new_plugins:
            storage.save_plugin(plugin)

        return redirect(url_for("admin.plugins_list", imported=len(new_plugins)))

    return render_template("plugin_import.html", error=None)


def _convert_lorebary_plugin(data, source_name="Импортированный плагин"):
    """Конвертирует экспорт плагина LoreBary в формат этой панели."""
    result = []
    for entry in data.get("entries", {}).values():
        name = entry.get("name") or entry.get("comment") or f"entry-{entry.get('uid', '')}"

        trigger_groups = entry.get("triggerGroups") or []
        tg = trigger_groups[0] if trigger_groups else {}
        ttype = tg.get("type", "always")

        trigger = "always"
        keywords = []
        interval = 0
        start_after = 0

        if ttype == "keyword":
            trigger = "keyword"
            keywords = tg.get("keywords", [])
        elif ttype == "messageCountInterval":
            trigger = "interval"
            interval = tg.get("messageCountInterval", 0)
            start_after = tg.get("messageCountValue", interval)

        actions = (entry.get("actions") or {}).get("default", [])
        pool = []
        role = "system"
        for action in actions:
            pool.extend(action.get("pool", []))
            role = action.get("role", role)

        result.append({
            "id": None,
            "name": name,
            "source": source_name,
            "trigger": trigger,
            "keywords": keywords,
            "pattern": "",
            "interval": interval,
            "start_after": start_after,
            "pool": pool,
            "role": role,
            "enabled": True,
        })
    return result


def _convert_own_format_plugin(data, source_name="Импортированный плагин"):
    """Принимает список правил уже в формате этой панели."""
    result = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        result.append({
            "id": None,
            "name": entry.get("name", "Без названия"),
            "source": entry.get("source") or source_name,
            "trigger": entry.get("trigger", "always"),
            "keywords": entry.get("keywords", []),
            "pattern": entry.get("pattern", ""),
            "interval": entry.get("interval", 0),
            "start_after": entry.get("start_after", 0),
            "pool": entry.get("pool", []),
            "role": entry.get("role", "system"),
            "enabled": entry.get("enabled", True),
        })
    return result


@admin.route("/plugins/new", methods=["GET", "POST"])
def plugins_new():
    if request.method == "POST":
        plugin = _plugin_from_form(request.form)
        plugin["source"] = f"Ручной: {plugin['name'] or plugin['id'] or 'без названия'}"
        storage.save_plugin(plugin)
        return redirect(url_for("admin.plugins_list"))
    return render_template("plugin_edit.html", plugin=None)


@admin.route("/plugins/<plugin_id>/edit", methods=["GET", "POST"])
def plugins_edit(plugin_id):
    existing = storage.get_plugin(plugin_id)
    if request.method == "POST":
        plugin = _plugin_from_form(request.form, plugin_id=plugin_id)
        plugin["source"] = existing.get("source", "Добавлено вручную") if existing else "Добавлено вручную"
        storage.save_plugin(plugin)
        return redirect(url_for("admin.plugins_list"))
    return render_template("plugin_edit.html", plugin=existing)


@admin.route("/plugins/<plugin_id>/delete", methods=["POST"])
def plugins_delete(plugin_id):
    plugin = storage.get_plugin(plugin_id)
    source = plugin.get("source", "") if plugin else ""
    storage.delete_plugin(plugin_id)
    return redirect(url_for("admin.plugins_list", open=source))


@admin.route("/plugins/<plugin_id>/toggle", methods=["POST"])
def plugins_toggle(plugin_id):
    plugin = storage.get_plugin(plugin_id)
    source = plugin.get("source", "") if plugin else ""
    storage.toggle_plugin(plugin_id)
    return redirect(url_for("admin.plugins_list", open=source))


def _plugin_from_form(form, plugin_id=None):
    trigger = form.get("trigger", "always")
    pool_raw = form.get("pool", "")
    pool = [line.strip() for line in pool_raw.splitlines() if line.strip()]

    return {
        "id": plugin_id,
        "name": form.get("name", "").strip(),
        "trigger": trigger,
        "keywords": [k.strip() for k in form.get("keywords", "").split(",") if k.strip()],
        "pattern": form.get("pattern", "").strip(),
        "interval": int(form.get("interval") or 0),
        "start_after": int(form.get("start_after") or 0),
        "pool": pool,
        "role": form.get("role", "system"),
        "enabled": form.get("enabled") == "on",
    }
