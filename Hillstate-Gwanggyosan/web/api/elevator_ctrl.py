from . import api
from flask import render_template, jsonify, request
from datetime import datetime
import os
import sys
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/web/api/
PROJPATH = os.path.dirname(os.path.dirname(CURPATH))  # {$PROJECT}/
INCPATH = os.path.join(PROJPATH, 'Include')  # {$PROJECT}/Include/
sys.path.extend([CURPATH, PROJPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH, INCPATH
from Include import get_home


@api.route('/elevator_ctrl', methods=['GET', 'POST'])
def elevator_ctrl():
    home = get_home()

    req = request.get_data().decode(encoding='utf-8')
    if 'command' in req:
        home.onMqttCommandElevator('', {'state': 6})

    state_str = '??'
    state = home.elevator.state
    if state == 0:
        state_str = 'IDLE'
    elif state == 1:
        state_str = 'ARRIVED'
    elif state in [5, 6]:
        state_str = 'MOVING'
    floor_list = home.elevator.floor_list

    return render_template(
        "elevator_ctrl.html",
        time=datetime.now(),
        state=state_str,
        floor1=floor_list[0],
        floor2=floor_list[1],
    )


@api.route('/elevator_ctrl/update', methods=['GET', 'POST'])
def elevator_update():
    home = get_home()
    now = datetime.now()

    state_str = '??'
    state = home.elevator.state
    if state == 0:
        state_str = 'IDLE'
    elif state == 1:
        state_str = 'ARRIVED'
    elif state in [5, 6]:
        state_str = 'MOVING'
    floor_list = home.elevator.floor_list
    if state ==0:
        floor1 = ''
        floor2 = ''
    else:
        floor1 = floor_list[0]
        floor2 = floor_list[1]

    return jsonify({
        'time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'state': state_str,
        'floor1': floor1,
        'floor2': floor2
    })
