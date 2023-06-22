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
from Common import DeviceType


def get_state_string() -> str:
    home = get_home()
    elevator = home.findDevice(DeviceType.ELEVATOR, 0, 0)
    if elevator is None:
        return 'NOT DEFINED'
        
    dev_info_list = elevator.dev_info_list
    if len(dev_info_list) == 0:
        state_str = 'IDLE'
    else:
        state_str = ''    
        for info in dev_info_list:
            state_str += f'{info.index}호기: '
            img_path_list = []
            try:
                if info.floor[0] == 'B':
                    img_path_list.append(f'/static/seven_seg_b.png')
                else:
                    img_path_list.append(f'/static/seven_seg_{int(info.floor[0])}.png')
            except Exception:
                img_path_list.append('/static/seven_seg_null.png')
            try:
                img_path_list.append(f'/static/seven_seg_{int(info.floor[1])}.png')
            except Exception:
                img_path_list.append('/static/seven_seg_null.png')
            
            img_width, img_height = 60, 80
            for img_path in img_path_list:
                state_str += f'<img width="{img_width}" height="{img_height}" src="{img_path}"/>'
            
            state_str += ' '

            if elevator.state == 0:  # idle
                pass
            elif elevator.state == 1:  # arrived
                state_str += f'<img width="{img_height}" height="{img_height}" src="/static/destination.png"/>'
            else:
                if info.direction.value == 5:  # moving up
                    state_str += f'<img width="{img_height}" height="{img_height}" src="/static/arrow_up.png"/>'
                elif info.direction.value == 6:  # moving down
                    state_str += f'<img width="{img_height}" height="{img_height}" src="/static/arrow_down.png"/>'
            state_str += "<br>"
    return state_str


@api.route('/elevator_ctrl', methods=['GET', 'POST'])
def elevator_ctrl():
    home = get_home()
    now = datetime.now()

    req = request.get_data().decode(encoding='utf-8')
    if 'command_call_down' in req:
        home.onMqttCommandElevator('', {'state': 6})
    elif 'command_call_up' in req:
        home.onMqttCommandElevator('', {'state': 5})

    return render_template(
        "elevator_ctrl.html",
        current_time=now.strftime('%Y-%m-%d %H:%M:%S'),
        state=get_state_string()
    )


@api.route('/elevator_ctrl/update', methods=['GET', 'POST'])
def elevator_update():
    home = get_home()
    now = datetime.now()

    return jsonify({
        'current_time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'state': get_state_string()
    })
