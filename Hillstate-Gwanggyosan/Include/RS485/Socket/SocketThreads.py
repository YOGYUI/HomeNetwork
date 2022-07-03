import os
import sys
import time
import queue
import socket
import threading
from typing import Union
from abc import abstractmethod, ABCMeta
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/Include/RS485/Socket
INCPATH = os.path.dirname(os.path.dirname(CURPATH))  # {$PROJECT}/Include/
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Common import writeLog, Callback


class ThreadCommon(threading.Thread):
    __metaclass__ = ABCMeta

    _keepAlive: bool = True
    _sock: Union[socket.socket, None] = None
    _loop_sleep_time: float = 1e-3

    def __init__(self, name: str = 'Socket Thread Common'):
        threading.Thread.__init__(self, name=name)
        self.sig_terminated = Callback()
        self.sig_send = Callback(bytes)
        self.sig_recv = Callback(bytes)
        self.sig_exception = Callback(str, bool)  # message, terminate socket flag
        self.setDaemon(True)
    
    def run(self):
        writeLog('Started', self)
        while self._keepAlive:
            self.loop()
            if self._loop_sleep_time > 0:
                time.sleep(self._loop_sleep_time)
        writeLog('Terminated', self)
        self.sig_terminated.emit()
    
    @abstractmethod
    def loop(self):
        pass

    def stop(self):
        self._keepAlive = False
    
    def setSocket(self, sock: socket.socket):
        self._sock = sock


class ThreadSend(ThreadCommon):
    def __init__(self, sock: socket.socket, queue_send: queue.Queue):
        super().__init__(name='Socket Thread Send')
        self._sock = sock
        self._queue_send = queue_send
    
    def loop(self):
        try:
            if not isinstance(self._sock, socket.socket):
                return
            if not self._queue_send.empty():
                data = self._queue_send.get()
                datalen = len(data)
                while datalen > 0:
                    sendlen = self._sock.send(data)
                    self.sig_send.emit(data[:sendlen])
                    data = data[sendlen:]
                    datalen = len(data)
        except OSError as e:
            if e.args[0] == 10038:
                self.sig_exception.emit(f'OSError 10038 ({e})', True)
        except Exception as e:
            self.sig_exception.emit(f'Exception ({e})', True)


class ThreadRecv(ThreadCommon):
    def __init__(self, sock: socket.socket, queue_recv: queue.Queue, bufsize: int = 4096):
        super().__init__(name='Socket Thread Recv')
        self._sock = sock
        self._queue_recv = queue_recv
        self._bufsize = bufsize
        self._loop_sleep_time = 0.

    def loop(self):
        try:
            if isinstance(self._sock, socket.socket):
                data = self._sock.recv(self._bufsize)
                if data is None or len(data) == 0:
                    self.sig_exception.emit('Lost connection', True)
                    self.stop()
                else:
                    self.sig_recv.emit(data)
                    self._queue_recv.put(data)
        except OSError as e:
            if e.args[0] == 10038:
                self.sig_exception.emit(str(e), False)
                self.stop()
            elif e.args[0] == 10022:
                self.sig_exception.emit(str(e), False)
        except Exception as e:
            self.sig_exception.emit(f'Exception ({e})', True)
            self.stop()


class ThreadCheckRecvQueue(ThreadCommon):
    def __init__(self, queue_recv: queue.Queue):
        super().__init__(name='Socket Thread Check Recv Queue')
        self._queue_recv = queue_recv
    
    def loop(self):
        if not self._queue_recv.empty():
            data = self._queue_recv.get()
            self.sig_recv.emit(data)
