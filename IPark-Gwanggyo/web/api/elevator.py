from . import api
from flask import render_template, jsonify, request
from datetime import datetime
import os
import sys
CURPATH = os.path.dirname(os.path.abspath(__file__))  # /project/web/api/
PROJPATH = os.path.dirname(os.path.dirname(CURPATH))  # /project/
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
from app import get_home


@api.route('/elevator', methods=['GET', 'POST'])
def elevator():
    home = get_home()
    req = request.get_data().decode(encoding='utf-8')
    if 'command' in req:
        home.elevator.call_down()

    return render_template(
        "elevator.html",
        time=datetime.now(),
        state=home.elevator.state,
        current_floor=home.elevator.current_floor
    )


@api.route('/elevator/update', methods=['GET', 'POST'])
def elevator_update():
    home = get_home()
    now = datetime.now()
    dev = home.elevator

    return jsonify({
        'time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'state': dev.state,
        'current_floor': dev.current_floor
    })
