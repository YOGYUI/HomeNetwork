# TODO: rs485 및 파서를 리스트로 객체화하게 바꾸었다
# 코드 구조를 전면적으로 개편해야 한다
from . import api
import os
import sys
import http
import datetime
from flask import render_template, jsonify, request
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/web/api/
PROJPATH = os.path.dirname(os.path.dirname(CURPATH))  # {$PROJECT}/
INCPATH = os.path.join(PROJPATH, 'Include')  # {$PROJECT}/Include/
sys.path.extend([CURPATH, PROJPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH, INCPATH
from Include import get_home


def prettifyPacket(packet: bytearray) -> str:
    return ' '.join(['%02X' % x for x in packet])


def stringifyPacketInfo(info: dict) -> str:
    device: str = info.get('device')
    timestamp: datetime.datetime = info.get('timestamp')
    packet: bytearray = info.get('packet')

    return f" [{timestamp.strftime('%H:%M:%S.%f')[:-3]}] [{device}] {prettifyPacket(packet)}"


@api.route('/packet_logger', methods=['GET', 'POST'])
def packet_logger():
    home = get_home()
    rs485_info_list = home.rs485_info_list
    if len(rs485_info_list) > 0:
        parser = rs485_info_list[0].parser
        enable_header_light_19 = parser.enable_store_packet_header_19
        enable_header_light_1E = parser.enable_store_packet_header_1E
        enable_header_light_1F = parser.enable_store_packet_header_1F
    else:
        enable_header_light_19 = False
        enable_header_light_1E = False
        enable_header_light_1F = False
    
    if len(rs485_info_list) > 1:
        parser = rs485_info_list[1].parser
        enable_header_various_18 = parser.enable_store_packet_header_18
        enable_header_various_1B = parser.enable_store_packet_header_1B
        enable_header_various_1C = parser.enable_store_packet_header_1C
        enable_header_various_2A = parser.enable_store_packet_header_2A
        enable_header_various_2B = parser.enable_store_packet_header_2B
        enable_header_various_34 = parser.enable_store_packet_header_34
        enable_header_various_43 = parser.enable_store_packet_header_43
        enable_header_various_44 = parser.enable_store_packet_header_44
        enable_header_various_48 = parser.enable_store_packet_header_48
    else:
        enable_header_various_18 = False
        enable_header_various_1B = False
        enable_header_various_1C = False
        enable_header_various_2A = False
        enable_header_various_2B = False
        enable_header_various_34 = False
        enable_header_various_43 = False
        enable_header_various_44 = False
        enable_header_various_48 = False
        
    if len(rs485_info_list) > 2:
        parser = rs485_info_list[2].parser
        enable_subphone = parser.enable_store_packet_general
    else:
        enable_subphone = False
    
    return render_template(
        'packet_logger.html', 
        enable_header_light_19=int(enable_header_light_19),
        enable_header_light_1E=int(enable_header_light_1E),
        enable_header_light_1F=int(enable_header_light_1F),
        enable_header_various_18=int(enable_header_various_18),
        enable_header_various_1B=int(enable_header_various_1B),
        enable_header_various_1C=int(enable_header_various_1C),
        enable_header_various_2A=int(enable_header_various_2A),
        enable_header_various_2B=int(enable_header_various_2B),
        enable_header_various_34=int(enable_header_various_34),
        enable_header_various_43=int(enable_header_various_43),
        enable_header_various_44=int(enable_header_various_44),
        enable_header_various_48=int(enable_header_various_48),
        enable_subphone=int(enable_subphone)
    )


@api.route('/packet_logger/update', methods=['GET', 'POST'])
def packet_logger_update():
    home = get_home()
    
    rs485_info_list = home.rs485_info_list
    if len(rs485_info_list) > 0:
        parser = rs485_info_list[0].parser
        packets_light = parser.packet_storage
    else:
        packets_light = []

    if len(rs485_info_list) > 1:
        parser = rs485_info_list[1].parser
        packets_various = parser.packet_storage
    else:
        packets_various = []

    if len(rs485_info_list) > 2:
        parser = rs485_info_list[2].parser
        packets_subphone = parser.packet_storage
    else:
        packets_subphone = []
    
    str_packet_light = [stringifyPacketInfo(x) for x in packets_light[::-1]]
    str_packet_various = [stringifyPacketInfo(x) for x in packets_various[::-1]]
    str_packet_subphone = [stringifyPacketInfo(x) for x in packets_subphone[::-1]]

    return jsonify({
        'light': '<br>'.join(str_packet_light),
        'various': '<br>'.join(str_packet_various),
        'subphone': '<br>'.join(str_packet_subphone)
    })


@api.route('/packet_logger/clear/<target>', methods=['POST'])
def packet_logger_clear(target):
    home = get_home()
    rs485_info_list = home.rs485_info_list
    if target == 'light':
        if len(rs485_info_list) > 0:
            parser = rs485_info_list[0].parser
            parser.clearPacketStorage()
    elif target == 'various':
        if len(rs485_info_list) > 1:
            parser = rs485_info_list[1].parser
            parser.clearPacketStorage()
    elif target == 'subphone':
        if len(rs485_info_list) > 2:
            parser = rs485_info_list[2].parser
            parser.clearPacketStorage()
    
    return '', http.HTTPStatus.NO_CONTENT


@api.route('/packet_logger/enable/<target>/<header>', methods=['POST'])
def packet_logger_enable_header(target, header):
    home = get_home()
    rs485_info_list = home.rs485_info_list
    req = request.get_data().decode(encoding='utf-8')
    value = int(req[6:].strip()) if 'value=' in req else 1
    if target == 'light':
        if len(rs485_info_list) > 0:
            parser = rs485_info_list[0].parser
            if header == '19':
                parser.enable_store_packet_header_19 = bool(value)
            elif header == '1E':
                parser.enable_store_packet_header_1E = bool(value)
            elif header == '1F':
                parser.enable_store_packet_header_1F = bool(value)
            parser.clearPacketStorage()
    elif target == 'various':
        if len(rs485_info_list) > 1:
            parser = rs485_info_list[1].parser
            if header == '18':
                parser.enable_store_packet_header_18 = bool(value)
            elif header == '1B':
                parser.enable_store_packet_header_1B = bool(value)
            elif header == '1C':
                parser.enable_store_packet_header_1C = bool(value)
            elif header == '2A':
                parser.enable_store_packet_header_2A = bool(value)
            elif header == '2B':
                parser.enable_store_packet_header_2B = bool(value)
            elif header == '34':
                parser.enable_store_packet_header_34 = bool(value)
            elif header == '43':
                parser.enable_store_packet_header_43 = bool(value)
            elif header == '44':
                parser.enable_store_packet_header_44 = bool(value)
            elif header == '48':
                parser.enable_store_packet_header_48 = bool(value)
            parser.clearPacketStorage()
    elif target == 'subphone':
        if len(rs485_info_list) > 2:
            parser = rs485_info_list[2].parser
            parser.enable_store_packet_general = bool(value)
            parser.clearPacketStorage()
    
    return '', http.HTTPStatus.NO_CONTENT
