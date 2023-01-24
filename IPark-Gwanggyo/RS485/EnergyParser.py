from PacketParser import *


class EnergyParser(PacketParser):
    enable_log_header_31: bool = True
    enable_log_header_41: bool = True
    enable_log_header_42: bool = True
    enable_log_header_d1: bool = True
    enable_log_room_1: bool = True
    enable_log_room_2: bool = True
    enable_log_room_3: bool = True
    _max_light_count: int = 4
    _max_outlet_count: int = 3

    def handlePacket(self):
        try:
            idx = self.buffer.find(0x2)
            if idx > 0:
                self.buffer = self.buffer[idx:]
            
            if len(self.buffer) >= 3:
                packetLen = self.buffer[2]
                if len(self.buffer) >= max(packetLen, 5):
                    header = self.buffer[1]
                    self.timestamp = self.buffer[4]
                    if header == 0xD1 and packetLen == 0x30:  # 
                        idx_lst = []
                        next_ts = (self.timestamp + 1) & 0xFF
                        # 02 D1 30 XX 시작 패킷은 전체 패킷이 다 수신되지 않는다...
                        for i in range(len(self.buffer)):
                            if self.buffer[i] == next_ts:
                                idx_lst.append(i)
                        for idx in idx_lst:
                            if idx >= 4 and len(self.buffer) > idx + 4 and self.buffer[idx - 4] == 0x2:
                                chunk = self.buffer[:idx - 4]
                                self.chunk_cnt += 1
                                if self.enable_console_log:
                                    msg = ' '.join(['%02X' % x for x in chunk])
                                    # print(msg + ' ({}, {}, {})'.format(len(chunk), packetLen, len(self.buffer)))
                                    print(msg)
                                    if chunk[1] == 0xD1:
                                        pass
                                    else:
                                        print(msg)
                                self.interpretPacket(chunk)
                                self.buffer = self.buffer[idx - 4:]
                                packetLen = self.buffer[2] if len(self.buffer) >= 3 else 0
                                break
                    chunk = self.buffer[:packetLen]
                    if self.chunk_cnt >= self.max_chunk_cnt:
                        self.chunk_cnt = 0
                    self.chunk_cnt += 1
                    if self.enable_console_log:
                        msg = ' '.join(['%02X' % x for x in chunk])
                        # print(msg + ' ({}, {}, {})'.format(len(chunk), packetLen, len(self.buffer)))
                        print(msg)
                        if chunk[1] == 0x31:
                            # 조명
                            pass
                        elif chunk[1] == 0x41:
                            # print(msg)
                            pass
                        elif chunk[1] == 0x42:
                            # print(msg)
                            pass
                        elif chunk[1] == 0xD1:
                            pass
                        else:
                            print(msg)
                            pass
                        """
                        if chunk[1:4] == bytearray([0x31, 0x07, 0x11]):
                            # 각 방의 에너지 정보 쿼리 패킷
                            pass
                        elif chunk[1:4] == bytearray([0x31, 0x1E, 0x91]):
                            # 각 방의 에너지 정보 응답 패킷
                            pass
                        elif chunk[1:4] == bytearray([0x41, 0x07, 0x11]):
                            # print(msg)
                            pass
                        elif chunk[1:4] == bytearray([0x41, 0x08, 0x91]):
                            # print(msg)
                            pass
                        elif chunk[1:4] == bytearray([0x42, 0x07, 0x11]):
                            # print(msg)
                            pass
                        elif chunk[1:4] == bytearray([0x42, 0x08, 0x91]):
                            # print(msg)
                            pass
                        elif chunk[1:4] == bytearray([0xD1, 0x07, 0x02]):
                            pass
                        else:
                            print(msg)
                        """
                    self.interpretPacket(chunk)
                    self.buffer = self.buffer[packetLen:]
        except Exception as e:
            writeLog('handlePacket Exception::{}'.format(e), self)

    def interpretPacket(self, packet: bytearray):
        try:
            if len(packet) < 8:
                return
            header = packet[1]
            command = packet[3]
            room_idx = 0
            if header == 0x31:
                if command == 0x81:
                    pass
                elif command == 0x91:
                    room_idx = packet[5] & 0x0F
                    self.handleStatePacket(packet)
                elif command in [0x01, 0x11]:
                    room_idx = packet[5] & 0x0F
            elif header == 0x41:  # 정체파악 못한 패킷
                pass
            elif header == 0x42:  # 정체파악 못한 패킷
                pass
            elif header == 0xD1:  # HEMS 패킷?
                if command == 0x02:  # HEMS 쿼리 
                    pass
                elif command == 0x82:
                    self.handleHEMSPacket(packet)
            else:
                pass

            # packet log
            enable = True
            if header == 0x31:
                if not self.enable_log_header_31:
                    enable = False
                else:
                    if room_idx == 1 and not self.enable_log_room_1:
                        enable = False
                    if room_idx == 2 and not self.enable_log_room_2:
                        enable = False
                    if room_idx == 3 and not self.enable_log_room_3:
                        enable = False
            if header == 0x41 and not self.enable_log_header_41:
                enable = False
            if header == 0x42 and not self.enable_log_header_42:
                enable = False
            if header == 0xD1 and not self.enable_log_header_d1:
                enable = False
            if enable:
                self.sig_raw_packet.emit(packet)
        except Exception as e:
            writeLog('interpretPacket Exception::{}'.format(e), self)

    def handleStatePacket(self, packet: bytearray):
        room_idx = packet[5] & 0x0F
        # 방 조명 패킷
        for idx in range(self._max_light_count):
            state = (packet[6] & (0x01 << idx)) >> idx
            result = {
                'device': 'light',
                'room_index': room_idx,
                'index': idx,
                'state': state
            }
            self.sig_parse_result.emit(result)
        # 콘센트 소비전력 패킷
        for idx in range(self._max_outlet_count):
            state = (packet[7] & (0x01 << idx)) >> idx
            # TODO: 월패드에서 제어가 되지 않는 (항상 켜져있는) 아울렛 state 지정
            idx1 = 14 + 2 * idx
            idx2 = idx1 + 2
            if len(packet) > idx2:
                value = int.from_bytes(packet[idx1:idx2], byteorder='big')
                consumption = value / 10.
            else:
                consumption = 0.
            result = {
                'device': 'outlet',
                'room_index': room_idx,
                'index': idx,
                'state': state,
                'consumption': consumption
            }
            self.sig_parse_result.emit(result)

    def handleHEMSPacket(self, packet: bytearray):
        # TODO: 전체 평균/세대 평균?
        try:
            # 전기 [13:14]
            if len(packet) >= 15:
                v1 = int('{:02X}'.format(packet[13]))
                v2 = int('{:02X}'.format(packet[14]))
                self.sig_parse_result.emit({
                    'device': 'hems',
                    'category': 'electricity',
                    'value': v1 * 100 + v2
                })
            # 난방 [21:22]
            if len(packet) >= 23:
                v1 = int('{:02X}'.format(packet[21]))
                v2 = int('{:02X}'.format(packet[22]))
                self.sig_parse_result.emit({
                    'device': 'hems',
                    'category': 'heating',
                    'value': v1 * 100 + v2
                })
            # 온수 [29:30]
            if len(packet) >= 31:
                v1 = int('{:02X}'.format(packet[29]))
                v2 = int('{:02X}'.format(packet[30]))
                self.sig_parse_result.emit({
                    'device': 'hems',
                    'category': 'hotwater',
                    'value': v1 * 100 + v2
                })
            # 가스 [37:38]
            if len(packet) >= 39:
                v1 = int('{:02X}'.format(packet[37]))
                v2 = int('{:02X}'.format(packet[38]))
                self.sig_parse_result.emit({
                    'device': 'hems',
                    'category': 'gas',
                    'value': v1 * 100 + v2
                })
            # 수도 [44:45]
            if len(packet) >= 46:
                v1 = int('{:02X}'.format(packet[44]))
                v2 = int('{:02X}'.format(packet[45]))
                self.sig_parse_result.emit({
                    'device': 'hems',
                    'category': 'water',
                    'value': v1 * 100 + v2
                })
        except Exception as e:
            writeLog('handleHEMSPacket Exception::{}'.format(e), self)
