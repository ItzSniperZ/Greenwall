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

    if (moistureValues[i] > DRY_THRESHOLD) { // if too dry, turn on water
      Serial.print("Soil too dry in sensor ");
      Serial.print(i + 1);
      setWaterPump(waterPumpPin, HIGH);
      delay (10000);
      setWaterPump(waterPumpPin, LOW);
    }
    if (moistureValues[i] < WET_THRESHOLD) { // if too wet, turn off water
      Serial.print("Soil to wet in sensor ");
      Serial.print(i + 1);
      setWaterPump(waterPumpPin, LOW);
    }
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
  Serial.println(F("Concentration Units (standard)"));
  Serial.print(F("PM 1.0: ")); Serial.print(data.pm10_standard);
  Serial.print(F("\t\tPM 2.5: ")); Serial.print(data.pm25_standard);
  Serial.print(F("\t\tPM 10: ")); Serial.println(data.pm100_standard);
  Serial.println(F("---------------------------------------"));
  Serial.println(F("Concentration Units (environmental)"));
  Serial.print(F("PM 1.0: ")); Serial.print(data.pm10_env);
  Serial.print(F("\t\tPM 2.5: ")); Serial.print(data.pm25_env);
  Serial.print(F("\t\tPM 10: ")); Serial.println(data.pm100_env);
  Serial.println(F("---------------------------------------"));
  Serial.print(F("Particles > 0.3um / 0.1L air:")); Serial.println(data.particles_03um);
  Serial.print(F("Particles > 0.5um / 0.1L air:")); Serial.println(data.particles_05um);
  Serial.print(F("Particles > 1.0um / 0.1L air:")); Serial.println(data.particles_10um);
  Serial.print(F("Particles > 2.5um / 0.1L air:")); Serial.println(data.particles_25um);
  Serial.print(F("Particles > 5.0um / 0.1L air:")); Serial.println(data.particles_50um);
  Serial.print(F("Particles > 10 um / 0.1L air:")); Serial.println(data.particles_100um);
  Serial.println(F("---------------------------------------"));
  Serial.println(F("AQI"));
  Serial.print(F("PM2.5 AQI US: ")); Serial.print(data.aqi_pm25_us);
  Serial.print(F("\tPM10  AQI US: ")); Serial.println(data.aqi_pm100_us);
  Serial.println("------------------------------------------------");
  delay(3000); // Wait before next full set of readings
}
