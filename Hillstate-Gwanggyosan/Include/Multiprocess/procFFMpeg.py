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


def procFFMpeg(cfg: dict, pipe: connection.Connection):
    pid = os.getpid()
    name = mp.current_process().name
    prefix = f'[MultiProcess][{name}({pid})] '
    writeLog(prefix + 'Started')

    idev = cfg.get('input_device', '/dev/video0')
    fps = cfg.get('frame_rate', 30)
    width = cfg.get('width', 480)
    height = cfg.get('height', 320)
    feed = cfg.get('feed_path', 'http://0.0.0.0:8090/feed.ffm')
    rtmp_server = cfg.get('rtmp_server', 'rtmp://0.0.0.0:1935/live')
    # cmd = f"exec ~/ffmpeg/ffmpeg -i {idev} -r {fps} -s {width}x{height} -threads 1 {feed}"
    cmd = f"exec ffmpeg -i {idev} -f flv {rtmp_server}"

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
