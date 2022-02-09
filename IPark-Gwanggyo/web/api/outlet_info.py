from . import api
from flask import render_template, jsonify
import os
import sys
CURPATH = os.path.dirname(os.path.abspath(__file__))  # /project/web/api/
PROJPATH = os.path.dirname(os.path.dirname(CURPATH))  # /project/
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
from app import get_home


@api.route('/outlet_info', methods=['GET', 'POST'])
def outlet_info():
    return render_template('outlet.html')


@api.route('/outlet_info/update', methods=['POST'])
def outlet_update():
    home = get_home()
    data = dict()
    for room in home.rooms:
        idx = room.index
        for i, o in enumerate(room.outlets):
            data[f'room{idx}_outlet{i + 1}'] = o.measurement
    return jsonify(data)
