import json
import datetime
import requests
import bs4
from bs4 import BeautifulSoup
from Device import *
from Common import writeLog
from packaging.version import Version
if (Version(bs4.__version__) >= Version("4.11.0")):
    from bs4 import XMLParsedAsHTMLWarning
    import warnings
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


class WeatherStation(Device):
    """
    공공데이터포털 - 기상청 단기예보 조회서비스
    url: https://www.data.go.kr/data/15084084/openapi.do#tab_layer_detail_function
    """
    _api_key: str = ''
    _coord_x: int = 0
    _coord_y: int = 0
    _last_query_time: datetime.datetime = None

    def __init__(self, name="Weather Station", index: int = 0, room_index: int = 0, topic_prefix: str = "home"):
        super().__init__(name, index, room_index, topic_prefix)
        self.dev_type = DeviceType.WEATHERSTATION
        self.unique_id = f"weather_station_{self.room_index}_{self.index}"
        self.mqtt_state_topic = f'{topic_prefix}/state/weatherstation/{self.room_index}/{self.index}'
        self.mqtt_command_topic = f'{topic_prefix}/command/weatherstation/{self.room_index}/{self.index}'
        self._measure_data = {
            "temperature": 0.0,
            "relative_humidity": 0.0,
            "weather_condition": 0,
            "wind_direction": 0,
            "wind_speed": 0.0,
            "rain_1h": 0.0
        }
    
    def setDefaultName(self):
        self.name = "Weather Station"
    
    def setApiParams(self, api_key: str, coord_x: int, coord_y: int):
        self._api_key = api_key
        self._coord_x = coord_x
        self._coord_y = coord_y

    def refreshData(self):
        """
        getUltraSrtNcst: 초단기실황조회
        getUltraSrtFcst: 초단기예보조회
        getVilageFcst: 단기예보조회
        """
        call_api: bool = False
        now = datetime.datetime.now()
        if self._last_query_time is None:
            call_api = True
        else:
            if now.hour != self._last_query_time.hour and now.minute > 10:
                call_api = True
        
        if call_api:
            url_base = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
            url_spec = "getUltraSrtNcst"
            url = url_base + "/" + url_spec
            api_key_decode = requests.utils.unquote(self._api_key, encoding='utf-8')
            params = {
                "serviceKey": api_key_decode,
                "pageNo": 1,
                "numOfRows": 10,
                "dataType": "XML",
                "base_date": now.strftime("%Y%m%d"),
                "base_time": now.strftime("%H00"),
                "nx": self._coord_x,
                "ny": self._coord_y
            }
            try:
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    xml = BeautifulSoup(response.text.replace('\n', ''), "lxml")
                    result_code = xml.find('resultcode')
                    result_msg = xml.find('resultmsg')
                    if result_code is not None and result_msg is not None:
                        result_code_text = result_code.text
                        result_msg_text = result_msg.text
                        if result_code_text in ['00', '200']:
                            items = xml.find_all("item")
                            for item in items:
                                category = item.find("category").text
                                obsrvalue = item.find("obsrvalue").text
                                # print(category, obsrvalue)
                                if category == "T1H":  # 기온, 단위=℃
                                    try:
                                        self._measure_data['temperature'] = float(obsrvalue)
                                    except ValueError as e:
                                        writeLog(f"parse error ({e})", self)
                                        self._measure_data['temperature'] = 0.0
                                elif category == "RN1":  # 1시간 강수량, 단위=mm
                                    """
                                    "1mm 미만": 0.1 ~ 1.0mm 미만
                                    "실수값+mm" (1.0mm~29.9mm): 1.0mm 이상 30.0mm 미만
                                    "30.0~50.0mm": 30.0 mm 이상 50.0 mm 미만
                                    "50.0mm 이상": 50.0 mm 이상                                    
                                    -, null, 0값은 ‘강수없음’
                                    """
                                    # 'rain_1h'
                                    pass
                                elif category == "UUU":  # 동서바람성분, 단위=m/s
                                    pass
                                elif category == "VVV":  # 남북바람성분, 단위=m/s
                                    pass
                                elif category == "REH":  # 습도, 단위=%
                                    try:
                                        self._measure_data['relative_humidity'] = float(obsrvalue)
                                    except ValueError:
                                        self._measure_data['relative_humidity'] = 0.0
                                elif category == "PTY":  # 강수형태
                                    # 없음(0), 비(1), 비/눈(2), 눈(3), 빗방울(5), 빗방울눈날림(6), 눈날림(7)
                                    pass
                                elif category == "VEC":  # 풍향, 단위=deg
                                    pass
                                elif category == "WSD":  # 풍속, 단위=m/s
                                    try:
                                        self._measure_data['wind_speed'] = float(obsrvalue)
                                    except ValueError:
                                        self._measure_data['wind_speed'] = 0.0
                                else:
                                    writeLog(f"Unknown category <{category}>...", self)
                            self._last_query_time = now
                        else:
                            writeLog(f"API Error ({result_code_text, result_msg_text})", self)
                    else:
                        writeLog(f"API Error (xml parsing error {xml.text})", self)
                else:
                    writeLog(f"Request GET Error ({response.status_code})", self)
            except requests.exceptions.ConnectionError as e:
                writeLog(f'{e}', self)
            except Exception as e:
                writeLog(f'{e}', self)
    
    def publishMQTT(self):
        try:
            self.refreshData()
            obj = {
                "temperature": self._measure_data.get('temperature'),
                "relative_humidity": self._measure_data.get('relative_humidity'),
                "weather_condition": self._measure_data.get('weather_condition'),
                "wind_direction": self._measure_data.get('wind_direction'),
                "wind_speed": self._measure_data.get('wind_speed'),
                "rain_1h": self._measure_data.get('rain_1h')
            }
            if self.mqtt_client is not None:
                self.mqtt_client.publish(self.mqtt_state_topic, json.dumps(obj), 1)
        except Exception:
            pass
    
    def configMQTT(self, retain: bool = False):
        # add homebridge accessory
        hb_config = self.read_homebridge_config_template()
        accessories = hb_config.get('accessories')
        find = list(filter(lambda x: x.get('name') == self.name, accessories))
        if len(find) > 0:
            return
        
        elem = {
            "name": self.name,
            "accessory": "mqttthing",
            "type": "weatherStation",
            "url": f"{self.mqtt_host}:{self.mqtt_port}",
            "username": self.mqtt_username,
            "password": self.mqtt_password,
            "history": True,
            "logMqtt": False,
            "topics": {
                "getCurrentTemperature": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).temperature;"
                },
                "getCurrentRelativeHumidity": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).relative_humidity;"
                },
                "getWeatherCondition": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).weather_condition;"
                },
                "getWindDirection": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).wind_direction;"
                },
                "getWindSpeed": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).wind_speed;"
                },
                "getRain1h": {
                    "topic": self.mqtt_state_topic,
                    "apply": "return JSON.parse(message).rain_1h;"
                }
            }
        }
        accessories.append(elem)
        
        self.write_homebridge_config_template(hb_config)
