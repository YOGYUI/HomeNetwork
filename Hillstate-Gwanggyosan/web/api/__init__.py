from flask import Blueprint

api = Blueprint('api', __name__)

from . import light_ctrl
from . import outlet_ctrl
from . import elevator_ctrl
from . import packet_logger
from . import hems
from . import timer
from . import system
