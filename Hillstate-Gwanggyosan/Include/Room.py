from typing import List
from Device import Device
from Light import Light
from Outlet import Outlet
from Common import writeLog


class Room:
    name: str = 'Room'
    index: int = 0
    lights: List[Light]
    outlets: List[Outlet]

    def __init__(
        self, name: str = 'Room', 
        index: int = 0, 
        light_count: int = 0, 
        outlet_count: int = 0,
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
        writeLog(f'Room Created >> {self}', self)

    def __repr__(self):
        return f"Room <{self.name}>: Index={self.index}," \
               f" Light#={len(self.lights)}," \
               f" Outlet#={len(self.outlets)}" \

    def getDevices(self) -> List[Device]:
        devices = list()
        devices.extend(self.lights)
        devices.extend(self.outlets)
        return devices

    @property
    def light_count(self):
        return len(self.lights)

    @property
    def outlet_count(self):
        return len(self.outlets)