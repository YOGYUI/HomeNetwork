
import datetime
import threading
from functools import reduce


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

    def emit(self, *args):
        if len(args) != len(self._args):
            raise Exception('Callback::Argument Length Mismatch')
        arglen = len(args)
        if arglen > 0:
            validTypes = [checkAgrumentType(args[i], self._args[i]) for i in range(arglen)]
            if sum(validTypes) != arglen:
                raise Exception('Callback::Argument Type Mismatch (Definition: {}, Call: {})'.format(self._args, args))
        for callback in self._callbacks:
            callback(*args)


def timestampToString(timestamp: datetime.datetime):
    h = timestamp.hour
    m = timestamp.minute
    s = timestamp.second
    us = timestamp.microsecond
    return '%02d:%02d:%02d.%06d' % (h, m, s, us)


def getCurTimeStr():
    return '<%s>' % timestampToString(datetime.datetime.now())


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


def calculate_bestin_checksum(packet: bytearray) -> int:
    # special thanks to laz-
    # https://gist.github.com/laz-/a507af756e13e64ed3aaceb236b5ad49
    try:
        return reduce(lambda x, y: ((x ^ y) + 1) & 0xFF, packet, 3)
    except Exception as e:
        writeLog(f'Calc Bestin Checksum Error ({e})')
        return 0
