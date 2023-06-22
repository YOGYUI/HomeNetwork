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


@api.route('/hems', methods=['GET', 'POST'])
def hems():
    return render_template("hems.html")


@api.route('/hems/update', methods=['GET', 'POST'])
def hems_update():
    home = get_home()
    now = datetime.now()
    obj = {'current_time': now.strftime('%Y-%m-%d %H:%M:%S')}
    
    hems = home.findDevice(DeviceType.HEMS, 0, 0)
    if hems is not None:
        data = hems.data
        if 'last_recv_time' in data.keys():
            obj['last_recv_time'] = data.get('last_recv_time').strftime('%Y-%m-%d %H:%M:%S')

        obj['electricity_current'] = data.get('electricity_current')
        obj['electricity_history_cur_month'] = data.get('electricity_history_cur_month')
        obj['electricity_history_1m_ago'] = data.get('electricity_history_1m_ago')
        obj['electricity_history_2m_ago'] = data.get('electricity_history_2m_ago')
        obj['electricity_otheraverage_cur_month'] = data.get('electricity_otheraverage_cur_month')
        obj['electricity_otheraverage_1m_ago'] = data.get('electricity_otheraverage_1m_ago')
        obj['electricity_otheraverage_2m_ago'] = data.get('electricity_otheraverage_2m_ago')
        obj['electricity_fee_cur_month'] = data.get('electricity_fee_cur_month')
        obj['electricity_fee_1m_ago'] = data.get('electricity_fee_1m_ago')
        obj['electricity_fee_2m_ago'] = data.get('electricity_fee_2m_ago')
        obj['electricity_co2_cur_month'] = data.get('electricity_co2_cur_month')
        obj['electricity_co2_1m_ago'] = data.get('electricity_co2_1m_ago')
        obj['electricity_co2_2m_ago'] = data.get('electricity_co2_2m_ago')
        obj['electricity_target'] = data.get('electricity_target')

        # obj['water_current'] = data.get('water_current')
        obj['water_history_cur_month'] = data.get('water_history_cur_month')
        obj['water_history_1m_ago'] = data.get('water_history_1m_ago')
        obj['water_history_2m_ago'] = data.get('water_history_2m_ago')
        obj['water_otheraverage_cur_month'] = data.get('water_otheraverage_cur_month')
        obj['water_otheraverage_1m_ago'] = data.get('water_otheraverage_1m_ago')
        obj['water_otheraverage_2m_ago'] = data.get('water_otheraverage_2m_ago')
        obj['water_fee_cur_month'] = data.get('water_fee_cur_month')
        obj['water_fee_1m_ago'] = data.get('water_fee_1m_ago')
        obj['water_fee_2m_ago'] = data.get('water_fee_2m_ago')
        obj['water_co2_cur_month'] = data.get('water_co2_cur_month')
        obj['water_co2_1m_ago'] = data.get('water_co2_1m_ago')
        obj['water_co2_2m_ago'] = data.get('water_co2_2m_ago')
        obj['water_target'] = data.get('water_target')

        # obj['gas_current'] = data.get('gas_current')
        obj['gas_history_cur_month'] = data.get('gas_history_cur_month')
        obj['gas_history_1m_ago'] = data.get('gas_history_1m_ago')
        obj['gas_history_2m_ago'] = data.get('gas_history_2m_ago')
        obj['gas_otheraverage_cur_month'] = data.get('gas_otheraverage_cur_month')
        obj['gas_otheraverage_1m_ago'] = data.get('gas_otheraverage_1m_ago')
        obj['gas_otheraverage_2m_ago'] = data.get('gas_otheraverage_2m_ago')
        obj['gas_fee_cur_month'] = data.get('gas_fee_cur_month')
        obj['gas_fee_1m_ago'] = data.get('gas_fee_1m_ago')
        obj['gas_fee_2m_ago'] = data.get('gas_fee_2m_ago')
        obj['gas_co2_cur_month'] = data.get('gas_co2_cur_month')
        obj['gas_co2_1m_ago'] = data.get('gas_co2_1m_ago')
        obj['gas_co2_2m_ago'] = data.get('gas_co2_2m_ago')
        obj['gas_target'] = data.get('gas_target')

        # obj['hotwater_current'] = data.get('hotwater_current')
        obj['hotwater_history_cur_month'] = data.get('hotwater_history_cur_month')
        obj['hotwater_history_1m_ago'] = data.get('hotwater_history_1m_ago')
        obj['hotwater_history_2m_ago'] = data.get('hotwater_history_2m_ago')
        obj['hotwater_otheraverage_cur_month'] = data.get('hotwater_otheraverage_cur_month')
        obj['hotwater_otheraverage_1m_ago'] = data.get('hotwater_otheraverage_1m_ago')
        obj['hotwater_otheraverage_2m_ago'] = data.get('hotwater_otheraverage_2m_ago')
        obj['hotwater_fee_cur_month'] = data.get('hotwater_fee_cur_month')
        obj['hotwater_fee_1m_ago'] = data.get('hotwater_fee_1m_ago')
        obj['hotwater_fee_2m_ago'] = data.get('hotwater_fee_2m_ago')
        obj['hotwater_co2_cur_month'] = data.get('hotwater_co2_cur_month')
        obj['hotwater_co2_1m_ago'] = data.get('hotwater_co2_1m_ago')
        obj['hotwater_co2_2m_ago'] = data.get('hotwater_co2_2m_ago')
        obj['hotwater_target'] = data.get('hotwater_target')

        # obj['heating_current'] = data.get('heating_current')
        obj['heating_history_cur_month'] = data.get('heating_history_cur_month')
        obj['heating_history_1m_ago'] = data.get('heating_history_1m_ago')
        obj['heating_history_2m_ago'] = data.get('heating_history_2m_ago')
        obj['heating_otheraverage_cur_month'] = data.get('heating_otheraverage_cur_month')
        obj['heating_otheraverage_1m_ago'] = data.get('heating_otheraverage_1m_ago')
        obj['heating_otheraverage_2m_ago'] = data.get('heating_otheraverage_2m_ago')
        obj['heating_fee_cur_month'] = data.get('heating_fee_cur_month')
        obj['heating_fee_1m_ago'] = data.get('heating_fee_1m_ago')
        obj['heating_fee_2m_ago'] = data.get('heating_fee_2m_ago')
        obj['heating_co2_cur_month'] = data.get('heating_co2_cur_month')
        obj['heating_co2_1m_ago'] = data.get('heating_co2_1m_ago')
        obj['heating_co2_2m_ago'] = data.get('heating_co2_2m_ago')
        obj['heating_target'] = data.get('heating_target')

    return jsonify(obj)
