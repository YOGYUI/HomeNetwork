Summary
-------------
![summary](./summary.png)

How to run?
-------------
Bash example is written in [run.sh](https://github.com/YOGYUI/HomeNetwork/blob/main/IPark-Gwanggyo/run.sh) <br>
```
/bin/python3 /home/pi/Project/HomeNetwork/IPark-Gwanggyo/app.py
```

Python Requirements
-------------
```
flask
flask_httpauth
werkzeug
paho-mqtt
PyQt5
pyserial
```

Notice
-------------
All accessories of [Homebridge](https://homebridge.io/) are implemented with
[Mqttthing](https://github.com/arachnetech/homebridge-mqttthing#readme) plugin.<br>
You should run [Mosquitto](https://mosquitto.org/), a.k.a. MQTT Broker, in somewhere. <br>
(In my case, homebridge and mosquitto are run in Raspberry-Pi 4 Device) <br>
You can see my Homebridge config file (json format) in
[homebridge_config.json](https://github.com/YOGYUI/HomeNetwork/blob/main/IPark-Gwanggyo/homebridge_config.json). <br><br> 
You should modify 'mqtt' tag in 
[config.xml](https://github.com/YOGYUI/HomeNetwork/blob/main/IPark-Gwanggyo/config.xml). <br>
```
<homenetworkserver>
    <mqtt>
        <host>...</host>
        <port>...</port>
        <username>...</username>
        <password>...</password>
    </mqtt>
```
* host: Mosquitto Ip Address 
* port: Mosquitto Port
* username: Mosquitto Authentication ID 
* password: Mosquitto Authentication Password

Reference URLs
-------------
I recommend you to read developer's notes in my blog.<br><br>
Illumination: [광교아이파크::조명 Apple 홈킷 연동](https://yogyui.tistory.com/entry/%EA%B4%91%EA%B5%90%EC%95%84%EC%9D%B4%ED%8C%8C%ED%81%AC-%EC%A1%B0%EB%AA%85-%ED%99%88%ED%82%B7-%EC%97%B0%EB%8F%99-1?category=937615) <br>
Thermostat: [광교아이파크::난방 Apple 홈킷 연동](https://yogyui.tistory.com/entry/%EA%B4%91%EA%B5%90%EC%95%84%EC%9D%B4%ED%8C%8C%ED%81%AC-%EB%82%9C%EB%B0%A9-%ED%99%88%ED%82%B7-%EC%97%B0%EB%8F%99-1?category=937615) <br>
Ventilator: [광교아이파크::환기(전열교환기) Apple 홈킷 연동](https://yogyui.tistory.com/entry/%EA%B4%91%EA%B5%90%EC%95%84%EC%9D%B4%ED%8C%8C%ED%81%AC-%ED%99%98%EA%B8%B0-%ED%99%88%ED%82%B7-%EC%97%B0%EB%8F%99-1?category=937615) <br>
Gas: [광교아이파크::가스 Apple 홈킷 연동](https://yogyui.tistory.com/entry/%EA%B4%91%EA%B5%90%EC%95%84%EC%9D%B4%ED%8C%8C%ED%81%AC-%EA%B0%80%EC%8A%A4-%ED%99%88%ED%82%B7-%EC%97%B0%EB%8F%99-2?category=937615) <br>
Elevator: [광교아이파크::엘리베이터 Apple 홈킷 연동](https://yogyui.tistory.com/entry/%EA%B4%91%EA%B5%90%EC%95%84%EC%9D%B4%ED%8C%8C%ED%81%AC-%EC%97%98%EB%A6%AC%EB%B2%A0%EC%9D%B4%ED%84%B0-%ED%99%88%ED%82%B7-%EC%97%B0%EB%8F%99-1-2?category=937615) <br>
Livingroom Illumination: [광교아이파크::거실 조명 Apple 홈킷 연동](https://yogyui.tistory.com/entry/%EA%B4%91%EA%B5%90%EC%95%84%EC%9D%B4%ED%8C%8C%ED%81%AC%EA%B1%B0%EC%8B%A4-%EC%A1%B0%EB%AA%85-Apple-%ED%99%88%ED%82%B7-%EC%97%B0%EB%8F%99-1?category=937615) <br>
Outlet: [광교아이파크::전원콘센트 Apple 홈킷 연동](https://yogyui.tistory.com/entry/%EA%B4%91%EA%B5%90%EC%95%84%EC%9D%B4%ED%8C%8C%ED%81%AC%EC%A0%84%EC%9B%90%EC%BD%98%EC%84%BC%ED%8A%B8-Apple-%ED%99%88%ED%82%B7-%EC%97%B0%EB%8F%99-1?category=937615) <br>
