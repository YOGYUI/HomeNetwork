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
from Common import Callback, writeLog
from Define import *
from RS485 import ParserSubPhone


def prettifyPacket(packet: bytearray) -> str:
    return ' '.join(['%02X' % x for x in packet])
    
    
class ThreadEnergyMonitor(threading.Thread):
    _keepAlive: bool = True
    _home_initialized: bool = False

    def __init__(self, 
        subphone: SubPhone, 
        parser: ParserSubPhone, 
        interval_realtime_ms: int = 1 * 1000,
        interval_regular_ms: int = 60 * 60 * 1000
    ):
        threading.Thread.__init__(self, name='Energy Monitor Thread')
        self._subphone = subphone
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
                writeLog('Home is not initialized!', self)
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
            return
        packet = self._subphone.makePacketQueryHEMS(dev, category)
        self._parser.sendPacket(packet, log_send)
        self._parser.line_busy = True
        tm = time.perf_counter()
        is_timeout = False
        while self._parser.isRS485LineBusy():
            if time.perf_counter() - tm > timeout:
                is_timeout = True
                self._parser.line_busy = False
                break
            time.sleep(50e-3)
        if is_timeout:
            writeLog(f'Timeout ({prettifyPacket(packet)})', self)
        else:
            if sleep_sec > 0:
                time.sleep(sleep_sec)

    def send_query_realtime(self, log_send: bool = False):
        self.send_query(HEMSDevType.Electricity, HEMSCategory.Current, log_send)
        # self.send_query(HEMSDevType.Water, HEMSCategory.Current, log_send)
        # self.send_query(HEMSDevType.Gas, HEMSCategory.Current, log_send)
        # self.send_query(HEMSDevType.HotWater, HEMSCategory.Current, log_send)
        # self.send_query(HEMSDevType.Heating, HEMSCategory.Current, log_send)

    def send_query_regular(self, log_send: bool = False):
        writeLog("start regular query", self)
        self.send_query(HEMSDevType.Electricity, HEMSCategory.History, log_send)
        self.send_query(HEMSDevType.Electricity, HEMSCategory.OtherAverage, log_send)
        self.send_query(HEMSDevType.Electricity, HEMSCategory.Fee, log_send)
        self.send_query(HEMSDevType.Electricity, HEMSCategory.CO2, log_send)
        self.send_query(HEMSDevType.Electricity, HEMSCategory.Target, log_send)
        
        self.send_query(HEMSDevType.Water, HEMSCategory.History, log_send)
        self.send_query(HEMSDevType.Water, HEMSCategory.OtherAverage, log_send)
        self.send_query(HEMSDevType.Water, HEMSCategory.Fee, log_send)
        self.send_query(HEMSDevType.Water, HEMSCategory.CO2, log_send)
        self.send_query(HEMSDevType.Water, HEMSCategory.Target, log_send)
        
        self.send_query(HEMSDevType.Gas, HEMSCategory.History, log_send)
        self.send_query(HEMSDevType.Gas, HEMSCategory.OtherAverage, log_send)
        self.send_query(HEMSDevType.Gas, HEMSCategory.Fee, log_send)
        self.send_query(HEMSDevType.Gas, HEMSCategory.CO2, log_send)
        self.send_query(HEMSDevType.Gas, HEMSCategory.Target, log_send)
        
        self.send_query(HEMSDevType.HotWater, HEMSCategory.History, log_send)
        self.send_query(HEMSDevType.HotWater, HEMSCategory.OtherAverage, log_send)
        self.send_query(HEMSDevType.HotWater, HEMSCategory.Fee, log_send)
        self.send_query(HEMSDevType.HotWater, HEMSCategory.CO2, log_send)
        self.send_query(HEMSDevType.HotWater, HEMSCategory.Target, log_send)
        
        self.send_query(HEMSDevType.Heating, HEMSCategory.History, log_send)
        self.send_query(HEMSDevType.Heating, HEMSCategory.OtherAverage, log_send)
        self.send_query(HEMSDevType.Heating, HEMSCategory.Fee, log_send)
        self.send_query(HEMSDevType.Heating, HEMSCategory.CO2, log_send)
        self.send_query(HEMSDevType.Heating, HEMSCategory.Target, log_send)
