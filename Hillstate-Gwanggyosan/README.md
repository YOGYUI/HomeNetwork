# YOGYUI Home Network: Hillstate-Gwanggyosan

Summary
---
Integrate **Hillstate Home Network** to **Apple HomeKit** and **Google Assistant**.<br>

<img src="./summary.png" width="100%">

<br>

Developer's Comments
---
I only tested this code on wallpad model **HDHN-2000**. <br>
If you have a problem adopting this code with other home network environment, please let me know.<br>
E-mail: lee2002w@gmail.com

Install
---
Notice: scripts below are assumed to be run on **Raspberry Pi (with Raspbian OS)** SBC.
1. Clone repository
    ```
    $ mkdir ~/repos
    $ cd ~/repos
    $ git clone https://github.com/YOGYUI/HomeNetwork.git
    $ cd HomeNetwork/Hillstate-Gwanggyosan
    ```
2. Install python3 requirements
    ```
    $ sudo pip3 install -r requirements.txt
    ```

Configuration
---
All configurations needed to run application properly are stored in 
[config.xml](https://github.com/YOGYUI/HomeNetwork/blob/main/Hillstate-Gwanggyosan/config.xml) 
file. <br>
1. RS-485 to UART Converter 
    - Common
        ```xml
        <rs485>
            <port>
                <name>port name</name>
                <index>0</index>
                <enable>1</enable>
                <packettype>0</packettype>
            </port>
        </rs485>
        ```
        - name: unique string to distinguish from other ports.
        - index: unique number (zero based) for mapping port with device. <br>
            Minimum index value shoud be **0**. <br>
            See **4. Parser Mapping** also.
        - enable: 1=enable this port, 0=disable this port.
        - packettype: 0=regular, 1=kitchen subphone
    - RS-485 to USB converter <br>
        **hwtype** should be **0**
        ```xml
        <rs485>
            <port>
                <hwtype>0</hwtype>
                <usb2serial>
                    <port>/dev/ttyUSB0</port>
                    <baud>9600</baud>
                    <databit>8</databit>
                    <parity>N</parity>
                    <stopbits>1</stopbits>
                </usb2serial>
            </port>
        <rs485>
        ```
        ⚠️ kitchen subphone setting
        - baud: 3840
        - databit: 8
        - parity: E
        - stopbits: 1
    - Wireless (TCP based) RS-485 converter (like EW11) <br>
        **hwtype** should be **1**
        ```xml
        <rs485>
            <port>
                <hwtype>1</hwtype>
                <ew11>
                    <ipaddr>192.168.0.2</ipaddr>
                    <port>8899</port>
                </ew11>
            </port>
        <rs485>
        ```
        - ipaddr: ip address or dns for ew11
        - port: port number for ew11
1. MQTT Broker (like Mosquitto) Configuration
    ```xml
    <config>
        <mqtt>
            <host>...</host>
            <port>...</port>
            <username>...</username>
            <password>...</password>
        </mqtt>
    </config>
    ```
    - host: MQTT broker address <br>
        - if mosquitto is running on same SBC, **127.0.0.1** or **0.0.0.0** can be used.
    - port: MQTT broker port
    - username: MQTT broker authentication id
    - password: MQTT broker authentication password

    ❗If advanced authentication method (like SSL/TLS) is required, please tell me.
1. Device Configuration <br>
    MQTT topics to get/set control should be carefully modified in this section. <br>
    These topics should be matched to your home network platform's(like homebridge, homeassistant) configuration. <br>
    ```xml
    <config>
        <device>
            <entry>
                <dev_type>
                    <name>Device Name</name>
                    <index>Device Index</index>
                    <room>Room Index</room>
                    <enable>1</enable>
                    <!--
                    <mqtt>
                        <publish>home/state/dev_type/room_index/dev_index</publish>
                        <subscribe>home/command/dev_type/1room_index/dev_index</subscribe>
                    </mqtt>
                    -->
                </dev_type>
                <dev_type>
                    <!-- ... -->
                </dev_type>
            </entry>
        </device>
    </config>
    ```
    - Supported 'dev_type': light, outlet, thermostat, airconditioner, gasvalve, ventilator, elevator, subphone, hems, batchoffsw
    - 'index' and 'room' tag value is **0-based** integer. <br>
    - 'enable' tag means whether or not add this device. (1=enable, 2=disable)
    - MQTT topic is automatically assigned when device is created. <br>
      If you want to customize topic, uncomment and modify pub/sub topic.<br>
      **publish** topic means updating current state **to** home network accessories. <br>
      **subscribe** topic means receiving state changing command **from** home network platform. <br>
    - You can find other optional tags for various device types in xml file in repository. Please take a look for a moment before building your own environment.
1. **Parser Mapping**
    ```xml
    <config>
        <device>
            <parser_mapping>
                <light>0</light>
                <outlet>0</outlet>
                <gasvalve>1</gasvalve>
                <thermostat>1</thermostat>
                <ventilator>1</ventilator>
                <airconditioner>1</airconditioner>
                <elevator>1</elevator>
                <subphone>2</subphone>
                <batchoffsw>1</batchoffsw>
                <hems>2</hems>
            </parser_mapping>
        </device>
    </config>
    ```
    Index(number) which is configured in **rs485** tag should be matched to related devices. <br>
    Script example above means that **'Light'** related RS-485 packets are streaming on index 0 converter and **'Gas Valve'** related packets are streaming on index 1 converter.<br>
    If you are using only one converter, these values should be all set to 0.

Run Application
---
- native python 
    ```
    $ /bin/python3 ~/repos/HomeNetwork/Hillstate-Gwanggyosan/app.py
    ```
- Nginx & uWSGI environment
    ```
    $ /usr/local/bin/uwsgi ~/repos/HomeNetwork/Hillstate-Gwanggyosan/uwsgi.ini
    ```

Homebridge & Home Assistant 
---
You can find home IoT platform configuration template (json for homebridge, yaml for HA) is this repository. 
- Homebridge: [homebridge_config.json](https://github.com/YOGYUI/HomeNetwork/blob/main/Hillstate-Gwanggyosan/Template/homebridge/homebridge_config.json) 
- Home Assistant: [ha_configuration.yaml](https://github.com/YOGYUI/HomeNetwork/blob/main/Hillstate-Gwanggyosan/Template/homeassistant/ha_configuration.yaml) 


Reference URLs
---
- Illumination: [힐스테이트 광교산::조명 제어 RS-485 패킷 분석](https://yogyui.tistory.com/entry/%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8-%EA%B4%91%EA%B5%90%EC%82%B0%EC%A1%B0%EB%AA%85-%EC%95%A0%ED%94%8C-%ED%99%88%ED%82%B7-%EA%B5%AC%EA%B8%80-%EC%96%B4%EC%8B%9C%EC%8A%A4%ED%84%B4%ED%8A%B8-%EC%97%B0%EB%8F%99?category=1047622) <br>
- Outlet: [힐스테이트 광교산::아울렛(콘센트) - 애플 홈킷 + 구글 어시스턴트 연동](https://yogyui.tistory.com/entry/%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8-%EA%B4%91%EA%B5%90%EC%82%B0%EC%BD%98%EC%84%BC%ED%8A%B8-%EC%A0%9C%EC%96%B4-RS-485-%ED%8C%A8%ED%82%B7-%EB%B6%84%EC%84%9D?category=1047622) <br>
- GasValve: [힐스테이트 광교산::도시가스차단기(밸브) - 애플 홈킷 + 구글 어시스턴트 연동](https://yogyui.tistory.com/entry/%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8-%EA%B4%91%EA%B5%90%EC%82%B0%EA%B0%80%EC%8A%A4%EC%B0%A8%EB%8B%A8%EA%B8%B0-%EC%95%A0%ED%94%8C-%ED%99%88%ED%82%B7-%EA%B5%AC%EA%B8%80-%EC%96%B4%EC%8B%9C%EC%8A%A4%ED%84%B4%ED%8A%B8-%EC%97%B0%EB%8F%99?category=1047622) <br>
- Thermostat: [힐스테이트 광교산::난방 - 애플 홈킷 + 구글 어시스턴트 연동](https://yogyui.tistory.com/entry/%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8-%EA%B4%91%EA%B5%90%EC%82%B0%EB%82%9C%EB%B0%A9-%EC%95%A0%ED%94%8C-%ED%99%88%ED%82%B7-%EA%B5%AC%EA%B8%80-%EC%96%B4%EC%8B%9C%EC%8A%A4%ED%84%B4%ED%8A%B8-%EC%97%B0%EB%8F%99?category=1047622) <br>
- Ventilator: [힐스테이트 광교산::환기(전열교환기) 제어 RS-485 패킷 분석](https://yogyui.tistory.com/entry/%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8-%EA%B4%91%EA%B5%90%EC%82%B0%ED%99%98%EA%B8%B0%EC%A0%84%EC%97%B4%EA%B5%90%ED%99%98%EA%B8%B0-%EC%A0%9C%EC%96%B4-RS-485-%ED%8C%A8%ED%82%B7-%EB%B6%84%EC%84%9D?category=1047622) <br>
- Airconditioner: [힐스테이트 광교산::시스템에어컨 - 애플 홈킷 + 구글 어시스턴트 연동](https://yogyui.tistory.com/entry/%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8-%EA%B4%91%EA%B5%90%EC%82%B0%EC%8B%9C%EC%8A%A4%ED%85%9C%EC%97%90%EC%96%B4%EC%BB%A8-%EC%95%A0%ED%94%8C-%ED%99%88%ED%82%B7-%EA%B5%AC%EA%B8%80-%EC%96%B4%EC%8B%9C%EC%8A%A4%ED%84%B4%ED%8A%B8-%EC%97%B0%EB%8F%99?category=1047622) <br>
- Elevator: [힐스테이트 광교산::엘리베이터 - 애플 홈킷 + 구글 어시스턴트 연동](https://yogyui.tistory.com/entry/%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8-%EA%B4%91%EA%B5%90%EC%82%B0%EC%97%98%EB%A6%AC%EB%B2%A0%EC%9D%B4%ED%84%B0-%EC%95%A0%ED%94%8C-%ED%99%88%ED%82%B7-%EA%B5%AC%EA%B8%80-%EC%96%B4%EC%8B%9C%EC%8A%A4%ED%84%B4%ED%8A%B8-%EC%97%B0%EB%8F%99?category=1047622) <br>
- Doorlock: [힐스테이트 광교산::현관 도어락 - 애플 홈킷 + 구글 어시스턴트 연동](https://yogyui.tistory.com/entry/%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8-%EA%B4%91%EA%B5%90%EC%82%B0%EB%8F%84%EC%96%B4%EB%9D%BD-%EC%95%A0%ED%94%8C-%ED%99%88%ED%82%B7-%EA%B5%AC%EA%B8%80-%EC%96%B4%EC%8B%9C%EC%8A%A4%ED%84%B4%ED%8A%B8-%EC%97%B0%EB%8F%99?category=1047622) <br>
- Kitchen Subphone: [힐스테이트 광교산::주방 비디오폰 연동 - 세대 및 공동 현관문 제어 (애플 홈킷)](https://yogyui.tistory.com/entry/%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8-%EA%B4%91%EA%B5%90%EC%82%B0%EC%A3%BC%EB%B0%A9-%EC%84%9C%EB%B8%8C%ED%8F%B0-%EC%97%B0%EB%8F%99-%ED%98%84%EA%B4%80%EB%AC%B8-%EB%B9%84%EB%94%94%EC%98%A4) <br>
- Batch Off Switch: [힐스테이트 광교산::일괄소등 스위치 RS-485 패킷 분석 및 애플 홈 연동](https://yogyui.tistory.com/entry/%ED%9E%90%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%8A%B8-%EA%B4%91%EA%B5%90%EC%82%B0%EC%9D%BC%EA%B4%84%EC%86%8C%EB%93%B1-%EC%8A%A4%EC%9C%84%EC%B9%98-RS-485-%ED%8C%A8%ED%82%B7-%EB%B6%84%EC%84%9D-%EB%B0%8F-IoT-%EC%97%B0%EB%8F%99) <br>

TODO
---
- Finalize auto detecting device implementation.