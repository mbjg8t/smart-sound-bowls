from flask import Blueprint, current_app, render_template


main_bp = Blueprint("main", __name__)


def controller():
    return current_app.extensions["sound_bowl_controller"]


@main_bp.route("/")
def index():
    return render_template(
        "main.html",
        state=controller().get_state(),
    )
