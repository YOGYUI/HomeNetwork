import _io
import datetime
import threading
from functools import partial
from enum import IntEnum, auto, unique
import xml.etree.ElementTree as ElementTree


def checkAgrumentType(obj, arg):
    if type(obj) == arg:
        return True
    if arg == object:
        return True
    if arg in obj.__class__.__bases__:
        return True
    return False


class Callback(object):
    _args = None

    def __init__(self, *args):
        self._args = args
        self._callbacks = list()

    def connect(self, callback):
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def disconnect(self, callback=None):
        if callback is None:
            self._callbacks.clear()
        else:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def emit(self, *args):
        if len(self._callbacks) == 0:
            return
        if len(args) != len(self._args):
            raise Exception('Callback::Argument Length Mismatch')
        arglen = len(args)
        if arglen > 0:
            validTypes = [checkAgrumentType(args[i], self._args[i]) for i in range(arglen)]
            if sum(validTypes) != arglen:
                raise Exception('Callback::Argument Type Mismatch (Definition: {}, Call: {})'.format(self._args, args))
        for callback in self._callbacks:
            callback(*args)


def getCurTimeStr():
    now = datetime.datetime.now()
    return '<%04d-%02d-%02d %02d:%02d:%02d.%03d>' % (now.year, now.month, now.day, now.hour, now.minute, now.second, now.microsecond // 1000)


def writeLog(strMsg: str, obj: object = None):
    strTime = getCurTimeStr()
    if obj is not None:
        if isinstance(obj, threading.Thread):
            if obj.ident is not None:
                strObj = ' [%s (0x%X)]' % (type(obj).__name__, obj.ident)
            else:
                strObj = ' [%s (0x%X)]' % (type(obj).__name__, id(obj))
        else:
            strObj = ' [%s (0x%X)]' % (type(obj).__name__, id(obj))
    else:
        strObj = ''

    msg = strTime + strObj + ' ' + strMsg
    print(msg)


def prettifyPacket(packet: bytearray) -> str:
    return ' '.join(['%02X' % x for x in packet])


class bind(partial):
    # https://stackoverflow.com/questions/7811247/how-to-fill-specific-positional-arguments-with-partial-in-python
    """
    An improved version of partial which accepts Ellipsis (...) as a placeholder
    """
    def __call__(self, *args, **keywords):
        keywords = {**self.keywords, **keywords}
        iargs = iter(args)
        args = (next(iargs) if arg is ... else arg for arg in self.args)
        return self.func(*args, *iargs, **keywords)


@unique
class DeviceType(IntEnum):
    UNKNOWN = 0
    LIGHT = auto()
    OUTLET = auto()
    THERMOSTAT = auto()
    AIRCONDITIONER = auto()
    GASVALVE = auto()
    VENTILATOR = auto()
    ELEVATOR = auto()
    SUBPHONE = auto()
    HEMS = auto()
    BATCHOFFSWITCH = auto()
    DOORLOCK = auto()
    EMOTIONLIGHT = auto()
    DIMMINGLIGHT = auto()


@unique
class HEMSDevType(IntEnum):
    Unknown = 0
    Electricity = 1  # 전기
    Water = 2  # 수도
    Gas = 3  # 가스
    HotWater = 4  # 온수
    Heating = 5  # 난방
    Reserved = 10  # ?


@unique
class HEMSCategory(IntEnum):
    Unknown = 0
    History = 1  # 우리집 사용량 이력 (3달간, 단위: kWh/L/MWh)
    OtherAverage = 2  # 동일평수 평균 사용량 이력 (3달간, 단위: kWh/L/MWh)
    Fee = 3  # 요금 이력 (3달간, 단위: 천원)
    CO2 = 4  # CO2 배출량 이력 (3달간, 단위: kg)
    Target = 5  # 목표량
    Current = 7  # 현재 실시간 사용량 


def writeXmlFile(elem: ElementTree.Element, path: str = '', fp: _io.TextIOWrapper = None, level: int = 0):
    if fp is None:
        _fp = open(path, 'w', encoding='utf-8')
        _fp.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>' + '\n')
    else:
        _fp = fp
    _fp.write('\t' * level)
    _fp.write('<' + elem.tag)
    for key in elem.keys():
        _fp.write(' ' + key + '="' + elem.attrib[key] + '"')
    if len(list(elem)) > 0:
        _fp.write('>\n')
        for child in list(elem):
            writeXmlFile(child, fp=_fp, level=level+1)
        _fp.write('\t' * level)
        _fp.write('</' + elem.tag + '>\n')
    else:
        if elem.text is not None:
            txt = elem.text
            txt = txt.replace('\r', '')
            txt = txt.replace('\n', '')
            txt = txt.replace('\t', '')
            if len(txt) > 0:
                _fp.write('>' + txt + '</' + elem.tag + '>\n')
            else:
                _fp.write('/>\n')
        else:
            _fp.write('/>\n')
    if level == 0:
        _fp.close()
