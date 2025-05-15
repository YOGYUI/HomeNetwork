import os
import sys
import time
import math
import queue
import threading
from typing import Union, Tuple
CURPATH = os.path.dirname(os.path.abspath(__file__))
INCPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Define import *
from Common import Callback, writeLog
from RS485 import PacketParser, RS485HwType


class ThreadCommandQueue(threading.Thread):
    _keepAlive: bool = True

    def __init__(self, queue_: queue.Queue):
        threading.Thread.__init__(self, name='Command Queue Thread')
        self._queue = queue_
        self._retry_cnt = 10
        self._delay_response = 0.4
        self.sig_start_seq = Callback()
        self.sig_finish_seq = Callback()
        self.sig_terminated = Callback()

    def run(self):
        writeLog('Started', self)
        while self._keepAlive:
            if not self._queue.empty():
                elem: dict = self._queue.get()
                elem_txt = '\n'
                for k, v in elem.items():
                    elem_txt += f'  {k}: {v}\n'
                writeLog(f'Get Command Queue: \n{{{elem_txt}}}', self)
                try:
                    dev = elem.get('device')
                    category = elem.get('category')
                    target = elem.get('target')
                    if target is None:
                        writeLog('target is not designated', self)
                        continue
                    parser = elem.get('parser')
                    if parser is None:
                        writeLog('parser is not designated', self)
                        continue
                    change_state = elem.get('change_state_after_command', False)
                    
                    self.sig_start_seq.emit()
                    if isinstance(dev, Light):
                        if category == 'state':
                            self.set_state_common(dev, target, parser, change_state)
                    elif isinstance(dev, EmotionLight):
                        if category == 'state':
                            self.set_state_common(dev, target, parser, change_state)
                    elif isinstance(dev, DimmingLight):
                        if category == 'state':
                            self.set_state_common(dev, target, parser, change_state)
                        elif category == 'brightness':
                            self.set_brightness(dev, target, parser, change_state)
                    elif isinstance(dev, Outlet):
                        if category == 'state':
                            self.set_state_common(dev, target, parser, change_state)
                    elif isinstance(dev, GasValve):
                        if category == 'state':
                            if target == 0:
                                self.set_state_common(dev, target, parser, change_state)
                            else:  # 밸브 여는것은 지원되지 않음!
                                """
                                packet_test = dev.makePacketSetState(True)
                                parser.sendPacket(packet_test)
                                interval, _ = self.getSendParams(parser)
                                time.sleep(interval)
                                """
                                packet_query = dev.makePacketQueryState()
                                parser.sendPacket(packet_query)
                    elif isinstance(dev, Thermostat):
                        if category == 'state':
                            if target == 'OFF':
                                self.set_state_common(dev, 0, parser, change_state)
                            elif target == 'HEAT':
                                self.set_state_common(dev, 1, parser, change_state)
                        elif category == 'temperature':
                            self.set_target_temperature(dev, target, parser, change_state)
                    elif isinstance(dev, Ventilator):
                        if category == 'state':
                            self.set_state_common(dev, target, parser, change_state)
                        elif category == 'rotationspeed':
                            self.set_rotation_speed(dev, target, parser, change_state)
                    elif isinstance(dev, AirConditioner):
                        if category == 'active':
                            # for handling homebridge entity
                            self.set_state_common(dev, target, parser, change_state)
                            if target:
                                self.set_airconditioner_mode(dev, 1, parser, change_state)  # 최초 가동 시 모드를 '냉방'으로 바꿔준다
                                # self.set_rotation_speed(dev, 1, parser, change_state)  # 최초 가동 시 풍량을 '자동'으로 바꿔준다
                        elif category == 'mode':
                            # for handling homeassistant entity
                            # "off": 0, "cool": 1, "auto": 2, "dry": 3, "fan_only": 4
                            if not target:  
                                self.set_state_common(dev, 0, parser, change_state)
                            else:
                                self.set_state_common(dev, 1, parser, change_state)
                                mode_value = 1  # default = 냉방
                                if target == 2:
                                    # 자동
                                    mode_value = 0
                                elif target == 3:
                                    # 제습
                                    mode_value = 2
                                elif target == 4:
                                    # 송풍
                                    mode_value = 3
                                self.set_airconditioner_mode(dev, mode_value, parser, change_state)
                        elif category == 'temperature':
                            self.set_target_temperature(dev, target, parser, change_state)
                        elif category == 'rotationspeed':
                            self.set_rotation_speed(dev, target, parser, change_state)
                    elif isinstance(dev, Elevator):
                        if category == 'state':
                            self.set_elevator_call(dev, target, parser, change_state)
                    elif isinstance(dev, SubPhone):
                        if category == 'streaming':
                            self.set_subphone_streaming_state(dev, target, parser, change_state)
                        elif category == 'doorlock':
                            self.set_subphone_doorlock_state(dev, target, parser, change_state)
                        elif category == 'lock_front':
                            self.set_subphone_lock_front_state(dev, target, parser, change_state)
                        elif category == 'lock_communal':
                            self.set_subphone_lock_communal_state(dev, target, parser, change_state)
                    elif isinstance(dev, BatchOffSwitch):
                        if category == 'state':
                            self.set_state_common(dev, target, parser, change_state)
                    """
                    elif isinstance(dev, DoorLock):
                        if category == 'state':
                            if target == 'Unsecured':
                                self.set_doorlock_open(dev, parser)
                    """
                    self.sig_finish_seq.emit()
                except Exception as e:
                    writeLog(str(e), self)
            else:
                time.sleep(1e-3)
        writeLog('Terminated', self)
        self.sig_terminated.emit()

    def stop(self):
        self._keepAlive = False

    @staticmethod
    def getSendParams(parser: PacketParser) -> Tuple[float, int]:
        """
        interval = 0.2
        retry_cnt = 10
        if parser.getRS485HwType() == RS485HwType.Socket:
            # ew11은 무선 송수신 레이턴시때문에 RS485 IDLE 시간을 명확하게 알 수 없으므로
            # 짧은 간격으로 패킷을 많이 쏴보도록 한다
            interval = 0.1
            retry_cnt = 50
        """
        interval_sec = parser.send_command_interval_ms / 1000
        retry_cnt = parser.send_command_retry_count
        return interval_sec, retry_cnt

    def set_state_common(self, dev: Device, target: int, parser: PacketParser, change_state: bool = False):
        tm_start = time.perf_counter()
        cnt = 0

        if isinstance(dev, Outlet):
            if target == 0 and not dev.enable_off_command:
                writeLog(f'set_state_common::{dev} - off command is prohibited', self)
                dev.publishMQTT()
                return

        packet_command = dev.makePacketSetState(bool(target))
        interval, retry_cnt = self.getSendParams(parser)
        success = False
        while cnt < retry_cnt:
            if dev.state == target:
                success = True
                break
            if parser.isRS485LineBusy():
                time.sleep(1e-3)  # prevent cpu occupation
                continue
            parser.sendPacket(packet_command)
            cnt += 1
            time.sleep(interval)  # wait for parsing response
        if cnt > 0:
            tm_elapsed = time.perf_counter() - tm_start
            writeLog('set_state_common::send # = {}, elapsed = {:g} msec'.format(cnt, tm_elapsed * 1000), self)
            time.sleep(self._delay_response)
        if not success and change_state:
            dev.state = target
        dev.publishMQTT()

    def set_brightness(self, dev: Union[DimmingLight], brightness: int, parser: PacketParser, change_state: bool = False):
        tm_start = time.perf_counter()
        cnt = 0
        conv = dev.convert_level_to_word(brightness)
        packet_command = dev.makePacketSetBrightness(conv)
        interval, retry_cnt = self.getSendParams(parser)
        success = False
        while cnt < retry_cnt:
            if dev.brightness == conv:
                success = True
                break
            if parser.isRS485LineBusy():
                time.sleep(1e-3)  # prevent cpu occupation
                continue
            parser.sendPacket(packet_command)
            cnt += 1
            time.sleep(interval)  # wait for parsing response
        if cnt > 0:
            tm_elapsed = time.perf_counter() - tm_start
            writeLog('set_brightness::send # = {}, elapsed = {:g} msec'.format(cnt, tm_elapsed * 1000), self)
            time.sleep(self._delay_response)
        if not success and change_state:
            dev.brightness = conv
        dev.publishMQTT()

    def set_target_temperature(self, dev: Union[Thermostat, AirConditioner], target: float, parser: PacketParser, change_state: bool = False):
        # 힐스테이트는 온도값 범위가 정수형이므로 올림처리해준다
        tm_start = time.perf_counter()
        cnt = 0
        target_temp = math.ceil(target)
        packet_command = dev.makePacketSetTemperature(target_temp)
        interval, retry_cnt = self.getSendParams(parser)
        success = False
        while cnt < retry_cnt:
            if not dev.state:
                """
                Issue: OFF 상태에서 희망온도 설정 패킷만 보냈을 때 디바이스가 ON되는 문제 방지
                (애플 자동화 끄기 - OFF, 희망온도 두 개 명령이 각각 수신되는 경우, 희망온도 명령에 의해 켜지는 문제)
                TODO: 옵션 플래그로 변경
                """
                success = True
                break
            if dev.temp_config == target_temp:
                success = True
                break
            if parser.isRS485LineBusy():
                time.sleep(1e-3)  # prevent cpu occupation
                continue
            parser.sendPacket(packet_command)
            cnt += 1
            time.sleep(interval)  # wait for parsing response
        if cnt > 0:
            tm_elapsed = time.perf_counter() - tm_start
            writeLog('set_target_temperature::send # = {}, elapsed = {:g} msec'.format(cnt, tm_elapsed * 1000), self)
            time.sleep(self._delay_response)
        if not success and change_state:
            dev.temp_config = target_temp
        dev.publishMQTT()

    def set_rotation_speed(self, dev: Union[Ventilator, AirConditioner], target: int, parser: PacketParser, change_state: bool = False):
        tm_start = time.perf_counter()
        if isinstance(dev, Ventilator):
            # Speed 값 변환 (100단계의 풍량을 세단계로 나누어 1, 3, 7 중 하나로)
            if target <= 30:
                conv = 0x01
            elif target <= 60:
                conv = 0x03
            else:
                conv = 0x07
        else:
            # Speed 값 변환
            if target <= 25:
                conv = 0x01
            elif target <= 50:
                conv = 0x02
            elif target <= 75:
                conv = 0x03
            else:
                conv = 0x04
        cnt = 0
        packet_command = dev.makePacketSetRotationSpeed(conv)
        interval, retry_cnt = self.getSendParams(parser)
        success = False
        while cnt < retry_cnt:
            if dev.rotation_speed == conv:
                success = True
                break
            if parser.isRS485LineBusy():
                time.sleep(1e-3)  # prevent cpu occupation
                continue
            parser.sendPacket(packet_command)
            cnt += 1
            time.sleep(interval)  # wait for parsing response
        if cnt > 0:
            tm_elapsed = time.perf_counter() - tm_start
            writeLog('set_rotation_speed::send # = {}, elapsed = {:g} msec'.format(cnt, tm_elapsed * 1000), self)
            time.sleep(self._delay_response)
        if not success and change_state:
            dev.rotation_speed = conv
        dev.publishMQTT()

    def set_airconditioner_mode(self, dev: AirConditioner, target: int, parser: PacketParser, change_state: bool = False):
        tm_start = time.perf_counter()
        cnt = 0
        packet_command = dev.makePacketSetMode(target)
        interval, retry_cnt = self.getSendParams(parser)
        success = False
        while cnt < retry_cnt:
            if dev.mode == target:
                success = True
                break
            if parser.isRS485LineBusy():
                time.sleep(1e-3)  # prevent cpu occupation
                continue
            parser.sendPacket(packet_command)
            cnt += 1
            time.sleep(interval)  # wait for parsing response
        if cnt > 0:
            tm_elapsed = time.perf_counter() - tm_start
            writeLog('set_airconditioner_mode::send # = {}, elapsed = {:g} msec'.format(cnt, tm_elapsed * 1000), self)
            time.sleep(self._delay_response)
        if not success and change_state:
            dev.mode = target
        dev.publishMQTT()
    
    def set_elevator_call(self, dev: Elevator, target: int, parser: PacketParser, change_state: bool = False):
        tm_start = time.perf_counter()
        cnt = 0
        """
        if target in 5:
            packet_command = dev.makePacketCallUpside()
        elif target == 6:
            packet_command = dev.makePacketCallDownside()
        elif target == 0:
            packet_command = dev.makePacketRevokeCall()
        else:
            return
        """
        packet_command = dev.makePacketCall(target)
        interval, retry_cnt = self.getSendParams(parser)
        success = False
        while cnt < retry_cnt:
            if dev.check_call_command_done(target):
                success = True
                break
            if parser.isRS485LineBusy():
                time.sleep(1e-3)  # prevent cpu occupation
                continue
            parser.sendPacket(packet_command)
            cnt += 1
            time.sleep(interval)  # wait for parsing response
        if cnt > 0:
            tm_elapsed = time.perf_counter() - tm_start
            writeLog('set_elevator_call({})::send # = {}, elapsed = {:g} msec'.format(target, cnt, tm_elapsed * 1000), self)
            time.sleep(self._delay_response)
        if not success and change_state:
            pass
        # dev.publishMQTT()

    def set_subphone_streaming_state(self, dev: SubPhone, target: int, parser: PacketParser, change_state: bool = False):
        packet = dev.makePacketSetVideoStreamingState(target)
        parser.sendPacket(packet)
        dev.updateState(0, streaming=target)

    def set_subphone_doorlock_state(self, dev: SubPhone, target: str, parser: PacketParser, change_state: bool = False):
        if target == "Unsecured":
            dev.updateState(0, doorlock=0)  # 0: Unsecured
            if dev.state_ringing.value == 2:  # 공동출입문
                packet_open = dev.makePacketOpenCommunalDoor()
            else:
                packet_open = dev.makePacketOpenFrontDoor()
                
            if dev.state_streaming:
                parser.sendPacket(packet_open)
            else:
                parser.sendPacket(dev.makePacketSetVideoStreamingState(1))
                time.sleep(0.2)
                parser.sendPacket(packet_open)
                time.sleep(0.2)
            parser.sendPacket(dev.makePacketSetVideoStreamingState(0))
        elif target == 'Secured':
            dev.updateState(0, doorlock=1)  # 1: Secured

    def set_subphone_lock_front_state(self, dev: SubPhone, target: str, parser: PacketParser, change_state: bool = False):
        if target == "Unsecured":
            dev.updateState(0, lock_front=0)  # 0: Unsecured
            packet_open = dev.makePacketOpenFrontDoor()
            if not dev.state_streaming:
                parser.sendPacket(dev.makePacketSetVideoStreamingState(1))
                time.sleep(0.2)
            parser.sendPacket(packet_open)
            time.sleep(0.2)
            parser.sendPacket(dev.makePacketSetVideoStreamingState(0))
        elif target == "Secured":
            dev.updateState(0, lock_front=1)  # 1: Secured

    def set_subphone_lock_communal_state(self, dev: SubPhone, target: str, parser: PacketParser, change_state: bool = False):
        if target == "Unsecured":
            dev.updateState(0, lock_communal=0)  # 0: Unsecured
            packet_open = dev.makePacketOpenCommunalDoor()
            prev_state_ringing = dev.state_ringring_communal
            if not dev.state_streaming:
                parser.sendPacket(dev.makePacketSetVideoStreamingState(1))
                time.sleep(0.2)
            parser.sendPacket(packet_open)
            time.sleep(0.2)
            parser.sendPacket(dev.makePacketSetVideoStreamingState(0))
            if not prev_state_ringing:
                dev.updateState(0, lock_communal=1)  # 1: Secured
        elif target == "Secured":
            dev.updateState(0, lock_communal=1)  # 1: Secured

    """
    def set_doorlock_open(self, dev: DoorLock, parser: PacketParser):
        dev.open()  # GPIO
        packet_command = dev.makePacketOpen()
        parser.sendPacket(packet_command)
        time.sleep(0.3)
        parser.sendPacket(packet_command)
        time.sleep(0.3)
    """
