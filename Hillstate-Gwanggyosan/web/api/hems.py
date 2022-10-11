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


@api.route('/hems', methods=['GET', 'POST'])
def hems():
    return render_template("hems.html")


@api.route('/hems/update', methods=['GET', 'POST'])
def hems_update():
    home = get_home()
    hems = home.hems_info
    now = datetime.now()
    obj = {'current_time': now.strftime('%Y-%m-%d %H:%M:%S')}
    if 'last_recv_time' in hems.keys():
        obj['last_recv_time'] = hems.get('last_recv_time').strftime('%Y-%m-%d %H:%M:%S')

    obj['electricity_current'] = hems.get('electricity_current')
    obj['electricity_history_cur_month'] = hems.get('electricity_history_cur_month')
    obj['electricity_history_1m_ago'] = hems.get('electricity_history_1m_ago')
    obj['electricity_history_2m_ago'] = hems.get('electricity_history_2m_ago')
    obj['electricity_otheraverage_cur_month'] = hems.get('electricity_otheraverage_cur_month')
    obj['electricity_otheraverage_1m_ago'] = hems.get('electricity_otheraverage_1m_ago')
    obj['electricity_otheraverage_2m_ago'] = hems.get('electricity_otheraverage_2m_ago')
    obj['electricity_fee_cur_month'] = hems.get('electricity_fee_cur_month')
    obj['electricity_fee_1m_ago'] = hems.get('electricity_fee_1m_ago')
    obj['electricity_fee_2m_ago'] = hems.get('electricity_fee_2m_ago')
    obj['electricity_co2_cur_month'] = hems.get('electricity_co2_cur_month')
    obj['electricity_co2_1m_ago'] = hems.get('electricity_co2_1m_ago')
    obj['electricity_co2_2m_ago'] = hems.get('electricity_co2_2m_ago')
    obj['electricity_target'] = hems.get('electricity_target')

    # obj['water_current'] = hems.get('water_current')
    obj['water_history_cur_month'] = hems.get('water_history_cur_month')
    obj['water_history_1m_ago'] = hems.get('water_history_1m_ago')
    obj['water_history_2m_ago'] = hems.get('water_history_2m_ago')
    obj['water_otheraverage_cur_month'] = hems.get('water_otheraverage_cur_month')
    obj['water_otheraverage_1m_ago'] = hems.get('water_otheraverage_1m_ago')
    obj['water_otheraverage_2m_ago'] = hems.get('water_otheraverage_2m_ago')
    obj['water_fee_cur_month'] = hems.get('water_fee_cur_month')
    obj['water_fee_1m_ago'] = hems.get('water_fee_1m_ago')
    obj['water_fee_2m_ago'] = hems.get('water_fee_2m_ago')
    obj['water_co2_cur_month'] = hems.get('water_co2_cur_month')
    obj['water_co2_1m_ago'] = hems.get('water_co2_1m_ago')
    obj['water_co2_2m_ago'] = hems.get('water_co2_2m_ago')
    obj['water_target'] = hems.get('water_target')

    # obj['gas_current'] = hems.get('gas_current')
    obj['gas_history_cur_month'] = hems.get('gas_history_cur_month')
    obj['gas_history_1m_ago'] = hems.get('gas_history_1m_ago')
    obj['gas_history_2m_ago'] = hems.get('gas_history_2m_ago')
    obj['gas_otheraverage_cur_month'] = hems.get('gas_otheraverage_cur_month')
    obj['gas_otheraverage_1m_ago'] = hems.get('gas_otheraverage_1m_ago')
    obj['gas_otheraverage_2m_ago'] = hems.get('gas_otheraverage_2m_ago')
    obj['gas_fee_cur_month'] = hems.get('gas_fee_cur_month')
    obj['gas_fee_1m_ago'] = hems.get('gas_fee_1m_ago')
    obj['gas_fee_2m_ago'] = hems.get('gas_fee_2m_ago')
    obj['gas_co2_cur_month'] = hems.get('gas_co2_cur_month')
    obj['gas_co2_1m_ago'] = hems.get('gas_co2_1m_ago')
    obj['gas_co2_2m_ago'] = hems.get('gas_co2_2m_ago')
    obj['gas_target'] = hems.get('gas_target')

    # obj['hotwater_current'] = hems.get('hotwater_current')
    obj['hotwater_history_cur_month'] = hems.get('hotwater_history_cur_month')
    obj['hotwater_history_1m_ago'] = hems.get('hotwater_history_1m_ago')
    obj['hotwater_history_2m_ago'] = hems.get('hotwater_history_2m_ago')
    obj['hotwater_otheraverage_cur_month'] = hems.get('hotwater_otheraverage_cur_month')
    obj['hotwater_otheraverage_1m_ago'] = hems.get('hotwater_otheraverage_1m_ago')
    obj['hotwater_otheraverage_2m_ago'] = hems.get('hotwater_otheraverage_2m_ago')
    obj['hotwater_fee_cur_month'] = hems.get('hotwater_fee_cur_month')
    obj['hotwater_fee_1m_ago'] = hems.get('hotwater_fee_1m_ago')
    obj['hotwater_fee_2m_ago'] = hems.get('hotwater_fee_2m_ago')
    obj['hotwater_co2_cur_month'] = hems.get('hotwater_co2_cur_month')
    obj['hotwater_co2_1m_ago'] = hems.get('hotwater_co2_1m_ago')
    obj['hotwater_co2_2m_ago'] = hems.get('hotwater_co2_2m_ago')
    obj['hotwater_target'] = hems.get('hotwater_target')

    # obj['heating_current'] = hems.get('heating_current')
    obj['heating_history_cur_month'] = hems.get('heating_history_cur_month')
    obj['heating_history_1m_ago'] = hems.get('heating_history_1m_ago')
    obj['heating_history_2m_ago'] = hems.get('heating_history_2m_ago')
    obj['heating_otheraverage_cur_month'] = hems.get('heating_otheraverage_cur_month')
    obj['heating_otheraverage_1m_ago'] = hems.get('heating_otheraverage_1m_ago')
    obj['heating_otheraverage_2m_ago'] = hems.get('heating_otheraverage_2m_ago')
    obj['heating_fee_cur_month'] = hems.get('heating_fee_cur_month')
    obj['heating_fee_1m_ago'] = hems.get('heating_fee_1m_ago')
    obj['heating_fee_2m_ago'] = hems.get('heating_fee_2m_ago')
    obj['heating_co2_cur_month'] = hems.get('heating_co2_cur_month')
    obj['heating_co2_1m_ago'] = hems.get('heating_co2_1m_ago')
    obj['heating_co2_2m_ago'] = hems.get('heating_co2_2m_ago')
    obj['heating_target'] = hems.get('heating_target')

    return jsonify(obj)
