import atexit
from Include import *
from web import create_webapp, get_app_config
from werkzeug.debug import DebuggedApplication

import json
import argparse
parser = argparse.ArgumentParser(description='Home Network Application Arguments')
parser.add_argument(
    '--config_file_path', 
    help='absolute path of configuration file path')
parser.add_argument(
    '--mqtt_broker', 
    help='MQTT broker configuration (json formatted string)')
parser.add_argument(
    '--rs485', 
    help='RS485 port(s) configuration (json formatted string)')
parser.add_argument(
    '--discovery', 
    help='Device discovery configuration (json formatted string)')
parser.add_argument(
    '--parser_mapping', 
    help='RS485 parser mapping configuration (json formatted string)')
parser.add_argument(
    '--periodic_query_state', 
    help='Periodic query state configuration (json formatted string)')
parser.add_argument(
    '--subphone',
    help="Kitchen subphone configuration (json formatted string)")
parser.add_argument(
    '--etc', 
    help='Other optional configuration (json formatted string)')
args = parser.parse_args()

app_config = get_app_config(args.config_file_path)
app = create_webapp()
app.app_context().push()
app.wsgi_app = DebuggedApplication(app.wsgi_app, app_config.LOG)
app.debug = app_config.LOG

try:
    app_config.set_config_mqtt_broker(json.loads(args.mqtt_broker))
except Exception as e:
    print(f'no <mqtt_broker> argument ({e})')
try:
    app_config.set_config_rs485(json.loads(args.rs485))
except Exception as e:
    print(f'no <rs485> argument ({e})')
try:
    app_config.set_config_discovery(json.loads(args.discovery))
except Exception as e:
    print(f'no <discovery> argument ({e})')
try:
    app_config.set_config_parser_mapping(json.loads(args.parser_mapping))
except Exception as e:
    print(f'no <parser_mapping> argument ({e})')
try:
    app_config.set_config_periodic_query_state(json.loads(args.periodic_query_state))
except Exception as e:
    print(f'no <periodic_query_state> argument ({e})')
try:
    app_config.set_config_subphone(json.loads(args.subphone))
except Exception as e:
    print(f'no <subphone> argument ({e})')
try:
    app_config.set_config_etc(json.loads(args.etc))
except Exception as e:
    print(f'no <etc> argument ({e})')

home: Home = get_home('Hillstate-Gwanggyosan', args.config_file_path)
home.initRS485Connection()


def onExitApp():
    print("Web server is closing...")
    home.release()


atexit.register(onExitApp)

if __name__ == '__main__':
    app.run(host=app_config.HOST, port=app_config.PORT, debug=app_config.LOG)
