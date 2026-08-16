#include <DHT.h>
#include "Adafruit_PM25AQI.h"

const int BOARD_ID = 4;
const int CELL_START = 18;

const int DHTPins[6]      = {22, 24, 26, 28, 30, 32};
const int moisturePins[6] = {A8, A9, A10, A11, A12, A13};
const int relayPins[6]    = {23, 25, 27, 29, 31, 33};
const int solenoidPins[6] = {34, 15, 16, 17, 18, 19};
const int redPins[6]      = {2,  5,  8,  11, 44, 47};
const int greenPins[6]    = {3,  6,  9,  12, 45, 48};
const int bluePins[6]     = {4,  7,  10, 13, 46, 49};

const int photocellPin = A3;

const int DRY_THRESHOLD  = 215;
const int WET_THRESHOLD  = 730;
const int LIGHT_MIN      = 980;
const int LIGHT_MAX      = 1023;
const int FAN_ON_TEMP    = 28;
const int FAN_OFF_TEMP   = 25;

DHT DHTs[6] = {
  DHT(22, DHT11), DHT(24, DHT11), DHT(26, DHT11),
  DHT(28, DHT11), DHT(30, DHT11), DHT(32, DHT11)
};

Adafruit_PM25AQI aqi = Adafruit_PM25AQI();

float temperatures[6];
float humidities[6];
int moistureValues[6];
bool fanState[6] = {false, false, false, false, false, false};
bool breatheActive = false;
bool manualFanOverride = false;
bool manualLedOverride = false;

unsigned long lastDHTRead  = 0;
unsigned long lastSend     = 0;
unsigned long lastBreathe  = 0;
int dhtIndex = 0;
int breatheVal = 0;
int breatheDir = 1;

void setLEDColor(int i, int r, int g, int b) {
  digitalWrite(redPins[i],   r);
  digitalWrite(greenPins[i], g);
  digitalWrite(bluePins[i],  b);
}

void updateFans() {
  if (manualFanOverride) return;
  for (int i = 0; i < 6; i++) {
    if (temperatures[i] > 10 && temperatures[i] < 50) {
      if (!fanState[i] && temperatures[i] > FAN_ON_TEMP) {
        fanState[i] = true;
        digitalWrite(relayPins[i], HIGH);
      } else if (fanState[i] && temperatures[i] < FAN_OFF_TEMP) {
        fanState[i] = false;
        digitalWrite(relayPins[i], LOW);
      }
    }
    delay(50);
  }
}

void updateBreathe() {
  if (!breatheActive) return;
  unsigned long now = millis();
  if (now - lastBreathe < 10) return;
  lastBreathe = now;
  breatheVal += breatheDir * 3;
  if (breatheVal >= 255) { breatheVal = 255; breatheDir = -1; }
  if (breatheVal <= 0)   { breatheVal = 0;   breatheDir = 1;  }
  for (int i = 0; i < 6; i++) {
    analogWrite(redPins[i],  0);
    analogWrite(bluePins[i], 0);
    if (greenPins[i] == 48) {
      digitalWrite(greenPins[i], breatheVal > 127 ? HIGH : LOW);
    } else {
      analogWrite(greenPins[i], breatheVal);
    }
  }
}

