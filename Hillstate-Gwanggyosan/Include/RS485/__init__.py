import os
import sys
CURPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.extend([CURPATH])
sys.path = list(set(sys.path))
del CURPATH

from RS485Comm import RS485Comm, RS485Config, RS485HwType
from PacketParser import PacketParser, ParserType
