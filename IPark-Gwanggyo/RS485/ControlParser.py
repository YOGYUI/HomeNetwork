from PacketParser import *


class ControlParser(PacketParser):
    enable_log_header_28: bool = True
    enable_log_header_31: bool = True
    enable_log_header_61: bool = True

    def handlePacket(self):
        try:
            idx = self.buffer.find(0x2)
            if idx > 0:
                self.buffer = self.buffer[idx:]

            if len(self.buffer) >= 3:
                packetLen = self.buffer[2] if self.buffer[1] not in [0x31, 0x61] else 10
            
                if len(self.buffer) >= packetLen:
                    chunk = self.buffer[:packetLen]
                    if self.chunk_cnt >= self.max_chunk_cnt:
                        self.chunk_cnt = 0
                    self.chunk_cnt += 1
                    if self.enable_console_log:
                        msg = ' '.join(['%02X' % x for x in chunk])
                        # print(msg)
                        try:
                            if chunk[1] == 0x28:
                                # 난방
                                if chunk[3] in [0x21, 0xA1]:
                                    pass
                                elif chunk[3] in [0x11, 0x91]:
                                    pass
                                elif chunk[3] == 0x12:
                                    pass
                            elif chunk[1] == 0x31:
                                # 가스
                                # print(msg)
                                """
                                self.chunk_cnt += 1
                                if chunk[2] == 0x80:
                                    # print(msg)
                                    # self.chunk_cnt += 1
                                    pass
                                """
                                pass
                            elif chunk[1] == 0x61:
                                # 환기
                                # print(msg)
                                # self.chunk_cnt += 1
                                pass
                            else:
                                print(msg)
                                pass
                        except Exception:
                            pass
                    self.interpretPacket(chunk)
                    self.buffer = self.buffer[packetLen:]
        except Exception as e:
            writeLog('handlePacket Exception::{}'.format(e), self)

    def interpretPacket(self, packet: bytearray):
        try:
            if len(packet) < 10:
                return
            header = packet[1]  # [0x28, 0x31, 0x61]
            command = packet[3]
            if header == 0x28 and command in [0x91, 0x92]:
                # 난방 관련 패킷
                self.handleThermostat(packet)
            elif header == 0x31 and packet[2] in [0x80, 0x82]:
                # 가스밸브 관련 패킷 (길이 정보 없음, 무조건 10 고정)
                self.handleGasValve(packet)
            elif header == 0x61 and packet[2] in [0x80, 0x81, 0x83, 0x84, 0x87]:
                # 환기 관련 패킷
                self.handleVentilator(packet)
            else:
                pass
        
            # packet log
            enable = True
            if header == 0x28 and not self.enable_log_header_28:
                enable = False
            if header == 0x31 and not self.enable_log_header_31:
                enable = False
            if header == 0x61 and not self.enable_log_header_61:
                enable = False
            if enable:
                self.sig_raw_packet.emit(packet)
        except Exception as e:
            writeLog('interpretPacket Exception::{}'.format(e), self)

    def handleThermostat(self, packet: bytearray):
        # packet[3] == 0x91: 쿼리 응답 / 0x92: 명령 응답
        room_idx = packet[5] & 0x0F
        state = packet[6] & 0x01
        temperature_setting = (packet[7] & 0x3F) + (packet[7] & 0x40 > 0) * 0.5
        temperature_current = int.from_bytes(packet[8:10], byteorder='big') / 10.0
        result = {
            'device': 'thermostat',
            'room_index': room_idx,
            'state': state,
            'temperature_setting': temperature_setting,
            'temperature_current': temperature_current
        }
        self.sig_parse_result.emit(result)
    
    def handleGasValve(self, packet: bytearray):
        # packet[2] == 0x80: 쿼리 응답
        # packet[2] == 0x82: 명령 응답
        state = packet[5]
        result = {
            'device': 'gasvalve',
            'state': state
        }
        self.sig_parse_result.emit(result)
    
    def handleVentilator(self, packet: bytearray):
        state = packet[5] & 0x01
        state_natural = (packet[5] & 0x10) >> 4
        rotation_speed = packet[6]
        timer_remain = packet[7]
        result = {
            'device': 'ventilator',
            'state': state,
            'state_natural': state_natural,
            'rotation_speed': rotation_speed,
            'timer_remain': timer_remain
        }
        self.sig_parse_result.emit(result)
