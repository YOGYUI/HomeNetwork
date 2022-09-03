from PacketParser import *


class ParserDoorphone(PacketParser):
    def interpretPacket(self, packet: bytearray):
        try:
            pass
        except Exception as e:
            writeLog('interpretPacket::Exception::{} ({})'.format(e, packet), self)
