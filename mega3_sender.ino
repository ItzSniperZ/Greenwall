#include <dht.h>
#include "Adafruit_PM25AQI.h"

const int BOARD_ID = 3;
const int CELL_START = 12;

const int DHTPins[6] = {20, 21, 22, 23, 24, 25};
const int moisturePins[6] = {14, 15, 16, 17, 18, 19};
const int relayPins[6] = {26, 27, 28, 29, 30, 31};
const int redPins[6] = {2, 5, 8, 11, 44, 47};
const int greenPins[6] = {3, 6, 9, 12, 45, 48};
const int bluePins[6] = {4, 7, 10, 13, 46, 49};

const int waterPumpPin = 50;
const int pumpButtonPin = 52;
const int photocellPin = A3;

const int DRY_THRESHOLD = 850;
const int WET_THRESHOLD = 350;

Adafruit_PM25AQI aqi = Adafruit_PM25AQI();
dht DHTs[6];

int temperatures[6];
int humidities[6];
int moistureValues[6];

bool pumpToggleState = false;
int lastButtonReading = HIGH;
int stableButtonState = HIGH;
unsigned long lastDebounce = 0;

void setLEDColor(int i, int r, int g, int b) {
  digitalWrite(redPins[i], r);
  digitalWrite(greenPins[i], g);
  digitalWrite(bluePins[i], b);
}

void sendPacket(int light, uint16_t aqiVal) {
  Serial.print("{\"board_id\":");
  Serial.print(BOARD_ID);
  Serial.print(",\"cells\":[");

  for (int i = 0; i < 6; i++) {
    Serial.print("{\"cell\":");
    Serial.print(CELL_START + i + 1);
    Serial.print(",\"temp\":");
    Serial.print(temperatures[i]);
    Serial.print(",\"hum\":");
    Serial.print(humidities[i]);
    Serial.print(",\"moist\":");
    Serial.print(moistureValues[i]);
    Serial.print("}");
    if (i < 5) Serial.print(",");
  }

  Serial.print("],\"light\":");
  Serial.print(light);
  Serial.print(",\"aqi\":");
  Serial.print(aqiVal);
  Serial.print(",\"pump\":");
  Serial.print(pumpToggleState);
  Serial.println("}");
}

void setup() {
  Serial.begin(9600);

  for (int i = 0; i < 6; i++) {
    pinMode(redPins[i], OUTPUT);
    pinMode(greenPins[i], OUTPUT);
    pinMode(bluePins[i], OUTPUT);
    pinMode(relayPins[i], OUTPUT);
  }

  pinMode(waterPumpPin, OUTPUT);
  pinMode(pumpButtonPin, INPUT_PULLUP);

  aqi.begin_I2C();
}

void loop() {
  for (int i = 0; i < 6; i++) {
    DHTs[i].read11(DHTPins[i]);
    temperatures[i] = DHTs[i].temperature;
    humidities[i] = DHTs[i].humidity;
    moistureValues[i] = analogRead(moisturePins[i]);

    if (moistureValues[i] > DRY_THRESHOLD) setLEDColor(i, HIGH, LOW, LOW);
    else if (moistureValues[i] < WET_THRESHOLD) setLEDColor(i, LOW, LOW, HIGH);
    else setLEDColor(i, LOW, HIGH, LOW);
  }

  int light = map(analogRead(photocellPin), 0, 1000, 0, 100);

  uint16_t aqiVal = 0;
  PM25_AQI_Data data;
  if (aqi.read(&data)) aqiVal = data.aqi_pm25_us;

  sendPacket(light, aqiVal);
  delay(2500);
}
