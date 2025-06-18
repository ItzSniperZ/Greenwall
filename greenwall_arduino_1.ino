#include <dht.h>

// Pins for the 8 sensors
const int DHTPins[8] = {22, 23, 24, 25, 26, 27, 32, 33};
const int moisturePins[8] = {14, 15, 16, 17, 18, 19, 20, 21};
const int photocellPin = A3;
const int photoCellMin = 0;
const int photoCellMax = 1000;
#define REDPIN 7
#define GREENPIN 6
#define BLUEPIN 5

// Create 8 DHT sensor objects
dht DHTs[8];

// Arrays to store values
int temperatures[8];
int humidities[8];
int moistureValues[8];

void setup() {
  Serial.begin(9600);
  pinMode(REDPIN, OUTPUT);
  pinMode(GREENPIN, OUTPUT);
  pinMode(BLUEPIN, OUTPUT);

  // Set color to solid red
  analogWrite(REDPIN, 120);  // full brightness red
  analogWrite(GREENPIN, 0);  // green off
  analogWrite(BLUEPIN, 0);   // blue off
}

void loop() {
  for (int i = 0; i < 8; i++) {
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

    Serial.print("Temperature: ");
    Serial.print(temperatures[i]);
    Serial.print(" C\t");

    Serial.print("Humidity: ");
    Serial.print(humidities[i]);
    Serial.println(" %");
  }
  for (int i = 0; i < 8; i++) {
    moistureValues[i] = analogRead(moisturePins[i]);
    Serial.print("Moisture Sensor ");
    Serial.print(i + 1);
    Serial.print(" (Pin ");
    Serial.print(moisturePins[i]);
    Serial.print("): ");
    Serial.println(moistureValues[i]);
  } 
  int photoReading = analogRead(photocellPin);
  int lightPercent = map(photoReading, photoCellMin, photoCellMax, 0, 100); // Adjustments for photo cell sensitivity.
  Serial.print("Light Reading: ");
  Serial.print(lightPercent);
  Serial.print("%");
  Serial.println("");
  Serial.println("------------------------------------------------");
  delay(3000); // Wait before next full set of readings
}