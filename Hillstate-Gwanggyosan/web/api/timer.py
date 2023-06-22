# TODO: rs485 및 파서를 리스트로 객체화하게 바꾸었다
# 코드 구조를 전면적으로 개편해야 한다
from . import api
from flask import render_template, jsonify, request
from wtforms import Form, IntegerField, SelectField, validators
from datetime import datetime
import os
import sys
import json
import http
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/web/api/
PROJPATH = os.path.dirname(os.path.dirname(CURPATH))  # {$PROJECT}/
INCPATH = os.path.join(PROJPATH, 'Include')  # {$PROJECT}/Include/
sys.path.extend([CURPATH, PROJPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH, INCPATH
from Include import get_home
from Common import DeviceType


class TesfForm(Form):
    ontime = IntegerField('on_time', [validators.Length(min=0)])
    offtime = IntegerField('off_time', [validators.Length(min=0)])
    repeat = SelectField('repeat')


def get_timer_info() -> list:
    home = get_home()    
    info = []
    for i in range(4):
        d = dict()
        thermostat = home.findDevice(DeviceType.THERMOSTAT, 0, i + 1)
        if thermostat is not None:
            d['has_thermostat'] = True
            d['thermostat_timer_running'] = int(thermostat.isTimerOnOffRunning())
            params = thermostat.timer_onoff_params
            d['thermostat_on_time'] = params.get('on_time')
            d['thermostat_off_time'] = params.get('off_time')
            d['thermostat_repeat'] = int(params.get('repeat'))
            d['thermostat_off_when_terminate'] = int(params.get('off_when_terminate'))
        else:
            d['has_thermostat'] = False
            d['thermostat_timer_running'] = 0
            d['thermostat_on_time'] = 0
            d['thermostat_off_time'] = 0
            d['thermostat_repeat'] = 0
            d['thermostat_off_when_terminate'] = 0
        
        airconditioner = home.findDevice(DeviceType.AIRCONDITIONER, 0, i + 1)
        if airconditioner is not None:
            d['has_airconditioner'] = True
            d['airconditioner_timer_running'] = int(airconditioner.isTimerOnOffRunning())
            params = airconditioner.timer_onoff_params
            d['airconditioner_on_time'] = params.get('on_time')
            d['airconditioner_off_time'] = params.get('off_time')
            d['airconditioner_repeat'] = int(params.get('repeat'))
            d['airconditioner_off_when_terminate'] = int(params.get('off_when_terminate'))
        else:
            d['has_airconditioner'] = False
            d['airconditioner_timer_running'] = 0
            d['airconditioner_on_time'] = 0
            d['airconditioner_off_time'] = 0
            d['airconditioner_repeat'] = 0
            d['airconditioner_off_when_terminate'] = 0
        
        info.append(d)
    return info


@api.route('/timer', methods=['GET', 'POST'])
def timer():
    timer_info = get_timer_info()
    return render_template(
        'timer.html',
        room1=timer_info[0],
        room2=timer_info[1],
        room3=timer_info[2],
        room4=timer_info[3]
    )


@api.route('/timer/update', methods=['GET', 'POST'])
def timer_update():
    timer_info = get_timer_info()
    return render_template(
        'timer.html',
        room1=timer_info[0],
        room2=timer_info[1],
        room3=timer_info[2],
        room4=timer_info[3]
    )


@api.route('/timer/set/<room_idx>/<dev_type>', methods=['POST'])
def timer_activate(room_idx: str, dev_type: str):
    home = get_home()
    try:
        data = json.loads(request.get_data())
        room_idx = int(room_idx) - 1

        if dev_type == 'cool':
            dev = home.findDevice(DeviceType.AIRCONDITIONER, 0, room_idx)
        elif dev_type == 'heat':
            dev = home.findDevice(DeviceType.THERMOSTAT, 0, room_idx)
        else:
            return '', http.HTTPStatus.NO_CONTENT

        if dev is not None:
            if 'activate' in data.keys():
                value = int(data.get('activate'))
                dev.startTimerOnOff() if value else dev.stopTimerOnOff()
            elif 'on_time' in data.keys() and 'off_time' in data.keys() and 'repeat' in data.keys():
                on_time = int(data.get('on_time'))
                off_time = int(data.get('off_time'))
                repeat = bool(int(data.get('repeat')))
                dev.setTimerOnOffParams(on_time, off_time, repeat)
        else:
            return '', http.HTTPStatus.NO_CONTENT
    except Exception as e:
        print(e)
    return '', http.HTTPStatus.NO_CONTENT
