import http
from flask import Flask, request, json, render_template, jsonify
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from common import writeLog
from homeDef import Home

home: Home


class MyFlaskApp(Flask):
    def run(self, host=None, port=None, debug=None, load_dotenv=True, **options):
        # if not self.debug or os.getenv('WERKZEUG_RUN_MAIN') == 'true':
        with self.app_context():
            # home.initDevice()
            pass
        super(MyFlaskApp, self).run(host=host, port=port, debug=debug, load_dotenv=load_dotenv, **options)


app = MyFlaskApp(__name__)
auth = HTTPBasicAuth()
users = {
    'yogyui': generate_password_hash("N3EH~u~C+H74r5!2")
}


@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    writeLog('Unauthorized', app)
    return False


@app.route('/')
@app.route('/home')
def index():
    return render_template('index.html')


@app.route('/packet_sender')
def packet_sender():
    return render_template('packet_sender.html')


@app.route('/packet_sender/send/<target>', methods=['POST'])
def send(target):
    if target == 'energy':
        ser = home.serial_485_energy
    elif target == 'control':
        ser = home.serial_485_control
    elif target == 'smart1':
        ser = home.serial_485_smart1
    else:
        ser = home.serial_485_smart2
    req = request.get_data().decode(encoding='utf-8')
    req = req.replace('\r', '')
    req = req.replace('\n', '')
    packet = req[7:].strip().upper() if 'packet=' in req else ''
    msg = ''
    if len(packet) > 0:
        try:
            temp = packet.replace(' ', '')
            barr = bytearray([])
            for i in range(len(temp) // 2):
                barr.extend([int(temp[i * 2:(i + 1) * 2], 16)])
            ser.sendData(barr)
            msg = 'Sent <{}>'.format(' '.join(['%02X' % x for x in barr]))
        except Exception as e:
            msg = str(e)
    return render_template('packet_sender.html', target=target, result=msg, packet=packet)


@app.route('/packet_log')
def packet_log():
    return render_template(
        'packet_log.html', 
        enable_log_energy_31=int(home.enable_log_energy_31),
        enable_log_energy_41=int(home.enable_log_energy_41),
        enable_log_energy_42=int(home.enable_log_energy_42),
        enable_log_energy_d1=int(home.enable_log_energy_d1),
        enable_log_energy_room_1=int(home.enable_log_energy_room_1),
        enable_log_energy_room_2=int(home.enable_log_energy_room_2),
        enable_log_energy_room_3=int(home.enable_log_energy_room_3),
        enable_log_control_28=int(home.enable_log_control_28),
        enable_log_control_31=int(home.enable_log_control_31),
        enable_log_control_61=int(home.enable_log_control_61)
    )


@app.route('/packet_log/update', methods=['POST'])
def packet_log_update():
    p1 = '<br>'.join([' '.join(['%02X' % y for y in x])for x in home.packets_energy[::-1]])
    p2 = '<br>'.join([' '.join(['%02X' % y for y in x])for x in home.packets_control[::-1]])
    p3 = '<br>'.join([' '.join(['%02X' % y for y in x])for x in home.packets_smart1[::-1]])
    return jsonify({
        'energy': p1,
        'control': p2,
        'smart1': p3
    })


@app.route('/packet_log/clear/<target>', methods=['POST'])
def packet_log_clear(target):
    if target == 'energy':
        home.packets_energy.clear()
    elif target == 'control':
        home.packets_control.clear()
    elif target == 'smart1':
        home.packets_smart1.clear()
    return '', http.HTTPStatus.NO_CONTENT


@app.route('/packet_log/<device>/enable/<target>', methods=['POST'])
def packet_log_energy_enable(device, target):
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


@app.route('/outlet')
def outlet():
    return render_template('outlet.html')


@app.route('/outlet/update', methods=['POST'])
def outlet_update():
    return jsonify({
        'room1_outlet1': home.rooms[1].outlets[0].measurement,
        'room1_outlet2': home.rooms[1].outlets[1].measurement,
        'room1_outlet3': home.rooms[1].outlets[2].measurement,
        'room2_outlet1': home.rooms[2].outlets[0].measurement,
        'room2_outlet2': home.rooms[2].outlets[1].measurement,
        'room3_outlet1': home.rooms[3].outlets[0].measurement,
        'room3_outlet2': home.rooms[3].outlets[1].measurement
    })


# homebridge APIs from Here...
@app.route('/light', methods=['POST'])
@auth.login_required
def light_process():
    response = ""
    if not request.is_json:
        req = request.get_data().decode(encoding='utf-8')
        req = req.replace('\r', '')
        req = req.replace('\n', '')
        if 'json=' in req:
            params = json.loads(req[5:])
        else:
            if req[0] == '{' and req[-1] == '}':
                try:
                    params = json.loads(req)
                except Exception:
                    params = {}
            else:
                params = {}
    else:
        params = json.loads(request.get_data(), encoding='utf-8')

    writeLog('light_process::POST json >> {}'.format(params), app)
    try:
        room_idx = params['room']
        room = home.rooms[room_idx]
        if 'light' in params.keys():
            dev_idx = params['light']
            dev = room.lights[dev_idx]
            if 'command' in params.keys():
                value = 1 if params['command'].lower() == 'on' else 0
                home.command(
                    device=dev,
                    category='state',
                    target=value,
                    room_idx=room_idx,
                    dev_idx=dev_idx
                )
            elif 'status' in params.keys():
                response = '{}'.format(dev.state)
    except Exception:
        pass
    return response


@app.route('/thermo/<room>/status', methods=['GET'])
@auth.login_required
def thermostat_get_status(room):
    room_idx = int(room[-1])
    room = home.rooms[room_idx]
    dev = room.thermostat
    obj = {
        'targetHeatingCoolingState': dev.state,
        'targetTemperature': dev.temperature_setting,
        'currentHeatingCoolingState': dev.state,
        'currentTemperature': dev.temperature_current
        }
    writeLog('Response ({}::{}): {}'.format(room.name, dev.name, obj), app)
    return jsonify(obj)


@app.route('/thermo/<room>/targetHeatingCoolingState', methods=['GET'])
@auth.login_required
def thermostat_set_state(room):
    room_idx = int(room[-1])
    room = home.rooms[room_idx]
    dev = room.thermostat
    value = request.args.get('value', default=1, type=int)
    writeLog('Command ({}::{}): set_state: {}'.format(room.name, dev.name, value), app)
    home.command(
        device=dev,
        category='state',
        target=value,
        func=home.sendSerialControlPacket
    )
    return ''


@app.route('/thermo/<room>/targetTemperature', methods=['GET'])
@auth.login_required
def thermostat_set_target_temperature(room):
    room_idx = int(room[-1])
    room = home.rooms[room_idx]
    dev = room.thermostat
    value = request.args.get('value', default=20., type=float)
    writeLog('Command ({}::{}): set_target_temperature: {}'.format(room.name, dev.name, value), app)
    home.command(
        device=dev,
        category='temperature',
        target=value
    )
    return ''


@app.route('/gasvalve/status', methods=['GET'])
@auth.login_required
def gasvalve_get_status():
    dev = home.gas_valve
    obj = {
        'currentState': int(dev.state == 1)
        }
    writeLog('Response ({}): {}'.format(dev.name, obj), app)
    return jsonify(obj)


@app.route('/gasvalve/setState', methods=['GET'])
@auth.login_required
def gasvalve_set_state():
    dev = home.gas_valve
    value = request.args.get('value', default=0, type=int)
    writeLog('Command ({}): set_state: {}'.format(dev.name, value), app)
    home.command(
        device=dev,
        category='state',
        target=value
    )
    return ''


@app.route('/ventilator/status', methods=['GET'])
@auth.login_required
def ventilator_get_status():
    dev = home.ventilator
    obj = {
        'currentState': dev.state,
        'rotationSpeed': int(dev.rotation_speed / 3 * 100)
        }
    writeLog('Response ({}): {}'.format(dev.name, obj), app)
    return jsonify(obj)


@app.route('/ventilator/setState', methods=['GET'])
@auth.login_required
def ventilator_set_state():
    dev = home.ventilator
    value = request.args.get('value', default=0, type=int)
    writeLog('Command ({}): set_state: {}'.format(dev.name, value), app)
    home.command(
        device=dev,
        category='state',
        target=value
    )
    return ''


@app.route('/ventilator/setRotationSpeed', methods=['GET'])
@auth.login_required
def ventilator_set_rotation_speed():
    dev = home.ventilator
    value = request.args.get('value', default=0, type=int)
    conv = min(3, max(0, int(value / 100 * 3) + 1))
    writeLog('Command ({}): set_rotation_speed: {} (current: {})'.format(dev.name, conv, dev.rotation_speed), app)
    home.command(
        device=dev,
        category='rotation_speed',
        target=conv
    )
    return ''


@app.route('/elevator', methods=['GET', 'POST'])
# @auth.login_required
def elevator_process():
    req = request.get_data().decode(encoding='utf-8')
    if 'command' in req:
        home.elevator.call_down()
    from datetime import datetime
    return render_template(
        "elevator.html",
        time=datetime.now(),
        state=home.elevator.state, 
        current_floor=home.elevator.current_floor
        )


@app.route('/elevator/update', methods=['GET', 'POST'])
def elevator_update():
    from datetime import datetime
    now = datetime.now()
    dev = home.elevator

    return jsonify({
        'time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'state': dev.state,
        'current_floor': dev.current_floor
    })


if __name__ == '__main__':
    import os
    os.system('clear')

    home = Home(room_info=[
        {'name': 'Empty', 'light_count': 0, 'has_thermostat': False, 'outlet_count': 0},
        {'name': 'Kitchen', 'light_count': 4, 'has_thermostat': True, 'outlet_count': 3},
        {'name': 'Bedroom', 'light_count': 2, 'has_thermostat': True, 'outlet_count': 2},
        {'name': 'Computer', 'light_count': 2, 'has_thermostat': True, 'outlet_count': 2}
    ], name='IPark-Gwanggyo')

    home.initDevices()
    app.run(host='0.0.0.0', port=1234, debug=False)
    home.release()
