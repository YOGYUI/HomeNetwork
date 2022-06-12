from SerialParser import SerialParser


class ParserLight(SerialParser):
    def handlePacket(self):
        idx = self.buffer.find(0xF7)
        if idx > 0:
            self.buffer = self.buffer[idx:]
        if len(self.buffer) >= 3:
            packet_length = self.buffer[1]
            if len(self.buffer) >= packet_length:
                if self.buffer[packet_length - 1] == 0xEE:
                    packet = self.buffer[:packet_length]
                    self.sig_parse.emit(packet)
                    self.buffer = self.buffer[packet_length:]