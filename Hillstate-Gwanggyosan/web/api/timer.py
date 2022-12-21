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


class TesfForm(Form):
    ontime = IntegerField('on_time', [validators.Length(min=0)])
    offtime = IntegerField('off_time', [validators.Length(min=0)])
    repeat = SelectField('repeat')


def get_timer_info() -> list:
    home = get_home()
    info = []
    for room in home.rooms:
        d = {
            'has_thermostat': int(room.has_thermostat),
            'has_airconditioner': int(room.has_airconditioner)
        }
        if room.has_thermostat:
            thermostat = room.thermostat
            d['thermostat_timer_running'] = int(thermostat.isTimerOnOffRunning())
            params = thermostat.timer_onoff_params
            d['thermostat_on_time'] = params.get('on_time')
            d['thermostat_off_time'] = params.get('off_time')
            d['thermostat_repeat'] = int(params.get('repeat'))
            d['thermostat_off_when_terminate'] = int(params.get('off_when_terminate'))
        if room.has_airconditioner:
            airconditioner = room.airconditioner
            d['airconditioner_timer_running'] = int(airconditioner.isTimerOnOffRunning())
            params = airconditioner.timer_onoff_params
            d['airconditioner_on_time'] = params.get('on_time')
            d['airconditioner_off_time'] = params.get('off_time')
            d['airconditioner_repeat'] = int(params.get('repeat'))
            d['airconditioner_off_when_terminate'] = int(params.get('off_when_terminate'))
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
            dev = home.rooms[room_idx].airconditioner
        elif dev_type == 'heat':
            dev = home.rooms[room_idx].thermostat
        else:
            return '', http.HTTPStatus.NO_CONTENT

        if 'activate' in data.keys():
            value = int(data.get('activate'))
            dev.startTimerOnOff() if value else dev.stopTimerOnOff()
        elif 'on_time' in data.keys() and 'off_time' in data.keys() and 'repeat' in data.keys():
            on_time = int(data.get('on_time'))
            off_time = int(data.get('off_time'))
            repeat = bool(int(data.get('repeat')))
            dev.setTimerOnOffParams(on_time, off_time, repeat)
    except Exception as e:
        print(e)
    return '', http.HTTPStatus.NO_CONTENT
