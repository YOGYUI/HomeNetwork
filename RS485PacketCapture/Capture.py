from SerialComm import *


class ParserLight:
    buffer: bytearray
    max_buffer_size: int = 200

    def __init__(self, ser: SerialComm):
        self.buffer = bytearray()
        self.serial = ser
        self.serial.sig_recv_data.connect(self.onRecvData)
    
    def onRecvData(self, data: bytes):
        if len(self.buffer) > self.max_buffer_size:
            self.buffer.clear()
        self.buffer.extend(data)
        self.parseBuffer()
    
    def parseBuffer(self):
        idx = self.buffer.find(0xF7)
        if idx > 0:
            self.buffer = self.buffer[idx:]
        if len(self.buffer) >= 3:
            packet_length = self.buffer[1]
            if len(self.buffer) >= packet_length:
                if self.buffer[packet_length - 1] == 0xEE:
                    packet = self.buffer[:packet_length]
                    packet_str = ' '.join(['%02X' % x for x in packet])
                    if packet[2] == 0x01:
                        if packet[3] == 0x19:  # 조명 상태
                            header = packet[4]
                            room_idx = packet[6] >> 4
                            
                            if header == 0x01:  # 쿼리/명령
                                if room_idx == 1:  # 거실
                                    # print(packet_str)
                                    pass
                                elif room_idx == 2:  # 침실(방1)
                                    # print(packet_str)
                                    pass
                                elif room_idx == 3:  # 서재(방2)
                                    # print(packet_str)
                                    pass
                                elif room_idx == 4:  # 컴퓨터방 (방3)
                                    # print(packet_str)
                                    pass
                                elif room_idx == 6:  # 주방
                                    print(packet_str)
                                    pass
                            elif header == 0x04:  # 응답
                                light_count = packet_length - 10
                                # print(f'room {room_idx} light count: {light_count}')
                            else:
                                print(packet_str)
                        elif packet[3] == 0x1F:
                            # print(f'????: {packet_str}')
                            pass
                        else:
                            print(packet_str)
                    else:
                        print(packet_str)
                    self.buffer = self.buffer[packet_length:]



if __name__ == '__main__':
    ser = SerialComm()
    parser = ParserLight(ser)

    def printMenu():
        if ser.isConnected():
            print('Connected ({}, {})'.format(ser.port, ser.baudrate))
            print('0: Disconnect, 1: Test-1, 2: Test-2, 3: Terminate')
        else:
            print('0: Connect, 1: Terminate')

    def loop():
        os.system('clear')
        printMenu()
        sysin = sys.stdin.readline()
        try:
            head = int(sysin.split('\n')[0])
        except Exception:
            loop()
            return
        
        if ser.isConnected():
            if head == 0:
                ser.disconnect()
                loop()
            elif head == 1:
                ser.sendData(bytearray([0xF7, 0x0B, 0x01, 0x19, 0x02, 0x40, 0x41, 0x01, 0x00, 0xE6, 0xEE]))
                loop()
            elif head == 2:
                ser.sendData(bytearray([0xF7, 0x0B, 0x01, 0x19, 0x02, 0x40, 0x41, 0x02, 0x00, 0xE5, 0xEE]))
                loop()
            elif head == 3:
                ser.release()
            else:
                loop()
        else:
            if head == 0:
                """
                print('Port: ')
                sysin = sys.stdin.readline()
                try:
                    port = sysin.split('\n')[0]
                except Exception:
                    port = '/dev/ttyUSB0'
                
                print('Baud Rate: ')
                sysin = sys.stdin.readline()
                try:
                    baud = int(sysin.split('\n')[0])
                except Exception:
                    baud = 9600
                
                ser.connect(port, baud)
                """
                ser.connect('/dev/ttyUSB0', 9600)
                loop()
            elif head == 1:
                ser.release()
            else:
                loop()
    
    loop()