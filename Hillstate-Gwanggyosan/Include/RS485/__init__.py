import os
import sys
CURPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.extend([CURPATH])
sys.path = list(set(sys.path))
del CURPATH

from SerialComm import SerialComm
from SerialParser import SerialParser
from ParserLight import ParserLight