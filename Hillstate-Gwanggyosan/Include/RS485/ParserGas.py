from SerialParser import *


class ParserGas(SerialParser):    
    def interpretPacket(self, packet: bytearray):
        try:
            if packet[2:4] == bytearray([0x01, 0x1B]):  # 가스차단기
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
        except Exception as e:
            writeLog('interpretPacket::Exception::{} ({})'.format(e, packet), self)
