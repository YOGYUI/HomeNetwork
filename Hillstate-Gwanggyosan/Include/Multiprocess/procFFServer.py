import os
import sys
import subprocess
import multiprocessing as mp
from multiprocessing import connection
CURPATH = os.path.dirname(os.path.abspath(__file__))
INCPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, INCPATH
from Common import writeLog


def procFFServer(cfg: dict, pipe: connection.Connection):
    pid = os.getpid()
    name = mp.current_process().name
    prefix = f'[MultiProcess][{name}({pid})] '
    writeLog(prefix + 'Started')

    conf_path = cfg.get('conf_file_path')
    cmd = f'exec ~/ffmpeg/ffserver -f {conf_path}'
    
    with subprocess.Popen(cmd, 
        shell=True, 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT
    ) as subproc:
        pid = subproc.pid
        writeLog(prefix + f'Subprocess {pid} opened')
        msg = f'{pid}'
        pipe.send_bytes(msg.encode(encoding='utf-8', errors='ignore'))
        writeLog(prefix + f'Send Subprocess PID Info to pipe')
        buff = subproc.stdout.read() 
        print(buff.decode(encoding='UTF-8'))
    
    writeLog(prefix + 'Terminated')
