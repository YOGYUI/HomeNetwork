import atexit
from Include import get_home
from web import create_webapp, config
from werkzeug.debug import DebuggedApplication

app_debug: bool = True

app = create_webapp()
app.app_context().push()
app.wsgi_app = DebuggedApplication(app.wsgi_app, app_debug)
app.debug = app_debug
home = get_home('Hillstate-Gwanggyosan')
home.initRS485Connection()


def onExitApp():
    print("Web server is closing...")
    home.release()


atexit.register(onExitApp)

if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT, debug=app_debug)
