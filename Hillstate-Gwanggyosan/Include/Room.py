from typing import List
from Device import Device
from Light import Light
from Common import writeLog


class Room:
    name: str = 'Room'
    index: int = 0
    lights: List[Light]

    def __init__(self, name: str = 'Room', index: int = 0, light_count: int = 0, **kwargs):
        self.name = name
        self.index = index
        self.lights = list()

        for i in range(light_count):
            self.lights.append(Light(
                name=f'Light {i + 1}',
                index=i,
                room_index=self.index,
                mqtt_client=kwargs.get('mqtt_client')
            ))
        writeLog(f'Room Created >> {self}', self)

    def __repr__(self):
        return f"Room <{self.name}>: Index={self.index}," \
               f" Light#={len(self.lights)}"

    def getDevices(self) -> List[Device]:
        devices = list()
        devices.extend(self.lights)
        return devices

    @property
    def light_count(self):
        return len(self.lights)
