from typing import List, Union
import xml.etree.ElementTree as ET
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

    @staticmethod
    def splitTopicText(text: str) -> List[str]:
        topics = text.split('\n')
        topics = [x.replace(' ', '') for x in topics]
        topics = [x.replace('\t', '') for x in topics]
        topics = list(filter(lambda x: len(x) > 0, topics))
        return topics

    def loadConfig(self, node: ET.Element):
        try:
            room_node = node.find('room{}'.format(self.index))
            if room_node is not None:
                lights_node = room_node.find('lights')
                if lights_node is not None:
                    for j in range(self.light_count):
                        light_node = lights_node.find(f'light{j + 1}')
                        if light_node is not None:
                            self.lights[j].name = light_node.find('name').text
                            mqtt_node = light_node.find('mqtt')
                            self.lights[j].mqtt_publish_topic = mqtt_node.find('publish').text
                            topics = self.splitTopicText(mqtt_node.find('subscribe').text)
                            self.lights[j].mqtt_subscribe_topics.extend(topics)
                outlets_node = room_node.find('outlets')
                if outlets_node is not None:
                    for j in range(self.outlet_count):
                        outlet_node = outlets_node.find(f'outlet{j + 1}')
                        if outlet_node is not None:
                            self.outlets[j].name = outlet_node.find('name').text
                            self.outlets[j].enable_off_command = bool(int(outlet_node.find('enable_off_cmd').text))
                            mqtt_node = outlet_node.find('mqtt')
                            self.outlets[j].mqtt_publish_topic = mqtt_node.find('publish').text
                            topics = self.splitTopicText(mqtt_node.find('subscribe').text)
                            self.outlets[j].mqtt_subscribe_topics.extend(topics)
                thermostat_node = room_node.find('thermostat')
                if thermostat_node is not None:
                    range_min_node = thermostat_node.find('range_min')
                    range_min = int(range_min_node.text)
                    range_max_node = thermostat_node.find('range_max')
                    range_max = int(range_max_node.text)
                    mqtt_node = thermostat_node.find('mqtt')
                    if self.has_thermostat:
                        self.thermostat.setTemperatureRange(range_min, range_max)
                        self.thermostat.mqtt_publish_topic = mqtt_node.find('publish').text
                        topics = self.splitTopicText(mqtt_node.find('subscribe').text)
                        self.thermostat.mqtt_subscribe_topics.extend(topics)
                airconditioner_node = room_node.find('airconditioner')
                if airconditioner_node is not None:
                    range_min_node = airconditioner_node.find('range_min')
                    range_min = int(range_min_node.text)
                    range_max_node = airconditioner_node.find('range_max')
                    range_max = int(range_max_node.text)
                    mqtt_node = airconditioner_node.find('mqtt')
                    if self.has_airconditioner:
                        self.airconditioner.setTemperatureRange(range_min, range_max)
                        self.airconditioner.mqtt_publish_topic = mqtt_node.find('publish').text
                        topics = self.splitTopicText(mqtt_node.find('subscribe').text)
                        self.airconditioner.mqtt_subscribe_topics.extend(topics)
            else:
                writeLog(f"Failed to find room{self.index} node", self)        
        except Exception as e:
            writeLog(f"Failed to load config ({e})", self)

    @property
    def light_count(self):
        return len(self.lights)

    @property
    def outlet_count(self):
        return len(self.outlets)
