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
    
    return render_template('timer.html')

@api.route('/timer/update', methods=['GET', 'POST'])
def timer_update():
    timer_info = get_timer_info()
