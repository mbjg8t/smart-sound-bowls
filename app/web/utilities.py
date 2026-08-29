from flask import Blueprint, current_app, render_template


utilities_bp = Blueprint("utilities", __name__)


@utilities_bp.route("/audio")
def audio_utility():
    return render_template(
        "utilities/audio.html"
    )


@utilities_bp.route("/microphone")
def microphone_utility():
    return render_template(
        "utilities/microphone.html"
    )


@utilities_bp.route("/system")
def system_utility():
    return render_template(
        "utilities/system.html"
    )


@utilities_bp.route("/adxl345")
def adxl345_utility():
    return render_template(
        "utilities/adxl345.html"
    )
