from PacketParser import *


class ParserSubPhone(PacketParser):
    enable_store_packets: bool = False

    def handlePacket(self):
        # 3840 baudrate
        # packet format: 7F XX XX XX EE
        idx = self.buffer.find(0x7F)
        if idx > 0:
            self.buffer = self.buffer[idx:]
        if len(self.buffer) >= 2:
            idx2 = self.buffer.find(0xEE)
            if idx2 > 0:
                self.line_busy = False
                packet = self.buffer[:idx2 + 1]
                self.interpretPacket(packet)
                self.buffer = self.buffer[idx2 + 1:]

    def interpretPacket(self, packet: bytearray):
        try:
            store: bool = self.enable_store_packets
            packet_info = {'packet': packet, 'timestamp': datetime.datetime.now()}
            print(self.prettifyPacket(packet))
            result = {'device': 'subphone'}
            if packet[1] == 0xB5:
                # 현관 도어폰 초인종 호출 (월패드 -> 비디오폰)
                result['doorbell'] = 1
                print('>> Door Bell started')
            elif packet[1] == 0xB6:
                # 현관 도어폰 초인종 호출 종료 (월패드 -> 비디오폰)
                result['doorbell'] = 0
                print('>> Door Bell finished')
            elif packet[1] == 0xBB:
                # 현관 도어폰 통화 종료?
                result['doorcam'] = 0
                result['doorbell'] = 0
                print('>> Door Call finished')
            elif packet[1] == 0x5A:
                # 공동현관문 호출 (월패드 -> 비디오폰)
                result['outer_door_call'] = 1
                print('>> Outer Door Call started')
            elif packet[1] == 0x5C:
                # 공동현관문 호출 종료 (월패드 -> 비디오폰)
                result['outer_door_call'] = 0
                print('>> Outer Door Call finished')
            else:
                print('>> ???')
            self.sig_parse_result.emit(result)

            if store:
                if len(self.packet_storage) > self.max_packet_store_cnt:
                    self.packet_storage.pop(0)
                self.packet_storage.append(packet_info)
        except Exception as e:
            writeLog('interpretPacket::Exception::{} ({})'.format(e, packet), self)
