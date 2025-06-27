#include <dht.h>
#include "Adafruit_PM25AQI.h"

// Digital Pins Free: {1, 32-43, 51-53} (16 pins)
const int DHTPins[6] = {20, 21, 22, 23, 24, 25}; //pins for DHT sensors
const int moisturePins[6] = {14, 15, 16, 17, 18, 19}; //pins for moisture sensors
const int relayPins[6] = {26, 27, 28, 29, 30, 31}; //pins for relay sensors (fan controllers)
const int redPins[6] = {2, 5, 8, 11, 44, 47}; //red LED pins
const int greenPins[6] = {3, 6, 9, 12, 45, 48}; //green LED pins
const int bluePins[6] = {4, 7, 10, 13, 46, 49}; //blue LED pins
const int waterPumpPin = 50;
const int photocellPin = A3;
const int photoCellMin = 0; //minimum value for photo resistor
const int photoCellMax = 1000; //max value for photo resistor
const int DRY_THRESHOLD = 850; // limit for how dry rockwool can be before running water
const int WET_THRESHOLD = 350; //limit to how dry the rockwool can be before stopping water
unsigned long pumpStartTime = 0;
bool pumpRunning = false;
const unsigned long pumpDuration = 10000; // 10 seconds
Adafruit_PM25AQI aqi = Adafruit_PM25AQI(); //air quality sensor
dht DHTs[6]; //DHT sensor objects
int temperatures[6]; //array to store DHT temperature values
int humidities[6]; //array to store DHT humidity values
int moistureValues[6]; //array to store moisture values

void setLEDColor(int stripIndex, int redVal, int greenVal, int blueVal) {
  digitalWrite(redPins[stripIndex], redVal);
  digitalWrite(greenPins[stripIndex], greenVal);
  digitalWrite(bluePins[stripIndex], blueVal);
}

void setWaterPump(int pin, int power) { // on/off control for water pump
  digitalWrite(pin, power);
}

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < 6; i++) {
    pinMode(redPins[i], OUTPUT);
    pinMode(greenPins[i], OUTPUT);
    pinMode(bluePins[i], OUTPUT);
    setLEDColor(i, LOW, HIGH, LOW); // Turn green initially
    
    pinMode(relayPins[i], OUTPUT);
    digitalWrite(relayPins[i], LOW);
  }
  if (! aqi.begin_I2C()) {
     Serial.println("Could not find PM 2.5 sensor!");
  }
  pinMode(waterPumpPin, OUTPUT);
  digitalWrite(waterPumpPin, LOW);
}

void loop() {
  for (int i = 0; i < 6; i++) { //loop to go through all cells
  int output = DHTs[i].read11(DHTPins[i]); // Read sensor
    // Store values
    temperatures[i] = DHTs[i].temperature;
    humidities[i] = DHTs[i].humidity;

    // Print readings
    Serial.print("Sensor ");
    Serial.print(i + 1);
    Serial.print(" (Pin ");
    Serial.print(DHTPins[i]);
    Serial.print("): ");

    if (temperatures[i] > 26.66) {
      digitalWrite(relayPins[i], HIGH);  // Too warm → fan ON
    } 
    else if (temperatures[i] < 21.11) {
        digitalWrite(relayPins[i], LOW);  // Cool enough → fan OFF
    }

    Serial.print("Temperature: ");
    Serial.print(temperatures[i]);
    Serial.print(" C\t");

    Serial.print("Humidity: ");
    Serial.print(humidities[i]);
    Serial.println(" %");
 
    moistureValues[i] = analogRead(moisturePins[i]);
    Serial.print("Moisture Sensor ");
    Serial.print(i + 1);
    Serial.print(" (Pin ");
    Serial.print(moisturePins[i]);
    Serial.print("): ");
    Serial.println(moistureValues[i]);

  if (moistureValues[i] > DRY_THRESHOLD && !pumpRunning) {
    Serial.print("Soil too dry in sensor ");
    Serial.print(i + 1);
    Serial.println(" → Starting Pump");
    setWaterPump(waterPumpPin, HIGH);
    pumpRunning = true;
    pumpStartTime = millis();
    break; // stop checking others this cycle
  }
} 
  if (pumpRunning && millis() - pumpStartTime >= pumpDuration) {
    setWaterPump(waterPumpPin, LOW);
    pumpRunning = false;
    Serial.println("Pump cycle complete → Pump OFF");
  }

  int photoReading = analogRead(photocellPin);
  int lightPercent = map(photoReading, photoCellMin, photoCellMax, 0, 100); // Adjustments for photo cell sensitivity.
  Serial.print("Light Reading: ");
  Serial.print(lightPercent);
  Serial.print("%");
  Serial.println("");
  Serial.println("------------------------------------------------");
  
  PM25_AQI_Data data;
  if (! aqi.read(&data)) {
    Serial.println("Could not read from AQI");
    
    delay(500);  // try again in a bit!
    return;
  }

  Serial.println("AQI reading success");
 // air quality sensor code
  Serial.println(F("---------------------------------------"));
  uint16_t aqiValue = data.aqi_pm25_us;
  String category;

  if (aqiValue <= 50) category = "Good";
  else if (aqiValue <= 100) category = "Moderate";
  else if (aqiValue <= 150) category = "Unhealthy for Sensitive Groups";
  else if (aqiValue <= 200) category = "Unhealthy";
  else if (aqiValue <= 300) category = "Very Unhealthy";
  else category = "Hazardous";

  Serial.print("Air Quality (PM2.5 AQI US): ");
  Serial.print(aqiValue);
  Serial.print(" → ");
  Serial.println(category);
  Serial.println("------------------------------------------------");
  delay(2500); // Wait before next full set of readings
}
