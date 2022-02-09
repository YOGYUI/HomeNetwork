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

    def __init__(self, **kwargs):
        self._measure_data = {
            'khaiGrade': -1,
            'so2Value': 0.0,
            'coValue': 0.0,
            'o3Value': 0.0,
            'no2Value': 0.0,
            'pm10Value': 0.0,
            'pm25Value': 0.0,
        }
        super().__init__('Airquality', **kwargs)

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
            response = requests.get(url, params=params)
            if response.status_code == 200:
                xml = BeautifulSoup(response.text.replace('\n', ''), "lxml")
                result_code = xml.find('resultcode')
                result_msg = xml.find('resultmsg')
                if result_code is not None and result_msg is not None:
                    result_code_text = result_code.text
                    result_msg_text = result_msg.text
                    if result_code_text == '00':
                        items = xml.findAll("item")
                        if len(list(items)) >= 1:
                            item = items[0]
                            self._measure_data['dataTime'] = item.find('dataTime'.lower()).text
                            self._measure_data['so2Value'] = float(item.find('so2Value'.lower()).text)
                            self._measure_data['coValue'] = float(item.find('coValue'.lower()).text)
                            self._measure_data['o3Value'] = float(item.find('o3Value'.lower()).text)
                            self._measure_data['no2Value'] = float(item.find('no2Value'.lower()).text)
                            self._measure_data['pm10Value'] = float(item.find('pm10Value'.lower()).text)
                            self._measure_data['pm25Value'] = float(item.find('pm25Value'.lower()).text)
                            self._measure_data['khaiValue'] = float(item.find('khaiValue'.lower()).text)
                            self._measure_data['khaiGrade'] = int(item.find('khaiGrade'.lower()).text)
                            self._last_query_time = datetime.datetime.now()
                    else:
                        writeLog(f"API Error ({result_code_text, result_msg_text})", self)
                else:
                    writeLog(f"API Error (xml parsing error {xml.text})", self)
            else:
                writeLog(f"Request GET Error ({response.status_code})", self)

    def publish_mqtt(self):
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