void handleCommand(String cmd) {
  cmd.trim();
  if (cmd == "AUTO_MODE") {
    manualFanOverride = false;
    manualLedOverride = false;
  } else if (cmd == "MANUAL_MODE") {
    manualFanOverride = true;
    manualLedOverride = true;
  } else if (cmd.startsWith("SOL_ON_")) {
    int idx = cmd.substring(7).toInt() - 1;
    if (idx >= 0 && idx < 6) digitalWrite(solenoidPins[idx], HIGH);
  } else if (cmd.startsWith("SOL_OFF_")) {
    int idx = cmd.substring(8).toInt() - 1;
    if (idx >= 0 && idx < 6) digitalWrite(solenoidPins[idx], LOW);
  } else if (cmd == "ALL_SOL_OFF") {
    for (int i = 0; i < 6; i++) digitalWrite(solenoidPins[i], LOW);
  } else if (cmd.startsWith("FAN_ON_")) {
    int idx = cmd.substring(7).toInt() - 1;
    if (idx >= 0 && idx < 6) { fanState[idx] = true; digitalWrite(relayPins[idx], HIGH); }
  } else if (cmd.startsWith("FAN_OFF_")) {
    int idx = cmd.substring(8).toInt() - 1;
    if (idx >= 0 && idx < 6) { fanState[idx] = false; digitalWrite(relayPins[idx], LOW); }
  } else if (cmd == "ALL_FAN_ON") {
    for (int i = 0; i < 6; i++) { fanState[i] = true; digitalWrite(relayPins[i], HIGH); }
  } else if (cmd == "ALL_FAN_OFF") {
    for (int i = 0; i < 6; i++) { fanState[i] = false; digitalWrite(relayPins[i], LOW); }
  } else if (cmd.startsWith("LED_R_")) {
    breatheActive = false;
    int idx = cmd.substring(6).toInt() - 1;
    if (idx >= 0 && idx < 6) setLEDColor(idx, HIGH, LOW, LOW);
  } else if (cmd.startsWith("LED_G_")) {
    breatheActive = false;
    int idx = cmd.substring(6).toInt() - 1;
    if (idx >= 0 && idx < 6) setLEDColor(idx, LOW, HIGH, LOW);
  } else if (cmd.startsWith("LED_B_")) {
    breatheActive = false;
    int idx = cmd.substring(6).toInt() - 1;
    if (idx >= 0 && idx < 6) setLEDColor(idx, LOW, LOW, HIGH);
  } else if (cmd.startsWith("LED_W_")) {
    breatheActive = false;
    int idx = cmd.substring(6).toInt() - 1;
    if (idx >= 0 && idx < 6) setLEDColor(idx, HIGH, HIGH, HIGH);
  } else if (cmd.startsWith("LED_OFF_")) {
    breatheActive = false;
    int idx = cmd.substring(8).toInt() - 1;
    if (idx >= 0 && idx < 6) setLEDColor(idx, LOW, LOW, LOW);
  } else if (cmd == "ALL_LED_R") {
    breatheActive = false;
    for (int i = 0; i < 6; i++) setLEDColor(i, HIGH, LOW, LOW);
  } else if (cmd == "ALL_LED_G") {
    breatheActive = false;
    for (int i = 0; i < 6; i++) setLEDColor(i, LOW, HIGH, LOW);
  } else if (cmd == "ALL_LED_B") {
    breatheActive = false;
    for (int i = 0; i < 6; i++) setLEDColor(i, LOW, LOW, HIGH);
  } else if (cmd == "ALL_LED_W") {
    breatheActive = false;
    for (int i = 0; i < 6; i++) setLEDColor(i, HIGH, HIGH, HIGH);
  } else if (cmd == "ALL_LED_OFF") {
    breatheActive = false;
    for (int i = 0; i < 6; i++) setLEDColor(i, LOW, LOW, LOW);
  } else if (cmd == "BREATHE_GREEN") {
    breatheActive = true; breatheVal = 0; breatheDir = 1;
  } else if (cmd == "BREATHE_STOP") {
    breatheActive = false;
    for (int i = 0; i < 6; i++) setLEDColor(i, LOW, LOW, LOW);
  }
}

void sendPacket(int light, uint16_t aqiVal) {
  Serial.print("{\"board_id\":"); Serial.print(BOARD_ID);
  Serial.print(",\"cells\":[");
  for (int i = 0; i < 6; i++) {
    Serial.print("{\"cell\":"); Serial.print(CELL_START + i + 1);
    Serial.print(",\"temp\":"); Serial.print(temperatures[i]);
    Serial.print(",\"hum\":"); Serial.print(humidities[i]);
    Serial.print(",\"moist\":"); Serial.print(moistureValues[i]);
    Serial.print("}");
    if (i < 5) Serial.print(",");
  }
  Serial.print("],\"light\":"); Serial.print(light);
  Serial.print(",\"aqi\":"); Serial.print(aqiVal);
  Serial.print(",\"pump\":0");
  Serial.println("}");
}

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < 6; i++) {
    digitalWrite(relayPins[i], LOW);
    digitalWrite(solenoidPins[i], LOW);
    pinMode(redPins[i], OUTPUT);
    pinMode(greenPins[i], OUTPUT);
    pinMode(bluePins[i], OUTPUT);
    pinMode(relayPins[i], OUTPUT);
    pinMode(solenoidPins[i], OUTPUT);
    DHTs[i].begin();
    delay(50);
  }
  aqi.begin_I2C();
  manualFanOverride = false;
  manualLedOverride = false;
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    handleCommand(cmd);
  }
  unsigned long now = millis();
  if (now - lastDHTRead >= 1000) {
    lastDHTRead = now;
    float t = DHTs[dhtIndex].readTemperature();
    float h = DHTs[dhtIndex].readHumidity();
    if (!isnan(t) && !isnan(h)) {
      temperatures[dhtIndex] = t;
      humidities[dhtIndex]   = h;
    } else {
      temperatures[dhtIndex] = 0;
      humidities[dhtIndex]   = 0;
    }
    dhtIndex = (dhtIndex + 1) % 6;
    updateFans();
  }
  for (int i = 0; i < 6; i++) {
    moistureValues[i] = analogRead(moisturePins[i]);
    if (!manualLedOverride) {
      if (moistureValues[i] > 1000) {
        moistureValues[i] = -1;
        setLEDColor(i, LOW, LOW, LOW);
      } else if (moistureValues[i] < DRY_THRESHOLD) {
        setLEDColor(i, HIGH, LOW, LOW);
      } else if (moistureValues[i] > WET_THRESHOLD) {
        setLEDColor(i, LOW, LOW, HIGH);
      } else {
        setLEDColor(i, LOW, HIGH, LOW);
      }
    }
  }
  updateBreathe();
  if (now - lastSend >= 3000) {
    lastSend = now;
    int lightRaw = analogRead(photocellPin);
    int light = constrain(map(lightRaw, LIGHT_MIN, LIGHT_MAX, 0, 100), 0, 100);
    uint16_t aqiVal = 0;
    PM25_AQI_Data data;
    if (aqi.read(&data)) aqiVal = data.aqi_pm25_us;
    sendPacket(light, aqiVal);
  }
}
