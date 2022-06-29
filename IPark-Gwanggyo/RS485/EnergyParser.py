from PacketParser import PacketParser


class EnergyParser(PacketParser):
    def handlePacket(self):
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
                            self.sig_parse.emit(chunk)
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
                self.sig_parse.emit(chunk)
                self.buffer = self.buffer[packetLen:]
