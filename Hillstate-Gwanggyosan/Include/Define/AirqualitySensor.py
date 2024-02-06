import json
import datetime
import requests
from bs4 import BeautifulSoup
from Device import Device
from Common import writeLog


class AirqualitySensor(Device):
    """
    공공데이터포털 - 대기오염정보
    """
    _api_key: str = ''
    _obs_name: str = ''
    _last_query_time: datetime.datetime = None

    def __init__(self, name: str = 'Airquality', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.unique_id = f'airquality_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/airquality/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/airquality/{self.room_index}/{self.index}'
        self._measure_data = {
            'khaiGrade': -1,
            'so2Value': 0.0,
            'coValue': 0.0,
            'o3Value': 0.0,
            'no2Value': 0.0,
            'pm10Value': 0.0,
            'pm25Value': 0.0,
        }
    
    def setDefaultName(self):
        self.name = 'Airquality'

    def setApiParams(self, api_key: str, obs_name: str):
        self._api_key = api_key
        self._obs_name = obs_name

    def refreshData(self):
        if self._last_query_time is None:
            call_api = True
        else:
            tmdiff = datetime.datetime.now() - self._last_query_time
            if tmdiff.seconds > 3600:
                call_api = True
            else:
                call_api = False

        if call_api:
            url_base = "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc"
            url_spec = "getMsrstnAcctoRltmMesureDnsty"
            url = url_base + "/" + url_spec
            api_key_decode = requests.utils.unquote(self._api_key, encoding='utf-8')
            params = {
                "serviceKey": api_key_decode,
                "returnType": "xml",
                "stationName": self._obs_name,
                "dataTerm": "DAILY",
                "ver": "1.3",
                "numOfRows": 1,
                "pageNo": 1
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
                            items = xml.findAll("item")
                            if len(list(items)) >= 1:
                                item = items[0]
                                # 점검 및 교정 혹은 '-' 텍스트가 기록될 수 있다
                                self._measure_data['dataTime'] = item.find('dataTime'.lower()).text
                                try:
                                    self._measure_data['so2Value'] = float(item.find('so2Value'.lower()).text)
                                except ValueError:
                                    self._measure_data['so2Value'] = 0.0
                                try:
                                    self._measure_data['coValue'] = float(item.find('coValue'.lower()).text)
                                except ValueError:
                                    self._measure_data['coValue'] = 0.0
                                try:
                                    self._measure_data['o3Value'] = float(item.find('o3Value'.lower()).text)
                                except ValueError:
                                    self._measure_data['o3Value'] = 0.0
                                try:
                                    self._measure_data['no2Value'] = float(item.find('no2Value'.lower()).text)
                                except ValueError:
                                    self._measure_data['no2Value'] = 0.0
                                try:
                                    self._measure_data['pm10Value'] = float(item.find('pm10Value'.lower()).text)
                                except ValueError:
                                    self._measure_data['pm10Value'] = 0.0
                                try:
                                    self._measure_data['pm25Value'] = float(item.find('pm25Value'.lower()).text)
                                except ValueError:
                                    self._measure_data['pm25Value'] = 0.0
                                try:
                                    self._measure_data['khaiValue'] = float(item.find('khaiValue'.lower()).text)
                                except ValueError:
                                    self._measure_data['khaiValue'] = 0.0
                                try:
                                    self._measure_data['khaiGrade'] = int(item.find('khaiGrade'.lower()).text)
                                except ValueError:
                                    self._measure_data['khaiGrade'] = 0
                                self._last_query_time = datetime.datetime.now()
                            else:
                                writeLog(f"Cannot find 'item' node", self)
                        else:
                            writeLog(f"API Error ({result_code_text, result_msg_text})", self)
                    else:
                        writeLog(f"API Error (xml parsing error {xml.text})", self)
                else:
                    writeLog(f"Request GET Error ({response.status_code})", self)
            except requests.exceptions.ConnectionError as e:
                writeLog(f'{e}', self)

    def publishMQTT(self):
        try:
            self.refreshData()
            obj = {
                "grade": self._measure_data.get('khaiGrade'),
                "so2": self._measure_data.get('so2Value'),
                "co": self._measure_data.get('coValue'),
                "o3": self._measure_data.get('o3Value'),
                "no2": self._measure_data.get('no2Value'),
                "pm10": self._measure_data.get('pm10Value'),
                "pm25": self._measure_data.get('pm25Value')
            }
            if self.mqtt_client is not None:
                self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
        except Exception:
            pass

    def configMQTT(self, retain: bool = False):
        pass