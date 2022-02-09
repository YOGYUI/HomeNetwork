from typing import Union
from Include import Home
from web import create_webapp, config

home_: Union[Home, None] = None


def get_home() -> Home:
    global home_
    if home_ is None:
        home_ = Home(name='IPark-Gwanggyo')
    return home_


if __name__ == '__main__':
    home = get_home()
    home.initSerialConnection()
    app = create_webapp()
    app.app_context().push()
    app.run(host=config.HOST, port=config.PORT, debug=False)
    home.release()
