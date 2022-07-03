from PacketParser import PacketParser


class DoorphoneParser(PacketParser):
    def handlePacket(self):
        if len(self.buffer) > 16:
            chunk = self.buffer[:16]
            if self.chunk_cnt >= self.max_chunk_cnt:
                self.chunk_cnt = 0
            self.chunk_cnt += 1
            if self.enable_console_log:
                msg = ' '.join(['%02X' % x for x in chunk])
                print(msg)

            self.buffer = self.buffer[16:]
        """
        idx = self.buffer.find(0x2)
        if idx > 0:
            self.buffer = self.buffer[idx:]
        
        if len(self.buffer) >= 3:
            packetLen = self.buffer[2]

            if len(self.buffer) >= packetLen:
                chunk = self.buffer[:packetLen]
                if self.chunk_cnt >= self.max_chunk_cnt:
                    self.chunk_cnt = 0
                self.chunk_cnt += 1
                if self.enable_console_log:
                    msg = ' '.join(['%02X' % x for x in chunk])
                    print(msg)
                self.sig_parse.emit(chunk)
                self.buffer = self.buffer[packetLen:]
        """
