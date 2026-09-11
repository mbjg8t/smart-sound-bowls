from flask import Blueprint, abort, current_app, render_template

main_bp = Blueprint("main", __name__)


def controller():
    return current_app.extensions["sound_bowl_controller"]


@main_bp.route("/")
def index():
    return render_template("main.html", state={"system_status": "READY"}, bowls=controller().get_state())


@main_bp.route("/bowl/<int:bowl_id>")
def bowl_window(bowl_id):
    try:
        bowl = controller().get_state(bowl_id)
    except KeyError:
        abort(404)
    return render_template("bowl.html", state=bowl, bowl=bowl)
