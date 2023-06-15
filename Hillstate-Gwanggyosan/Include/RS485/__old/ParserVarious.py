from PacketParser import *
import datetime


class ParserVarious(PacketParser):
    enable_store_packet_header_18: bool = False
    enable_store_packet_header_1B: bool = False
    enable_store_packet_header_1C: bool = False
    enable_store_packet_header_2A: bool = False
    enable_store_packet_header_2B: bool = False
    enable_store_packet_header_34: bool = False
    enable_store_packet_header_43: bool = False
    enable_store_packet_header_44: bool = False
    enable_store_packet_header_48: bool = False
    enable_store_packet_unknown: bool = True

    enable_trace_timestamp_packet: bool = False

    def interpretPacket(self, packet: bytearray):
        try:
            store: bool = True
            packet_info = {'packet': packet, 'timestamp': datetime.datetime.now()}
            if packet[3] == 0x18:  # 난방
                self.handleThermostat(packet)
                packet_info['device'] = 'thermostat'
                store = self.enable_store_packet_header_18
            elif packet[3] == 0x1B:  # 가스차단기
                self.handleGasValve(packet)
                packet_info['device'] = 'gasvalve'
                store = self.enable_store_packet_header_1B
            elif packet[3] == 0x1C:  # 시스템에어컨
                self.handleAirconditioner(packet)
                store = self.enable_store_packet_header_1C
                packet_info['device'] = 'airconditioner'
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
                        writeLog(f'Timestamp Packet: {self.prettifyPacket(packet)}', self)
                        writeLog(f'>> {dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}', self)
                else:
                    packet_info['device'] = 'unknown'
                    writeLog(f'Unknown packet (44): {self.prettifyPacket(packet)}', self)
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
                    writeLog(f'Unknown packet (48): {self.prettifyPacket(packet)}', self)
                """
                packet_info['device'] = 'unknown'
                store = self.enable_store_packet_header_48
            else:
                writeLog(f'Unknown packet (??): {self.prettifyPacket(packet)}', self)
                packet_info['device'] = 'unknown'
                store = self.enable_store_packet_unknown
            if store:
                if len(self.packet_storage) > self.max_packet_store_cnt:
                    self.packet_storage.pop(0)
                self.packet_storage.append(packet_info)
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
                'device': DeviceType.GASVALVE,
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
                            'device': DeviceType.THERMOSTAT,
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
                        'device': DeviceType.THERMOSTAT,
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
                'device': DeviceType.VENTILATOR,
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
                'device': DeviceType.AIRCONDITIONER,
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
            #     상위4비트 A: 올라가는 중, B: 내려가는 중
            # YY: 현재 층수 (string encoded), ex) 지하3층 = B3, 5층 = 05
            # ZZ: 호기, ex) 01=1호기, 02=2호기, ...
            # **: Checksum (XOR SUM)
            state_h = (packet[8] & 0xF0) >> 4  # 상위 4비트, 0x0: stopped, 0xA: moving (up), 0x0B: moving (down)
            state_l = packet[8] & 0x0F  # 하위 4비트, 0x0: idle, 0x1: arrived, 0x5: command (up), 0x6: command (down)
            floor = '{:02X}'.format(packet[9])
            dev_idx = packet[10]  # 엘리베이터 n호기, 2대 이상의 정보가 교차로 들어오게 됨, idle일 경우 0

            state = 0  # idle (command done, command off)
            if state_h == 0x0:
                direction = 0
                if state_l == 0x1:
                    state = 1  # arrived
            else:
                direction = 0
                if state_h == 0xA:  # Up
                    direction = 5
                elif state_h == 0xB:  # Down
                    direction = 6
                if state_l == 0x5:  # Up
                    state = 5
                elif state_l == 0x6:  # Down
                    state = 6
                
            result = {
                'device': DeviceType.ELEVATOR,
                'data_type': 'query',
                'state': state,
                'dev_idx': dev_idx,
                'direction': direction,
                'floor': floor
            }
            # print(f'Query: {self.prettifyPacket(packet)}, {result}')
            self.sig_parse_result.emit(result)
        elif packet[4] == 0x02:
            pass
        elif packet[4] == 0x04:  # 상태 응답 (복도 미니패드 -> 월패드)
            # F7 0B 01 34 04 41 10 00 XX YY EE
            # XX: 하위 4비트: 6 = 하행 호출  ** 상행 호출에 해당하는 5 값은 발견되지 않는다
            # YY: Checksum (XOR SUM)
            # 미니패드의 '엘리베이터 호출' 버튼의 상태를 반환함
            state = packet[8] & 0x0F  # 0 = idle, 6 = command (하행) 호출
            result = {
                'device': DeviceType.ELEVATOR,
                'data_type': 'response',
                'state': state
            }
            # print(f'Response: {self.prettifyPacket(packet)}, {result}')
            self.sig_parse_result.emit(result)

    def handleEnergyMonitoring(self, packet: bytearray):
        if packet[4] == 0x01:  # 상태 쿼리
            pass
        elif packet[4] == 0x04:
            # 값들이 hexa encoding되어있다!
            if packet[5] == 0x11:  # 전기 사용량
                value = int(''.join('%02X' % x for x in packet[7:12]))
                # writeLog(f'EMON - Electricity: {value}', self)
            elif packet[5] == 0x13:  # 가스 사용량
                value = int(''.join('%02X' % x for x in packet[7:12]))
                # writeLog(f'EMON - Gas: {value}', self)
            elif packet[5] == 0x14:  # 수도 사용량
                value = int(''.join('%02X' % x for x in packet[7:12]))
                # writeLog(f'EMON - Water: {value}', self)
            elif packet[5] == 0x15:  # 온수 사용량
                value = int(''.join('%02X' % x for x in packet[7:12]))
                # writeLog(f'EMON - Hot Water: {value}', self)
            elif packet[5] == 0x16:  # 난방 사용량
                value = int(''.join('%02X' % x for x in packet[7:12]))
                # writeLog(f'EMON - Heating: {value}', self)
            else:
                writeLog(f'> {self.prettifyPacket(packet)}', self)

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
            self.sig_parse_result.emit(result)
