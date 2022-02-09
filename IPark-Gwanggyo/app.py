from Include import get_home
from web import create_webapp, config


if __name__ == '__main__':
    home = get_home('IPark-Gwanggyo (Bestin)')
    home.initSerialConnection()
    app = create_webapp()
    app.app_context().push()
    app.run(host=config.HOST, port=config.PORT, debug=False)
    home.release()
