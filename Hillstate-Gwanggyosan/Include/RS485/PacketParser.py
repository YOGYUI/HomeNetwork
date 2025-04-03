import os
import sys
import time
import datetime
from enum import IntEnum, auto, unique
from typing import Union, List
from functools import reduce
from RS485Comm import *
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/Include/RS485
INCPATH = os.path.dirname(CURPATH)  # {$PROJECT}/Include/
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Common import writeLog, DeviceType, HEMSDevType, HEMSCategory


@unique
class ParserType(IntEnum):
    REGULAR = 0         # 일반 RS-485 (baud 9600)
    SUBPHONE = auto()   # 주방 서브폰 (baud 3840)
    UNKNOWN = auto()


class PacketParser:
    name: str = "Parser"
    index: int = 0
    rs485: RS485Comm
    buffer: bytearray
    enable_console_log: bool = False
    chunk_cnt: int = 0
    max_chunk_cnt: int = 1e6
    max_buffer_size: int = 200
    line_busy: bool = False
    type_interpret: ParserType = ParserType.REGULAR

    packet_storage: List[dict]
    max_packet_store_cnt: int = 100

    log_send_result: bool = True

    thermo_len_per_dev: int = 3  # 난방 노멀 쿼리 > 각 기기당 바이트 수는 3 혹은 8?

    # for debugging (todo: remove or refactoring)
    enable_store_packet_header_15: bool = False
    enable_store_packet_header_18: bool = False
    enable_store_packet_header_19: bool = False
    enable_store_packet_header_1A: bool = False
    enable_store_packet_header_1B: bool = False
    enable_store_packet_header_1C: bool = False
    enable_store_packet_header_1E: bool = False
    enable_store_packet_header_1F: bool = False
    enable_store_packet_header_2A: bool = False
    enable_store_packet_header_2B: bool = False
    enable_store_packet_header_34: bool = False
    enable_store_packet_header_43: bool = False
    enable_store_packet_header_44: bool = False
    enable_store_packet_header_48: bool = False
    enable_store_packet_header_4B: bool = False
    enable_store_packet_unknown: bool = True
    enable_store_packet_general: bool = False
    enable_trace_timestamp_packet: bool = False

    def __init__(self, 
                 rs485_instance: RS485Comm, 
                 name: str, 
                 index: int, 
                 send_command_interval_ms: int,
                 send_command_retry_count: int,
                 type_interpret: ParserType = ParserType.REGULAR):
        self.buffer = bytearray()
        self.name = name
        self.index = index
        self.send_command_interval_ms: int = send_command_interval_ms
        self.send_command_retry_count: int = send_command_retry_count
        self.rs485 = rs485_instance
        self.rs485.sig_send_data.connect(self.onSendData)
        self.rs485.sig_recv_data.connect(self.onRecvData)
        self.type_interpret = type_interpret
        self.packet_storage = list()
        self.sig_parse_result = Callback(dict)
        writeLog(f"<{self.name}> initialized (index: {self.index}, " \
                 f"type: {self.type_interpret.name}, " \
                 f"command interval: {self.send_command_interval_ms}ms, " \
                 f"command retry count: {self.send_command_retry_count})", self)

    def __repr__(self):
        repr_txt = f'<{self.name}({self.__class__.__name__} at {hex(id(self))})>'
        return repr_txt

    def release(self):
        self.buffer.clear()

    def sendPacket(self, packet: Union[bytes, bytearray], log: bool = True):
        self.log_send_result = log
        self.rs485.sendData(packet)

    def sendString(self, packet_str: str):
        self.rs485.sendData(bytearray([int(x, 16) for x in packet_str.split(' ')]))

    def onSendData(self, data: bytes):
        if self.log_send_result:
            msg = ' '.join(['%02X' % x for x in data])
            self.log(f"Send >> {msg}")
        self.log_send_result = True

    def onRecvData(self, data: bytes):
        self.line_busy = True
        if len(self.buffer) > self.max_buffer_size:
            self.buffer.clear()
            self.line_busy = False
        self.buffer.extend(data)
        self.handlePacket()

    def log(self, message: str):
        writeLog(f"<{self.name}> {message}", self)

    def handlePacket(self):
        # self.log(f'buffer: {self.prettifyPacket(self.buffer)}')
        if len(self.buffer) == 0:
            time.sleep(1e-3)
        
        if self.type_interpret is ParserType.REGULAR:
            count = 0
            while True:
                if count >= 10:
                    self.log(f'failed to interprete buffer ({count} times loop)...')
                    self.log(f'buffer: {self.prettifyPacket(self.buffer)}')
                    self.buffer.clear()
                    break
                count += 1
                idx_prefix = self.buffer.find(0xF7)
                if idx_prefix >= 0:
                    self.buffer = self.buffer[idx_prefix:]
                else:
                    break
                if len(self.buffer) >= 2:
                    packet_length = self.buffer[1]
                    # issue: abnormal - packet length 0
                    if packet_length == 0:
                        self.log(f'Warning: abnormal packet (length 0), buffer: {self.prettifyPacket(self.buffer)}')
                        self.buffer.clear()
                        break

                    if len(self.buffer) >= packet_length:
                        if self.buffer[packet_length - 1] == 0xEE:
                            self.line_busy = False
                            packet = self.buffer[:packet_length]
                            self.buffer = self.buffer[packet_length:]
                            try:
                                checksum_calc = self.calcXORChecksum(packet[:-2])
                                checksum_recv = packet[-2]
                                self.interpretPacket(packet)
                                if checksum_calc != checksum_recv:
                                    pacstr = self.prettifyPacket(packet)
                                    self.log(f'Warning: Checksum Error (calc={checksum_calc}, recv={checksum_recv}) ({pacstr})')
                                count -= 1
                            except IndexError:
                                buffstr = self.prettifyPacket(self.buffer)
                                pacstr = self.prettifyPacket(packet)
                                self.log(f'Index Error (buffer={buffstr}, packet_len={packet_length}, packet={pacstr})')
                            continue
                        else:
                            if len(self.buffer) > 0:
                                self.buffer = self.buffer[1:]
                                idx_prefix = self.buffer.find(0xF7)
                                if idx_prefix >= 0:
                                    self.buffer = self.buffer[idx_prefix:]
                                    continue
                                else:
                                    self.buffer.clear()
                                    break
                    else:
                        break
                else:
                    break
        elif self.type_interpret is ParserType.SUBPHONE:
            idx = self.buffer.find(0x7F)
            if idx > 0:
                self.buffer = self.buffer[idx:]
            if len(self.buffer) >= 2:
                idx2 = self.buffer.find(0xEE)
                if idx2 > 0:
                    self.line_busy = False
                    packet = self.buffer[:idx2 + 1]
                    self.interpretPacket(packet)
                    self.buffer = self.buffer[idx2 + 1:]
            elif len(self.buffer) == 1 and self.buffer[0] == 0xEE:
                self.line_busy = False
                self.buffer.clear()
        elif self.type_interpret is ParserType.UNKNOWN:
            self.buffer.clear()
            self.log(f'Invalid Parser Type ({self.type_interpret})')
    
    def interpretPacket(self, packet: bytearray):
        store: bool = True
        packet_info = {'packet': packet, 'timestamp': datetime.datetime.now()}
        # self.log(f'packet: {self.prettifyPacket(packet)}')
        try:
            if self.type_interpret == ParserType.REGULAR:
                if packet[3] == 0x15:  # 감성조명
                    self.handleEmotionLight(packet)
                    packet_info['device'] = 'emotion light'
                    store = self.enable_store_packet_header_15
                elif packet[3] == 0x18:  # 난방
                    self.handleThermostat(packet)
                    packet_info['device'] = 'thermostat'
                    store = self.enable_store_packet_header_18
                elif packet[3] == 0x19:  # 조명
                    self.handleLight(packet)
                    packet_info['device'] = 'light'
                    store = self.enable_store_packet_header_19
                elif packet[3] == 0x1A:  # 디밍조명
                    self.handleDimmingLight(packet)
                    packet_info['device'] = 'dimming light'
                    store = self.enable_store_packet_header_1A
                elif packet[3] == 0x1B:  # 가스차단기
                    self.handleGasValve(packet)
                    packet_info['device'] = 'gasvalve'
                    store = self.enable_store_packet_header_1B
                elif packet[3] == 0x1C:  # 시스템에어컨
                    self.handleAirconditioner(packet)
                    store = self.enable_store_packet_header_1C
                    packet_info['device'] = 'airconditioner'
                elif packet[3] == 0x1E:  # 현관 도어락 (?)
                    # self.log(f'Doorlock Packet: {self.prettifyPacket(packet)}')
                    self.handleDoorlock(packet)
                    store = self.enable_store_packet_header_1E
                    packet_info['device'] = 'doorlock'
                elif packet[3] == 0x1F:  # 아울렛 (콘센트)
                    self.handleOutlet(packet)
                    packet_info['device'] = 'outlet'
                    store = self.enable_store_packet_header_1F
                elif packet[3] == 0x2A:  # 일괄소등 스위치
                    self.handleBatchOffSwitch(packet)
                    packet_info['device'] = 'multi function switch'
                    store = self.enable_store_packet_header_2A
                elif packet[3] == 0x2B:  # 환기 (전열교환기)
                    self.handleVentilator(packet)
                    packet_info['device'] = 'ventilator'
                    store = self.enable_store_packet_header_2B
                elif packet[3] == 0x34:  # 엘리베이터
                    self.handleElevator(packet)
                    packet_info['device'] = 'elevator'
                    store = self.enable_store_packet_header_34
                elif packet[3] == 0x43:  # 에너지 모니터링
                    self.handleEnergyMonitoring(packet)
                    packet_info['device'] = 'hems'
                    store = self.enable_store_packet_header_43
                elif packet[3] == 0x44:  # maybe current date-time?
                    if packet[4] == 0x0C:  # broadcasting?
                        packet_info['device'] = 'timestamp'
                        if self.enable_trace_timestamp_packet:
                            year, month, day = packet[8], packet[9], packet[10]
                            hour, minute, second = packet[11], packet[12], packet[13]
                            millis = packet[14] * 100 + packet[15] * 10 + packet[16]
                            dt = datetime.datetime(year, month, day, hour, minute, second, millis * 1000)
                            self.log(f'Timestamp Packet: {self.prettifyPacket(packet)}')
                            self.log(f'>> {dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}')
                    else:
                        packet_info['device'] = 'unknown'
                        self.log(f'Unknown packet (44): {self.prettifyPacket(packet)}')
                    store = self.enable_store_packet_header_44
                elif packet[3] == 0x48:  # ??
                    """
                    # F7 0D 01 48 01 40 10 00 71 11 01 83 EE 도 발견됐다!
                    # F7 0D 01 48 01 40 10 00 71 11 02 80 EE
                    # F7 0D 01 48 04 40 10 00 71 11 02 85 EE
                    if packet == bytearray([0xF7, 0x0D, 0x01, 0x48, 0x01, 0x40, 0x10, 0x00, 0x71, 0x11, 0x02, 0x80, 0xEE]):
                        pass
                    elif packet == bytearray([0xF7, 0x0D, 0x01, 0x48, 0x04, 0x40, 0x10, 0x00, 0x71, 0x11, 0x02, 0x85, 0xEE]):
                        pass
                    else:
                        self.log(f'Unknown packet (48): {self.prettifyPacket(packet)}')
                    """
                    packet_info['device'] = 'unknown'
                    store = self.enable_store_packet_header_48
                elif packet[3] == 0x4B:  # ??
                    """
                    # F7 0B 01 4B 01 68 11 00 00 CE EE
                    # F7 0B 01 4B 04 68 11 00 00 CB EE
                    """
                    packet_info['device'] = 'unknown'
                    store = self.enable_store_packet_header_4B
                else:
                    self.log(f'Unknown packet: {self.prettifyPacket(packet)}')
                    packet_info['device'] = 'unknown'
                    store = self.enable_store_packet_unknown
            elif self.type_interpret == ParserType.SUBPHONE:
                if (packet[1] & 0xF0) == 0xB0:  # 현관 도어폰 호출
                    packet_info['device'] = 'front door'
                    self.handleFrontDoor(packet)
                elif (packet[1] & 0xF0) == 0x50:  # 공동 현관문 호출
                    packet_info['device'] = 'communal door'
                    self.handleCommunalDoor(packet)
                elif (packet[1] & 0xF0) == 0xE0:  # HEMS
                    packet_info['device'] = 'hems'
                    self.handleHEMS(packet)
                else:
                    packet_info['device'] = 'unknown'
                    self.log(f'{self.prettifyPacket(packet)} >> ???')
                store = self.enable_store_packet_general

            if store:
                if len(self.packet_storage) > self.max_packet_store_cnt:
                    self.packet_storage.pop(0)
                self.packet_storage.append(packet_info)
        except Exception as e:
            self.log(f'interpretPacket::Exception::{e} ({self.prettifyPacket(packet)})')
    
    def startRecv(self, count: int = 64):
        self.buffer.clear()
        self.chunk_cnt = 0
        self.enable_console_log = True
        while self.chunk_cnt < count:
            pass
        self.enable_console_log = False

    def setRS485LineBusy(self, value: bool):
        self.line_busy = value

    def isRS485LineBusy(self) -> bool:
        if self.rs485.getType() == RS485HwType.Socket:
            return False  # 무선 송신 레이턴시때문에 언제 라인이 IDLE인지 정확히 파악할 수 없다
        return self.line_busy

    def getRS485HwType(self) -> RS485HwType:
        return self.rs485.getType()

    def clearPacketStorage(self):
        self.packet_storage.clear()

    def setBufferSize(self, size: int, clear_buffer: bool = True):
        self.max_buffer_size = size
        if clear_buffer:
            self.buffer.clear()
        self.log(f'Recv Buffer Size: {self.max_buffer_size}')

    @staticmethod
    def prettifyPacket(packet: bytearray) -> str:
        return ' '.join(['%02X' % x for x in packet])
    
    @staticmethod
    def calcXORChecksum(data: Union[bytearray, bytes, List[int]]) -> int:
        return reduce(lambda x, y: x ^ y, data, 0)

    def updateDeviceState(self, data: dict):
        data['parser_index'] = self.index
        self.sig_parse_result.emit(data)

    def handleLight(self, packet: bytearray):
        room_idx = packet[6] >> 4
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # 상태 변경 명령
            pass
        elif packet[4] == 0x04:  # 각 방별 On/Off
            dev_idx = packet[6] & 0x0F
            if dev_idx == 0:  # 일반 쿼리 (존재하는 모든 디바이스)
                light_count = len(packet) - 10
                for idx in range(light_count):
                    state = 0 if packet[8 + idx] == 0x02 else 1
                    result = {
                        'device': DeviceType.LIGHT, 
                        'index': idx,
                        'room_index': room_idx,
                        'state': state
                    }
                    self.updateDeviceState(result)
            else:  # 상태 변경 명령 직후 응답
                state = 0 if packet[8] == 0x02 else 1
                result = {
                    'device': DeviceType.LIGHT, 
                    'index': dev_idx - 1,
                    'room_index': room_idx,
                    'state': state
                }
                self.updateDeviceState(result)

    def handleEmotionLight(self, packet: bytearray):
        room_idx = packet[6] >> 4
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # 상태 변경 명령
            pass
        elif packet[4] == 0x04:  # 각 방별 On/Off
            dev_idx = packet[6] & 0x0F
            if dev_idx == 0:  # 일반 쿼리 (존재하는 모든 디바이스)
                self.log(f'Warning: Un-implemented packet interpreter (zero device index, {self.prettifyPacket(packet)})')
            else:  # 상태 변경 명령 직후 응답
                state = 0 if packet[8] == 0x02 else 1
                # todo: packet[9], packet[10]이 뭔가 정보를 담고 있긴 한거 같은데...
                result = {
                    'device': DeviceType.EMOTIONLIGHT, 
                    'index': dev_idx - 1,
                    'room_index': room_idx,
                    'state': state
                }
                self.updateDeviceState(result)

    def handleDimmingLight(self, packet: bytearray):
        room_idx = packet[6] >> 4
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # 상태 변경 명령
            pass
        elif packet[4] == 0x04:  # 각 방별 On/Off
            state_type = packet[5]
            dev_idx = packet[6] & 0x0F
            if dev_idx == 0:  # 일반 쿼리 (존재하는 모든 디바이스)
                # todo: 아마 없는 형태의 패킷 아닐까?
                light_count = len(packet) - 10
                for idx in range(light_count):
                    if state_type == 0x40:
                        state = 0 if packet[8 + idx] == 0x02 else 1
                        result = {
                            'device': DeviceType.DIMMINGLIGHT, 
                            'index': idx,
                            'room_index': room_idx,
                            'state': state,
                            'brightness': None
                        }
                        self.updateDeviceState(result)
                    elif state_type == 0x42:
                        brightness = packet[8]
                        result = {
                            'device': DeviceType.DIMMINGLIGHT, 
                            'index': idx,
                            'room_index': room_idx,
                            'state': None,
                            'brightness': brightness
                        }
                        self.updateDeviceState(result)
            else:  # 상태 변경 명령 직후 응답
                if state_type == 0x40:
                    state = 0 if packet[8] == 0x02 else 1
                    result = {
                        'device': DeviceType.DIMMINGLIGHT, 
                        'index': dev_idx - 1,
                        'room_index': room_idx,
                        'state': state,
                        'brightness': None
                    }
                    self.updateDeviceState(result)
                elif state_type == 0x42:
                    brightness = packet[8]
                    result = {
                        'device': DeviceType.DIMMINGLIGHT, 
                        'index': dev_idx - 1,
                        'room_index': room_idx,
                        'state': None,
                        'brightness': brightness
                    }
                    self.updateDeviceState(result)

    def handleOutlet(self, packet: bytearray):
        room_idx = packet[6] >> 4
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # 상태 변경 명령
            pass
        elif packet[4] == 0x04:  # 각 방별 상태 (On/Off)
            dev_idx = packet[6] & 0x0F
            if dev_idx == 0:  # 일반 쿼리 (모든 디바이스)
                outlet_count = (len(packet) - 10) // 9
                for idx in range(outlet_count):
                    # XX YY -- -- -- -- -- -- ZZ
                    # XX: 상위 4비트 = 공간 인덱스, 하위 4비트는 디바이스 인덱스
                    # YY: 02 = OFF, 01 = ON
                    # ZZ: 02 = 대기전력 차단 수동, 01 = 대기전력 차단 자동
                    # 중간에 있는 패킷들은 전력량계 데이터같은데, 파싱 위한 레퍼런스가 없음
                    dev_packet = packet[8 + idx * 9: 8 + (idx + 1) * 9]
                    state = 0 if dev_packet[1] == 0x02 else 1
                    result = {
                        'device': DeviceType.OUTLET,
                        'index': idx,
                        'room_index': room_idx,
                        'state': state
                    }
                    self.updateDeviceState(result)
            else:  # 상태 변경 명령 직후 응답
                state = 0 if packet[8] == 0x02 else 1
                result = {
                    'device': DeviceType.OUTLET,
                    'index': dev_idx - 1,
                    'room_index': room_idx,
                    'state': state
                }
                self.updateDeviceState(result)

    def handleGasValve(self, packet: bytearray):
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # 상태 변경 명령
            pass
        elif packet[4] == 0x04:  # 상태 응답
            state = 0 if packet[8] == 0x03 else 1
            result = {
                'device': DeviceType.GASVALVE,
                'state': state
            }
            self.updateDeviceState(result)
    
    def handleThermostat(self, packet: bytearray):
        room_idx = packet[6] & 0x0F
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # On/Off, 온도 변경 명령
            pass
        elif packet[4] == 0x04:  # 상태 응답
            if room_idx == 0:  # 일반 쿼리 (존재하는 모든 디바이스)
                thermostat_count = (len(packet) - 10) // self.thermo_len_per_dev
                for idx in range(thermostat_count):
                    dev_packet = packet[8 + idx * self.thermo_len_per_dev: 8 + (idx + 1) * self.thermo_len_per_dev]
                    if dev_packet[0] != 0x00:  # 0이면 존재하지 않는 디바이스
                        state = 0 if dev_packet[0] == 0x04 else 1                            
                        temp_current = dev_packet[1]  # 현재 온도
                        temp_config = dev_packet[2]  # 설정 온도
                        result = {
                            'device': DeviceType.THERMOSTAT,
                            'room_index': idx + 1,
                            'state': state,
                            'temp_current': temp_current,
                            'temp_config': temp_config
                        }
                        self.updateDeviceState(result)
            else:  # 상태 변경 명령 직후 응답
                if packet[5] in [0x45, 0x46]:  # 0x46: On/Off 설정 변경에 대한 응답, 0x45: 온도 설정 변경에 대한 응답
                    state = 0 if packet[8] == 0x04 else 1
                    temp_current = packet[9]  # 현재 온도
                    temp_config = packet[10]  # 설정 온도
                    result = {
                        'device': DeviceType.THERMOSTAT,
                        'room_index': room_idx,
                        'state': state,
                        'temp_current': temp_current,
                        'temp_config': temp_config
                    }
                    self.updateDeviceState(result)
    
    def handleVentilator(self, packet: bytearray):
        if packet[4] == 0x01:
            pass
        elif packet[4] == 0x02:
            pass
        elif packet[4] == 0x04:
            state = 0 if packet[8] == 0x02 else 1
            rotation_speed = packet[9]  # 0x01=약, 0x03=중, 0x07=강
            result = {
                'device': DeviceType.VENTILATOR,
                'state': state
            }
            if rotation_speed != 0:
                result['rotation_speed'] = rotation_speed
            self.updateDeviceState(result)

    def handleAirconditioner(self, packet: bytearray):
        dev_idx = packet[6] & 0x0F
        room_idx = packet[6] >> 4
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # On/Off, 온도 변경 명령
            pass
        elif packet[4] == 0x04:  # 상태 응답
            if dev_idx == 0:
                if packet[5] == 0x5E:
                    # todo: https://github.com/YOGYUI/HomeNetwork/pull/12#issuecomment-2271148687
                    pass
                else:
                    pass
            else:
                state = 0 if packet[8] == 0x02 else 1  # On/Off 상태
                temp_current = packet[9]  # 현재 온도
                temp_config = packet[10]  # 설정 온도
                mode = packet[11]  # 모드 (0=자동, 1=냉방, 2=제습, 3=송풍)
                rotation_speed = packet[12]  # 풍량 (1=자동, 2=미풍, 3=약풍, 4=강풍)
                result = {
                    'device': DeviceType.AIRCONDITIONER,
                    'index': dev_idx - 1,
                    'room_index': room_idx,
                    'state': state,
                    'temp_current': temp_current,
                    'temp_config': temp_config,
                    'mode': mode,
                    'rotation_speed': rotation_speed
                }
                self.updateDeviceState(result)

    def handleElevator(self, packet: bytearray):
        if packet[4] == 0x01:  # 상태 쿼리 (월패드 -> 복도 미니패드)
            # F7 0D 01 34 01 41 10 00 XX YY ZZ ** EE
            # XX: 00=Idle, 01=Arrived, 하위4비트가 6이면 하행 호출중, 5이면 상행 호출 중, 
            #     상위4비트 A: 올라가는 중, B: 내려가는 중
            # YY: 현재 층수 (string encoded), ex) 지하3층 = B3, 5층 = 05
            # ZZ: 호기, ex) 01=1호기, 02=2호기, ...
            # **: Checksum (XOR SUM)
            state_h = (packet[8] & 0xF0) >> 4  # 상위 4비트, 0x0: stopped, 0xA: moving upside, 0x0B: moving downside
            state_l = packet[8] & 0x0F  # 하위 4비트, 0x0: idle, 0x1: arrived, 0x5: command (up), 0x6: command (down)
            floor = '{:02X}'.format(packet[9])
            ev_dev_idx = packet[10]  # 엘리베이터 n호기, 2대 이상의 정보가 교차로 들어오게 됨, idle일 경우 0

            command_state = 0
            moving_state = 0
            if state_h == 0x0:
                if state_l == 0x1:  # packet[8] = 0x01
                    moving_state = 1
                else:  # packet[8] = 0x00
                    pass
            elif state_h == 0xA:  # packet[8] = 0xA*
                command_state = state_l
                moving_state = 5
            elif state_h == 0xB:  # packet[8] = 0xB*
                command_state = state_l
                moving_state = 6
            result = {
                'device': DeviceType.ELEVATOR,
                'data_type': 'query',
                'command_state': command_state,
                'moving_state': moving_state,
                'ev_dev_idx': ev_dev_idx,
                'floor': floor,
                'packet': self.prettifyPacket(packet)
            }
            self.updateDeviceState(result)
        elif packet[4] == 0x02:
            pass
        elif packet[4] == 0x04:  # 상태 응답 (복도 미니패드 -> 월패드)
            # F7 0B 01 34 04 41 10 00 XX YY EE
            # XX: 하위 4비트: 6 = 하행 호출  ** 상행 호출에 해당하는 5 값은 발견되지 않는다
            # YY: Checksum (XOR SUM)
            # 미니패드의 '엘리베이터 호출' 버튼의 상태를 반환함
            call_state = packet[8] & 0x0F  # 0 = idle, 6 = command (하행) 호출
            result = {
                'device': DeviceType.ELEVATOR,
                'data_type': 'response',
                'call_state': call_state,
                'packet': self.prettifyPacket(packet)
            }
            self.updateDeviceState(result)

    def handleEnergyMonitoring(self, packet: bytearray):
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x04:
            # 값들이 hexa encoding되어있다!
            if packet[5] == 0x11:  # 전기 사용량
                value = int(''.join('%02X' % x for x in packet[7:12]))
                # self.log(f'EMON - Electricity: {value}')
            elif packet[5] == 0x13:  # 가스 사용량
                value = int(''.join('%02X' % x for x in packet[7:12]))
                # self.log(f'EMON - Gas: {value}')
            elif packet[5] == 0x14:  # 수도 사용량
                value = int(''.join('%02X' % x for x in packet[7:12]))
                # self.log(f'EMON - Water: {value}')
            elif packet[5] == 0x15:  # 온수 사용량
                value = int(''.join('%02X' % x for x in packet[7:12]))
                # self.log(f'EMON - Hot Water: {value}')
            elif packet[5] == 0x16:  # 난방 사용량
                value = int(''.join('%02X' % x for x in packet[7:12]))
                # self.log(f'EMON - Heating: {value}')
            else:
                self.log(f'> {self.prettifyPacket(packet)}')

    def handleBatchOffSwitch(self, packet: bytearray):
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x04:
            # 쿼리 응답
            # F7 0E 01 2A 04 40 10 00 19 XX 1B 03 YY EE
            # 명령 응답
            # F7 0C 01 2A 04 40 11 XX 19 YY ZZ EE
            # 길이는 다르지만 10번째 패킷이 스위치 상태를 가리킴
            state = 0 if packet[9] == 0x02 else 1
            result = {
                'device': DeviceType.BATCHOFFSWITCH,
                'state': state
            }
            self.updateDeviceState(result)
    
    def handleFrontDoor(self, packet: bytearray):
        result = {'device': DeviceType.SUBPHONE}
        notify: bool = True
        if packet[1] == 0xB5:
            # 현관 도어폰 초인종 호출 (월패드 -> 서브폰)
            result['ringing_front'] = 1
            self.log(f'{self.prettifyPacket(packet)} >> Front door ringing started')
        elif packet[1] == 0xB6:
            # 현관 도어폰 초인종 호출 종료 (월패드 -> 서브폰)
            result['ringing_front'] = 0
            self.log(f'{self.prettifyPacket(packet)} >> Front door ringing terminated')
        elif packet[1] == 0xB9:
            # 서브폰에서 현관 통화 시작 (서브폰 -> 월패드)
            result['streaming'] = 1
            self.log(f'{self.prettifyPacket(packet)} >> Streaming (front door) started from Subphone')
        elif packet[1] == 0xBA:
            # 서브폰에서 현관 통화 종료 (서브폰 -> 월패드)
            result['streaming'] = 0
            self.log(f'{self.prettifyPacket(packet)} >> Streaming (front door) terminated from Subphone')
        elif packet[1] == 0xB4:
            # 서브폰에서 현관문 열림 명령 (서브폰 -> 월패드)
            result['doorlock'] = 0  # Unsecured
            result['lock_front'] = 0  # Unsecured
            self.log(f'{self.prettifyPacket(packet)} >> Open front door from Subphone')
        elif packet[1] in [0xBB, 0xB8]:
            # 현관 도어폰 통화 종료
            result['ringing_front'] = 0
            result['streaming'] = 0
            result['doorlock'] = 1  # Secured
            result['lock_front'] = 1  # Secured
            self.log(f'{self.prettifyPacket(packet)} >> Streaming finished')
        else:
            notify = False
            self.log(f'{self.prettifyPacket(packet)} >> ???')
        if notify:
            self.updateDeviceState(result)

    def handleCommunalDoor(self, packet: bytearray):
        result = {'device': DeviceType.SUBPHONE}
        notify: bool = True
        if packet[1] == 0x5A:
            # 공동현관문 호출 (월패드 -> 서브폰)
            result['ringing_communal'] = 1
            self.log(f'{self.prettifyPacket(packet)} >> Communal door ringing started')
        elif packet[1] == 0x5C:
            # 공동현관문 호출 종료 (월패드 -> 서브폰)
            result['ringing_communal'] = 0
            self.log(f'{self.prettifyPacket(packet)} >> Communal door ringing terminated')
        elif packet[1] == 0x5E:
            # 공동현관문 통화 종료
            result['ringing_communal'] = 0
            result['streaming'] = 0
            result['doorlock'] = 1  # Secured
            result['lock_communal'] = 1  # Secured
            self.log(f'{self.prettifyPacket(packet)} >> Streaming finished')
        else:
            notify = False
            self.log(f'{self.prettifyPacket(packet)} >> ???')
        if notify:
            self.updateDeviceState(result)

    def handleHEMS(self, packet: bytearray):
        if packet[1] == 0xE0:
            # 쿼리 패킷 (서브폰 -> 월패드)
            pass
        elif packet[1] == 0xE1:
            result = {'device': DeviceType.HEMS, 'packet': packet}
            notify: bool = True
            # 응답 패킷 (월패드 -> 서브폰)
            devtype = HEMSDevType((packet[2] & 0xF0) >> 4)
            category = HEMSCategory(packet[2] & 0x0F)
            if category.value in [1, 2, 3, 4]:
                # 7F E1 XY 09 P1 P2 P3 Q1 Q2 Q3 R1 R2 R3 ZZ EE
                # X: 디바이스 타입
                # Y: 쿼리 타입
                # P1 P2 P3 : 당월 이력 값
                # Q1 Q2 Q3 : 전월 이력 값
                # R1 R2 R3 : 전전월 이력 값
                # ZZ : XOR Checksum
                v1 = int.from_bytes(packet[4:7], byteorder='big', signed=False)
                v2 = int.from_bytes(packet[7:10], byteorder='big', signed=False)
                v3 = int.from_bytes(packet[10:13], byteorder='big', signed=False)
                result[f'{devtype.name.lower()}_{category.name.lower()}_cur_month'] = v1
                result[f'{devtype.name.lower()}_{category.name.lower()}_1m_ago'] = v2
                result[f'{devtype.name.lower()}_{category.name.lower()}_2m_ago'] = v3
            elif category.value in [5, 7]:
                # 7F E1 XY 03 P1 P2 P3 ZZ EE
                # X: 디바이스 타입
                # Y: 쿼리 타입
                # P1~P3: 값
                # ZZ : XOR Checksum
                v = int.from_bytes(packet[4:7], byteorder='big', signed=False)
                result[f'{devtype.name.lower()}_{category.name.lower()}'] = v
            else:
                notify = False
                self.log(f'{self.prettifyPacket(packet)} >> ???')
            if notify:
                self.updateDeviceState(result)
        elif packet[1] == 0xE2:
            if self.enable_trace_timestamp_packet:
                year, month, day = int('%02X' % packet[2]), int('%02X' % packet[3]), int('%02X' % packet[4])
                hour, minute, second = int('%02X' % packet[5]), int('%02X' % packet[6]), int('%02X' % packet[7])
                dt = datetime.datetime(year, month, day, hour, minute, second)
                self.log(f'Timestamp Packet: {self.prettifyPacket(packet)}')
                self.log(f'>> {dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}')
        else:
            self.log(f'{self.prettifyPacket(packet)} >> ???')

    def handleDoorlock(self, packet: bytearray):
        unknown = True
        if packet[4] == 0x01:
            if packet[5] == 0x40:
                if len(packet) >= 13:
                    # packet[8:13] = month-day-hour-minute-second
                    unknown = False
        elif packet[4] == 0x02:
            pass
        if unknown:
            self.log(f'Doorlock Packet: {self.prettifyPacket(packet)}')
