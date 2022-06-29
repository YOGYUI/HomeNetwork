from PacketParser import PacketParser


class ControlParser(PacketParser):
    def handlePacket(self):
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
                self.sig_parse.emit(chunk)
                self.buffer = self.buffer[packetLen:]
