from . import api
from flask import render_template, jsonify, request
import http
import os
import sys
CURPATH = os.path.dirname(os.path.abspath(__file__))  # /project/web/api/
PROJPATH = os.path.dirname(os.path.dirname(CURPATH))  # /project/
INCPATH = os.path.join(PROJPATH, 'Include')  # /project/Include
sys.path.extend([CURPATH, PROJPATH, INCPATH])
sys.path = list(set(sys.path))
from Include import get_home


@api.route('/packet/logger', methods=['GET', 'POST'])
def packet_logger():
    return render_template('packet_log.html')


@api.route('/packet/logger/update', methods=['POST'])
def packet_logger_update():
    home = get_home()
    p1 = '<br>'.join([' '.join(['%02X' % y for y in x]) for x in home.packets_energy[::-1]])
    p2 = '<br>'.join([' '.join(['%02X' % y for y in x]) for x in home.packets_control[::-1]])
    p3 = '<br>'.join([' '.join(['%02X' % y for y in x]) for x in home.packets_smart1[::-1]])
    return jsonify({'energy': p1, 'control': p2, 'smart1': p3})


@api.route('/packet/logger/clear/<target>', methods=['POST'])
def packet_log_clear(target):
    home = get_home()
    if target == 'energy':
        home.packets_energy.clear()
    elif target == 'control':
        home.packets_control.clear()
    elif target == 'smart1':
        home.packets_smart1.clear()
    return '', http.HTTPStatus.NO_CONTENT


@api.route('/packet/logger/<device>/enable/<target>', methods=['POST'])
def packet_log_enable(device, target):
    home = get_home()
    req = request.get_data().decode(encoding='utf-8')
    value = int(req[6:].strip()) if 'value=' in req else 1
    if device == 'energy':
        if target == '31':
            home.enable_log_energy_31 = bool(value)
        elif target == '41':
            home.enable_log_energy_41 = bool(value)
        elif target == '42':
            home.enable_log_energy_42 = bool(value)
        elif target == 'D1':
            home.enable_log_energy_d1 = bool(value)
        elif target == 'room1':
            home.enable_log_energy_room_1 = bool(value)
        elif target == 'room2':
            home.enable_log_energy_room_2 = bool(value)
        elif target == 'room3':
            home.enable_log_energy_room_3 = bool(value)
        home.packets_energy.clear()
    elif device == 'control':
        if target == '28':
            home.enable_log_control_28 = bool(value)
        elif target == '31':
            home.enable_log_control_31 = bool(value)
        elif target == '61':
            home.enable_log_control_61 = bool(value)
        home.packets_control.clear()
    return '', http.HTTPStatus.NO_CONTENT
