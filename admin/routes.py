from flask import Blueprint, render_template, request, redirect, url_for

from admin import storage

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

@admin.route("/lorebooks")
def lorebooks_list():
    return render_template("lorebooks.html", entries=storage.list_lorebooks())


@admin.route("/lorebooks/new", methods=["GET", "POST"])
def lorebooks_new():
    if request.method == "POST":
        entry = _entry_from_form(request.form)
        storage.save_lorebook(entry)
        return redirect(url_for("admin.lorebooks_list"))
    return render_template("lorebook_edit.html", entry=None)


@admin.route("/lorebooks/<entry_id>/edit", methods=["GET", "POST"])
def lorebooks_edit(entry_id):
    entry = storage.get_lorebook(entry_id)
    if request.method == "POST":
        entry = _entry_from_form(request.form, entry_id=entry_id)
        storage.save_lorebook(entry)
        return redirect(url_for("admin.lorebooks_list"))
    return render_template("lorebook_edit.html", entry=entry)


@admin.route("/lorebooks/<entry_id>/delete", methods=["POST"])
def lorebooks_delete(entry_id):
    storage.delete_lorebook(entry_id)
    return redirect(url_for("admin.lorebooks_list"))


@admin.route("/lorebooks/<entry_id>/toggle", methods=["POST"])
def lorebooks_toggle(entry_id):
    storage.toggle_lorebook(entry_id)
    return redirect(url_for("admin.lorebooks_list"))


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
    return render_template("plugins.html", plugins=storage.list_plugins())


@admin.route("/plugins/new", methods=["GET", "POST"])
def plugins_new():
    if request.method == "POST":
        plugin = _plugin_from_form(request.form)
        storage.save_plugin(plugin)
        return redirect(url_for("admin.plugins_list"))
    return render_template("plugin_edit.html", plugin=None)


@admin.route("/plugins/<plugin_id>/edit", methods=["GET", "POST"])
def plugins_edit(plugin_id):
    plugin = storage.get_plugin(plugin_id)
    if request.method == "POST":
        plugin = _plugin_from_form(request.form, plugin_id=plugin_id)
        storage.save_plugin(plugin)
        return redirect(url_for("admin.plugins_list"))
    return render_template("plugin_edit.html", plugin=plugin)


@admin.route("/plugins/<plugin_id>/delete", methods=["POST"])
def plugins_delete(plugin_id):
    storage.delete_plugin(plugin_id)
    return redirect(url_for("admin.plugins_list"))


@admin.route("/plugins/<plugin_id>/toggle", methods=["POST"])
def plugins_toggle(plugin_id):
    storage.toggle_plugin(plugin_id)
    return redirect(url_for("admin.plugins_list"))


def _plugin_from_form(form, plugin_id=None):
    return {
        "id": plugin_id,
        "name": form.get("name", "").strip(),
        "trigger": form.get("trigger", "always"),
        "pattern": form.get("pattern", "").strip(),
        "position": form.get("position", "after"),
        "text": form.get("text", "").strip(),
        "enabled": form.get("enabled") == "on",
    }
