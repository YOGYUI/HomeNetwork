from typing import List, Union
from Define import *
from Common import writeLog


class Room:
    name: str = 'Room'
    index: int = 0
    lights: List[Light]
    outlets: List[Outlet]
    has_thermostat: bool = False
    thermostat: Union[Thermostat, None] = None
    has_airconditioner: bool = False
    airconditioner: Union[AirConditioner, None] = None

    def __init__(
        self, name: str = 'Room', 
        index: int = 0, 
        light_count: int = 0, 
        outlet_count: int = 0,
        has_thermostat: bool = False,
        has_airconditioner: bool = False,
        **kwargs
    ):
        self.name = name
        self.index = index
        self.lights = list()
        self.outlets = list()

        for i in range(light_count):
            self.lights.append(Light(
                name=f'Light {i + 1}',
                index=i,
                room_index=self.index,
                mqtt_client=kwargs.get('mqtt_client')
            ))
        for i in range(outlet_count):
            self.outlets.append(Outlet(
                name=f'Outlet {i + 1}',
                index=i,
                room_index=self.index,
                mqtt_client=kwargs.get('mqtt_client')
            ))
        self.has_thermostat = has_thermostat
        if self.has_thermostat:
            self.thermostat = Thermostat(
                name=f'Thermostat',
                room_index=self.index, 
                mqtt_client=kwargs.get('mqtt_client')
            )
        self.has_airconditioner = has_airconditioner
        if self.has_airconditioner:
            self.airconditioner = AirConditioner(
                name=f'AirConditioner',
                room_index=self.index,
                mqtt_client=kwargs.get('mqtt_client')
            )
        writeLog(f'Room Created >> {self}', self)

    def __repr__(self):
        return f"Room <{self.name}>: Index={self.index}," \
               f" Light#={len(self.lights)}," \
               f" Outlet#={len(self.outlets)}," \
               f" Thermostat={self.has_thermostat}," \
               f" AirConditioner={self.has_airconditioner}" \

    def getDevices(self) -> List[Device]:
        devices = list()
        devices.extend(self.lights)
        devices.extend(self.outlets)
        if self.has_thermostat:
            devices.append(self.thermostat)
        if self.has_airconditioner:
            devices.append(self.airconditioner)
        return devices

    @property
    def light_count(self):
        return len(self.lights)

    @property
    def outlet_count(self):
        return len(self.outlets)
