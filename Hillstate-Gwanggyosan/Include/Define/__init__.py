import os
import sys
CURPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.extend([CURPATH])
sys.path = list(set(sys.path))
del CURPATH

from Device import Device
from Light import Light
from Outlet import Outlet
from GasValve import GasValve
from Thermostat import Thermostat
from Ventilator import Ventilator
