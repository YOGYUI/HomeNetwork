import os
import sys
import time
import threading
from typing import List
CURPATH = os.path.dirname(os.path.abspath(__file__))  # Project/Include/Threads
INCPATH = os.path.dirname(CURPATH)  # Project/Include/
DEFPATH = os.path.join(INCPATH, 'Define')  # Project/Include/Define
sys.path.extend([CURPATH, INCPATH, DEFPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH, DEFPATH
from Common import Callback, writeLog


class ThreadQueryState(threading.Thread):
    _keepAlive: bool = True

    def __init__(
        self, 
        device_list: list, 
        parser_mapping: dict, 
        rs485_info_list: list,
        period: int,
        verbose: bool
    ):
        threading.Thread.__init__(self, name='Query State Thread')
        self.device_list = device_list
        self.parser_mapping = parser_mapping
        self.rs485_info_list = rs485_info_list
        self.period = period
        self.verbose = verbose
        self.sig_terminated = Callback()
        self.available = True
    
    def run(self):
        writeLog('Started', self)
        while self._keepAlive:
            for dev in self.device_list:
                if not self._keepAlive:
                    break

                dev_type = dev.getType()
                index = self.parser_mapping.get(dev_type)
                info = self.rs485_info_list[index]
                packet_query = dev.makePacketQueryState()
                while not self.available:
                    if not self._keepAlive:
                        break
                    time.sleep(1e-3)
                while info.parser.isRS485LineBusy():
                    if not self._keepAlive:
                        break
                    time.sleep(1e-3)
                if self.verbose:
                    writeLog(f'sending query packet for {dev_type.name}/idx={dev.index}/room={dev.room_index}', self)
                info.parser.sendPacket(packet_query, self.verbose)
                
                time.sleep(self.period * 1e-3)
        writeLog('Terminated', self)
        self.sig_terminated.emit()
    
    def stop(self):
        self._keepAlive = False

    def setAvailable(self, value: bool):
        self.available = value
