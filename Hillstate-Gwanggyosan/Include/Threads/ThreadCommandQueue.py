import os
import sys
import time
import queue
import threading
from typing import Union
CURPATH = os.path.dirname(os.path.abspath(__file__))
INCPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Define import *
from Common import Callback, writeLog
from RS485 import SerialParser


class ThreadCommandQueue(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Command Queue Thread')
        self._queue = queue_
        self._retry_cnt = 10
        self._delay_response = 0.4
        self.sig_terminated = Callback()

    def run(self):
        writeLog('Started', self)
        while self._keepAlive:
            if not self._queue.empty():
                elem = self._queue.get()
                elem_txt = '\n'
                for k, v in elem.items():
                    elem_txt += f'  {k}: {v}\n'
                writeLog(f'Get Command Queue: \n{{{elem_txt}}}', self)
                try:
                    dev = elem['device']
                    category = elem['category']
                    target = elem['target']
                    parser = elem['parser']
                    if target is None:
                        continue

                    if isinstance(dev, Light):
                        if category == 'state':
                            self.set_state_common(dev, target, parser)
                    elif isinstance(dev, Outlet):
                        if category == 'state':
                            self.set_state_common(dev, target, parser)
                    elif isinstance(dev, GasValve):
                        if category == 'state':
                            if target == 0:  # 밸브 여는것은 지원되지 않음!
                                self.set_state_common(dev, target, parser)
                            else:
                                packet_query = dev.makePacketQueryState()
                                parser.sendPacket(packet_query)
                except Exception as e:
                    writeLog(str(e), self)
            else:
                time.sleep(1e-3)
        writeLog('Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False

    def set_state_common(self, dev: Device, target: int, parser: SerialParser):
        cnt = 0
        packet_command = dev.makePacketSetState(bool(target))
        packet_query = dev.makePacketQueryState()
        for _ in range(self._retry_cnt):
            if dev.state == target:
                break
            parser.sendPacket(packet_command)
            cnt += 1
            time.sleep(0.2)
            if dev.state == target:
                break
            parser.sendPacket(packet_query)
            time.sleep(0.2)
        writeLog('set_state_common::send # = {}'.format(cnt), self)
        time.sleep(self._delay_response)
        dev.publish_mqtt()
