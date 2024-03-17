import os
import sys
CURPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.extend([CURPATH])
sys.path = list(set(sys.path))
del CURPATH
from flask import Flask
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from config import Config, get_app_config

bootstrap = Bootstrap()
moment = Moment()


def create_webapp():
    app = Flask(__name__)

    app_config: Config = get_app_config()
    app.config.from_object(app_config)

    app_config.init_app(app)
    bootstrap.init_app(app)
    moment.init_app(app)

    from .main import main as blueprint_main
    app.register_blueprint(blueprint_main)

    from .api import api as blueprint_api
    app.register_blueprint(blueprint_api, url_prefix='/api')

    print(f"Flask App is created ({app})")

    return app
