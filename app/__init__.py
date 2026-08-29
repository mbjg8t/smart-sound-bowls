from flask import Flask

from app.core.controller import SoundBowlController
from app.hardware.pcm5122 import PCM5122
from app.hardware.inmp441 import INMP441


def create_app():
    app = Flask(__name__)

    controller = SoundBowlController()

    app.extensions["sound_bowl_controller"] = controller
    app.extensions["pcm5122"] = PCM5122()
    app.extensions["inmp441"] = INMP441()

    from app.web.routes import main_bp
    from app.web.api import api_bp
    from app.web.utilities import utilities_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(
        api_bp,
        url_prefix="/api",
    )

    app.register_blueprint(
        utilities_bp,
        url_prefix="/utilities",
    )

    return app
