from Parser import Parser


class ControlParser(Parser):
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


if __name__ == '__main__':
    import os
    import sys
    import time
    from SerialComm import SerialComm

    ser = SerialComm()
    par = ControlParser(ser)

    def printMenu():
        if ser.isConnected():
            print('Connected ({}, {})'.format(ser.port, ser.baudrate))
            print('0: Read, 1: Write, 2: Disconnect, 3: Terminate')
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
                try:
                    arr_temp = bytearray([int(x, 16) for x in temp.split(' ')])
                except Exception:
                    loop()
                    return
                for i in range(0xFF + 1):
                    print('Test {}'.format(i))
                    for _ in range(4):
                        ser.sendData(arr_temp + bytearray([i]))
                        time.sleep(0.4)
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
                ser.connect('/dev/ttyUSB0', baud)
                loop()
            elif head == 1:
                ser.release()
            else:
                loop()
    
    loop()
