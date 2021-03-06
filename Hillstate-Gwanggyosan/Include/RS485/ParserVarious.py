from PacketParser import *


class ParserVarious(PacketParser):    
    def interpretPacket(self, packet: bytearray):
        try:
            if packet[3] == 0x18:  # 난방
                self.handleThermostat(packet)
            elif packet[3] == 0x1B:  # 가스차단기
                self.handleGasValve(packet)
            elif packet[3] == 0x1C:  # 시스템에어컨
                self.handleAirconditioner(packet)
            elif packet[3] == 0x2A:  # 다기능스위치
                pass
            elif packet[3] == 0x2B:  # 환기 (전열교환기)
                self.handleVentilator(packet)
            elif packet[3] == 0x34:  # 엘리베이터
                self.handleElevator(packet)
            elif packet[3] == 0x43:  # ??
                # writeLog(f'Unknown packet (43): {self.prettifyPacket(packet)}', self)
                if packet == bytearray([0xF7, 0x0B, 0x01, 0x43, 0x01, 0x11, 0x11, 0x00, 0x00, 0xBF, 0xEE]):
                    pass
                elif packet[4] == 0x04:
                    # writeLog(f'{self.prettifyPacket(packet[7:12])} ({int.from_bytes(packet[7:12], byteorder="big")}, {packet[10]}, {packet[11]})')
                    pass
                else:
                    writeLog(f'Unknown packet (43): {self.prettifyPacket(packet)}', self)
            elif packet[3] == 0x48:  # ??
                if packet == bytearray([0xF7, 0x0D, 0x01, 0x48, 0x01, 0x40, 0x10, 0x00, 0x71, 0x11, 0x02, 0x80, 0xEE]):
                    pass
                elif packet == bytearray([0xF7, 0x0D, 0x01, 0x48, 0x04, 0x40, 0x10, 0x00, 0x71, 0x11, 0x02, 0x85, 0xEE]):
                    pass
                else:
                    writeLog(f'Unknown packet (48): {self.prettifyPacket(packet)}', self)
            else:
                writeLog(f'Unknown packet (??): {self.prettifyPacket(packet)}', self)
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

    def handleElevator(self, packet: bytearray):
        if packet[4] == 0x01:  # 상태 쿼리 (월패드 -> 복도 미니패드)
            # F7 0D 01 34 01 41 10 00 XX YY ZZ ** EE
            # XX: 00=Idle, 01=Arrived, 하위4비트가 6이면 하행 호출중, 5이면 상행 호출 중, 
            #     상위4비트는 엘리베이터 구분인가? (불확실함)
            # YY: 엘리베이터 층수
            # ZZ: 엘리베이터가 움직이는지 여부인가? (불확실함)
            # **: Checksum (XOR SUM)
            state = packet[8] & 0x0F  # 0 = idle, 1 = arrived, 5 = moving(up), 6 = moving(down)
            elevator_index = (packet[8] & 0xF0) >> 4  # 0x0A or 0x0B
            floor = ['??', '??']
            if elevator_index == 0x0A:
                floor[0] = '{:02X}'.format(packet[9])
            elif elevator_index == 0x0B:
                floor[1] = '{:02X}'.format(packet[9])
            result = {
                'device': 'elevator',
                'state': state,
                'floor': floor
            }
            self.sig_parse_result.emit(result)
        elif packet[4] == 0x02:
            pass
        elif packet[4] == 0x04:  # 상태 응답 (복도 미니패드 -> 월패드)
            state = packet[8] & 0x0F  # 0 = idle, 1 = arrived, 5 = moving(up), 6 = moving(down)
            result = {
                'device': 'elevator',
                'state': state
            }
            self.sig_parse_result.emit(result)
