from PacketParser import *


class EnergyParser(PacketParser):
    enable_log_header_31: bool = True
    enable_log_header_41: bool = True
    enable_log_header_42: bool = True
    enable_log_header_d1: bool = True
    enable_log_room_1: bool = True
    enable_log_room_2: bool = True
    enable_log_room_3: bool = True

    def handlePacket(self):
        try:
            idx = self.buffer.find(0x2)
            if idx > 0:
                self.buffer = self.buffer[idx:]
            
            if len(self.buffer) >= 3:
                packetLen = self.buffer[2]
                if len(self.buffer) >= max(packetLen, 5):
                    header = self.buffer[1]
                    timestamp = self.buffer[4]
                    if header == 0xD1 and packetLen == 0x30:  # 
                        idx_lst = []
                        next_ts = (timestamp + 1) & 0xFF
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
            header = packet[1]  # [0x31, 0x41, 0x42, 0xD1]
            command = packet[3]
            room_idx = 0
            if header == 0x31:
                if command in [0x81, 0x91]:
                    room_idx = packet[5] & 0x0F
                    for idx in range(4):
                        # 방 조명 패킷
                        state = (packet[6] & (0x01 << idx)) >> idx
                        result = {
                            'device': 'light',
                            'room_index': room_idx,
                            'index': idx,
                            'state': state
                        }
                        self.sig_parse_result.emit(result)
                        # 콘센트 소비전력 패킷
                        state = (packet[7] & (0x01 << idx)) >> idx
                        if len(packet) >= 14 + 2 * idx + 2 + 1:
                            value = int.from_bytes(packet[14 + 2 * idx: 14 + 2 * idx + 2], byteorder='big')
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
                elif command in [0x11]:
                    room_idx = packet[5] & 0x0F

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