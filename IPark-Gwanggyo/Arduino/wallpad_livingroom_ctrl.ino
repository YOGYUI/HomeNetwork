#include <ESP8266WiFi.h>
#include <Adafruit_MCP4725.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

char publish_msg[256];
StaticJsonDocument<256> json_doc;

const char* WIFI_SSID = "Your WiFi SSID";
const char* WIFI_PW = "Your WiFi Password";
WiFiClient wifi_client;

const char* MQTT_BROKER_ADDR = "Your MQTT Broker(Mosquitto) IP Address";
const int   MQTT_BROKER_PORT = 1234;  // Your MQTT Broker(Mosquitto) Port
const char* MQTT_ID = "Your MQTT Broker(Mosquitto) Auth ID";
const char* MQTT_PW = "Your MQTT Broker(Mosquitto) Auth Password";
PubSubClient mqtt_client(wifi_client);

const int DAC_RESOLUTION = 12;
const double DAC_VREG = 5.0;
Adafruit_MCP4725 dac;

const int MUX_SEL_PIN = 13;
const int LIGHT1_STATE_PIN = 14;
const int LIGHT2_STATE_PIN = 12;
const int LED1_PIN = 9;
const int LED2_PIN = 10;
int last_state_light1 = -1;
int last_state_light2 = -1;

const int MONITOR_INTERVAL_MS = 250;
long last_monitor_time = 0;

enum MUXOUT {
  WALLPAD = 0,
  DACOUT = 1
};

uint16_t convert_dac_value(double voltage) {
  return uint16_t( (pow(2, DAC_RESOLUTION) - 1) / DAC_VREG * voltage);
}

void setDacOutVoltage(double voltage) {
  uint16_t conv_val = convert_dac_value(voltage);
  Serial.printf("Set DAC Output Voltage: %f V\n", voltage);
  dac.setVoltage(conv_val, false);
}

void setMuxOut(MUXOUT value) {
  if (value == WALLPAD) {
    digitalWrite(MUX_SEL_PIN, LOW);
    Serial.println("MUX OUT >> WALLPAD");
  } else if (value == DACOUT) {
    digitalWrite(MUX_SEL_PIN, HIGH);
    Serial.println("MUX OUT >> DAC OUT");
  }
}

void changeLightState(int index) {
  if (index == 1) {
    setDacOutVoltage(4.0);
  } else if (index == 2) {
    setDacOutVoltage(3.0);
  }
  setMuxOut(DACOUT);
  delay(100);
  setMuxOut(WALLPAD);
  setDacOutVoltage(5.0);
}

void mqtt_callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");
  for (int i = 0; i < length; i++) {
    Serial.print((char)payload[i]);
  }
  Serial.println();

  if (!strcmp(topic, "home/ipark/livingroom/light/command/0")) {
    changeLightState(1);
  } else if(!strcmp(topic, "home/ipark/livingroom/light/command/1")) {
    changeLightState(2);
  }
}

void setup() {
  Serial.begin(115200);
  
  WiFi.begin(WIFI_SSID, WIFI_PW);
  Serial.print("\nWiFi Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  mqtt_client.setServer(MQTT_BROKER_ADDR, MQTT_BROKER_PORT);
  mqtt_client.setCallback(mqtt_callback);

  Serial.print("Connected, IP address: ");
  Serial.println(WiFi.localIP());
  Serial.printf("MAC address = %s\n", WiFi.softAPmacAddress().c_str());

  pinMode(MUX_SEL_PIN, OUTPUT);
  pinMode(LIGHT1_STATE_PIN, INPUT);
  pinMode(LIGHT2_STATE_PIN, INPUT);

  dac.begin(0x60);
  setDacOutVoltage(5.0);
  setMuxOut(WALLPAD);

  readLightStateAll();
  last_monitor_time = millis();
}

void establish_mqtt_connection() {
  if (mqtt_client.connected())
    return;
  while (!mqtt_client.connected()) {
    Serial.println("Try to connect MQTT Broker");
    if (mqtt_client.connect("ESP8266_WALLPAD_LIVINGROOM", MQTT_ID, MQTT_PW)) {
      Serial.println("Connected");
      mqtt_client.subscribe("home/ipark/livingroom/light/command/0");
      mqtt_client.subscribe("home/ipark/livingroom/light/command/1");
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqtt_client.state());
      delay(2000);
    }
  }
}

void readLightState(int index) {
  int state = -1;
  if (index == 1) {
    state = digitalRead(LIGHT1_STATE_PIN);
    if (state != last_state_light1) {
      last_state_light1 = state;
      publishLightState(1);
    }
  } else if (index == 2) {
    state = digitalRead(LIGHT2_STATE_PIN);
    if (state != last_state_light2) {
      last_state_light2 = state;
      publishLightState(2);
    }
  }
}

void readLightStateAll() {
  readLightState(1);
  readLightState(2);
}

void publishLightState(int index) {
  size_t n = 0;
    
  if (index == 1) {
    json_doc["state"] = last_state_light1;
    n = serializeJson(json_doc, publish_msg);
    mqtt_client.publish(
      "home/ipark/livingroom/light/state/0",
      publish_msg,
      n);
    Serial.print("Published (home/ipark/livingroom/light/state/0): ");
    Serial.println(publish_msg);
  } else if (index == 2) {
    json_doc["state"] = last_state_light2;
    n = serializeJson(json_doc, publish_msg);
    mqtt_client.publish(
      "home/ipark/livingroom/light/state/1",
      publish_msg,
      n);
    Serial.print("Published (home/ipark/livingroom/light/state/1): ");
    Serial.println(publish_msg);
  }
}

void loop() {
  establish_mqtt_connection();
  mqtt_client.loop();

  long current = millis();
  if (current - last_monitor_time >= MONITOR_INTERVAL_MS) {
    last_monitor_time = current;
    readLightStateAll();
  }
}