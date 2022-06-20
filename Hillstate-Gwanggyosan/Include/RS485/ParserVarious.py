from SerialParser import *


class ParserVarious(SerialParser):    
    def interpretPacket(self, packet: bytearray):
        try:
            if packet[3] == 0x1B:  # 가스차단기
                self.handleGasValve(packet)
            elif packet[3] == 0x18:  # 난방
                self.handleThermostat(packet)
            elif packet[3] == 0x2B:  # 환기 (전열교환기)
                self.handleVentilator(packet)
            elif packet[3] == 0x1C:  # 시스템에어컨
                self.handleAirconditioner(packet)
            else:
                if packet[4] == 0x02:
                    print(self.prettifyPacket(packet))
        except Exception as e:
            writeLog('interpretPacket::Exception::{} ({})'.format(e, packet), self)

    def handleGasValve(self, packet: bytearray):
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # 상태 변경 명령
            pass
        elif packet[4] == 0x04:  # 상태 응답
            state = 0 if packet[8] == 0x03 else 1
            result = {
                'device': 'gasvalve',
                'state': state
            }
            self.sig_parse_result.emit(result)
    
    def handleThermostat(self, packet: bytearray):
        room_idx = packet[6] & 0x0F
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # On/Off, 온도 변경 명령
            pass
        elif packet[4] == 0x04:  # 상태 응답
            if room_idx == 0:  # 일반 쿼리 (존재하는 모든 디바이스)
                thermostat_count = (len(packet) - 10) // 3
                for idx in range(thermostat_count):
                    dev_packet = packet[8 + idx * 3: 8 + (idx + 1) * 3]
                    if dev_packet[0] != 0x00:  # 0이면 존재하지 않는 디바이스
                        state = 0 if dev_packet[0] == 0x04 else 1                            
                        temp_current = dev_packet[1]  # 현재 온도
                        temp_config = dev_packet[2]  # 설정 온도
                        result = {
                            'device': 'thermostat',
                            'room_index': idx + 1,
                            'state': state,
                            'temp_current': temp_current,
                            'temp_config': temp_config
                        }
                        self.sig_parse_result.emit(result)
            else:  # 상태 변경 명령 직후 응답
                if packet[5] in [0x45, 0x46]:  # 0x46: On/Off 설정 변경에 대한 응답, 0x45: 온도 설정 변경에 대한 응답
                    state = 0 if packet[8] == 0x04 else 1
                    temp_current = packet[9]  # 현재 온도
                    temp_config = packet[10]  # 설정 온도
                    result = {
                        'device': 'thermostat',
                        'room_index': room_idx,
                        'state': state,
                        'temp_current': temp_current,
                        'temp_config': temp_config
                    }
                    self.sig_parse_result.emit(result)
    
    def handleVentilator(self, packet: bytearray):
        if packet[4] == 0x01:
            pass
        elif packet[4] == 0x02:
            pass
        elif packet[4] == 0x04:
            state = 0 if packet[8] == 0x02 else 1
            rotation_speed = packet[9]  # 0x01=약, 0x03=중, 0x07=강
            result = {
                'device': 'ventilator',
                'state': state
            }
            if rotation_speed != 0:
                result['rotation_speed'] = rotation_speed
            self.sig_parse_result.emit(result)

    def handleAirconditioner(self, packet: bytearray):
        room_idx = packet[6] >> 4
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x02:  # On/Off, 온도 변경 명령
            pass
        elif packet[4] == 0x04:  # 상태 응답
            state = 0 if packet[8] == 0x02 else 1
            temp_current = packet[9]  # 현재 온도
            temp_config = packet[10]  # 설정 온도
            mode = packet[11]  # 모드 (0=자동, 1=냉방, 2=제습, 3=공기청정)
            rotation_speed = packet[12]  # 풍량 (1=자동, 2=미풍, 3=약풍, 4=강풍)
            result = {
                'device': 'airconditioner',
                'room_index': room_idx,
                'state': state,
                'temp_current': temp_current,
                'temp_config': temp_config,
                'mode': mode,
                'rotation_speed': rotation_speed
            }
            self.sig_parse_result.emit(result)
