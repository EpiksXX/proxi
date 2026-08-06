from flask import Blueprint, render_template

admin = Blueprint(
    "admin",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/admin"
)


@admin.route("/")
def dashboard():
    return render_template("dashboard.html")
