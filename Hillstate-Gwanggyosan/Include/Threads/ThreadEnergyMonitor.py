import os
import sys
import time
import threading
import traceback
CURPATH = os.path.dirname(os.path.abspath(__file__))  # Project/Include/Threads
INCPATH = os.path.dirname(CURPATH)  # Project/Include/
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Common import Callback, writeLog, HEMSDevType, HEMSCategory
from Define import *
from RS485 import PacketParser


def prettifyPacket(packet: bytearray) -> str:
    return ' '.join(['%02X' % x for x in packet])
    
    
class ThreadEnergyMonitor(threading.Thread):
    _keepAlive: bool = True
    _home_initialized: bool = False
    _timeout_cnt: int = 0

    def __init__(self, 
        hems: HEMS, 
        parser: PacketParser, 
        interval_realtime_ms: int = 1 * 1000,
        interval_regular_ms: int = 60 * 60 * 1000
    ):
        threading.Thread.__init__(self, name='Energy Monitor Thread')
        self._hems = hems
        self._parser = parser
        self._interval_realtime_ms = interval_realtime_ms
        self._interval_regular_ms = interval_regular_ms
        self.sig_terminated = Callback()

    def run(self):
        log_send: bool = False
        query_init: bool = False

        writeLog('Started', self)
        tm_loop_realtime = time.perf_counter_ns() / 1e6 
        tm_loop_regular = time.perf_counter_ns() / 1e6
        while self._keepAlive:
            if not self._home_initialized:
                writeLog('Waiting for Initializing Home...', self)
                time.sleep(1)
                continue
            
            try:
                if not query_init:
                    self.send_query_regular(False)
                    tm_loop_regular = time.perf_counter_ns() / 1e6
                    query_init = True
                
                if time.perf_counter_ns() / 1e6 - tm_loop_realtime > self._interval_realtime_ms:
                    self.send_query_realtime(log_send)
                    tm_loop_realtime = time.perf_counter_ns() / 1e6

                if time.perf_counter_ns() / 1e6 - tm_loop_regular > self._interval_regular_ms:
                    self.send_query_regular(log_send)
                    tm_loop_regular = time.perf_counter_ns() / 1e6
            except Exception as e:
                writeLog(f'Exception::{e}', self)
                traceback.print_exc()
            time.sleep(100e-3)
        writeLog('Terminated', self)
        self.sig_terminated.emit()
    
    def stop(self):
        self._keepAlive = False

    def set_home_initialized(self):
        self._home_initialized = True

    def send_query(self, dev: HEMSDevType, category: HEMSCategory, log_send: bool = False, timeout: int = 2, sleep_sec: float = 0.5):
        if not self._parser.rs485.isConnected():
            writeLog(f'RS485 is not connected', self)
            return
        if self._parser.isRS485LineBusy():
            writeLog(f'RS485 line is busy', self)
            # for debugging
            if len(self._parser.buffer) > 0:
                buffer_str = prettifyPacket(self._parser.buffer)
                writeLog(f'Buffer: {buffer_str}', self)
            else:
                writeLog(f'Buffer: empty', self)
            return
        packet = self._hems.makePacketQuery(dev, category)
        self._parser.sendPacket(packet, log_send)
        self._parser.setRS485LineBusy(True)
        tm = time.perf_counter()
        is_timeout = False
        while self._parser.isRS485LineBusy():
            if time.perf_counter() - tm > timeout:
                is_timeout = True
                self._parser.setRS485LineBusy(False)
                break
            time.sleep(50e-3)
        if is_timeout:
            self._timeout_cnt += 1
            self._parser.setRS485LineBusy(False)
            writeLog(f'Timeout ({prettifyPacket(packet)})', self)
            if self._timeout_cnt > 10:
                writeLog(f'Too many timeout occurred, Try to reconnect RS485', self)
                self._parser.rs485.reconnect()
                self._timeout_cnt = 0
        else:
            self._timeout_cnt = 0
            if sleep_sec > 0:
                time.sleep(sleep_sec)

    def send_query_realtime(self, log_send: bool = False):
        self.send_query(HEMSDevType.Electricity, HEMSCategory.Current, log_send)
        # self.send_query(HEMSDevType.Water, HEMSCategory.Current, log_send)
        # self.send_query(HEMSDevType.Gas, HEMSCategory.Current, log_send)
        # self.send_query(HEMSDevType.HotWater, HEMSCategory.Current, log_send)
        # self.send_query(HEMSDevType.Heating, HEMSCategory.Current, log_send)

    def send_query_regular(self, log_send: bool = False):
        tm = time.perf_counter()

        writeLog(f"Start HEMS Regular Query (interval: {self._interval_regular_ms / 60000} min)", self)
        dev_list = [HEMSDevType.Electricity, HEMSDevType.Water, HEMSDevType.Gas, HEMSDevType.HotWater, HEMSDevType.Heating]
        cat_list = [HEMSCategory.History,HEMSCategory.OtherAverage,HEMSCategory.Fee,HEMSCategory.CO2,HEMSCategory.Target]
        for dev in dev_list:
            for cat in cat_list:
                self.send_query(dev, cat, log_send)
        elapsed = time.perf_counter() - tm
        writeLog(f"HEMS Regular Query Finished(elapsed: {elapsed} sec)", self)
