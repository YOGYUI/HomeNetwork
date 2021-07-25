from Parser import Parser


class EnergyParser(Parser):
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


if __name__ == '__main__':
    import os
    import sys
    import time
    from SerialComm import SerialComm

    ser = SerialComm()
    par = EnergyParser(ser)

    def printMenu():
        if ser.isConnected():
            print('Connected ({}, {})'.format(ser.port, ser.baudrate))
            print('0: Read, 1: Write, 2: Disconnect, 3: Terminate, 4: Test')
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
                print('Chunk # to read: ')
                sysin = sys.stdin.readline()
                try:
                    cnt = int(sysin.split('\n')[0])
                except Exception:
                    cnt = 10

                if cnt > 0:
                    ser.reset_input_buffer()
                    par.startRecv(cnt)
                    print('Press Any key to continue...')
                    sys.stdin.readline()
                loop()
            elif head == 1:
                print('Data to write: ')
                temp = sys.stdin.readline().replace('\n', '').strip()
                ser.sendData(bytearray([int(x, 16) for x in temp.split(' ')]))
                par.startRecv(4)
                print('Press Any key to continue...')
                sys.stdin.readline()
                loop()
            elif head == 2:
                ser.disconnect()
                loop()
            elif head == 3:
                ser.release()
            elif head == 4:
                import time
                print('Data to write: ')
                temp = sys.stdin.readline().replace('\n', '').strip()
                arr_temp = bytearray([int(x, 16) for x in temp.split(' ')])
                for i in range(0xFF + 1):
                    print('Test {}'.format(i))
                    ser.sendData(arr_temp + bytearray([i]))
                    time.sleep(0.2)
                    ser.sendData(arr_temp + bytearray([i]))
                    time.sleep(0.2)
                    # par.startRecv(8)
                    # time.sleep(0.5)
                print('Press Any key to continue...')
                sys.stdin.readline()
                loop()
            elif head == 5:
                import time
                # temp = '02 41 0D 01 97 01 81 00 00 00 00 01'
                # temp = '02 D1 0D 01 97 00 8F 00 00 00 00 04'
                temp = '02 31 0D 01 58 04 8F 00 00 00 00 04'
                arr_temp = bytearray([int(x, 16) for x in temp.split(' ')])
                for i in range(0xFF + 1):
                    print('Test {}'.format(i))
                    ser.sendData(arr_temp + bytearray([i]))
                    time.sleep(0.2)
                    ser.sendData(arr_temp + bytearray([i]))
                    time.sleep(0.2)
                    # par.startRecv(8)
                    # time.sleep(0.5)
                print('Press Any key to continue...')
                sys.stdin.readline()
                loop()
            else:
                loop()
        else:
            if head == 0:
                print('Baud Rate: ')
                sysin = sys.stdin.readline()
                try:
                    baud = int(sysin.split('\n')[0])
                except Exception:
                    baud = 9600
                ser.connect('/dev/rs485_energy', baud)
                loop()
            elif head == 1:
                ser.release()
            else:
                loop()
    
    loop()
