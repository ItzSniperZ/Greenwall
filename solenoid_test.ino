// solenoid_test.ino
// Greenwall Water System Test
// Closes solenoids on pins 14-19 and holds them closed.

const int SOLENOID_PINS[] = {14, 15, 16, 17, 18, 19};
const int NUM_SOLENOIDS = 6;

void setup() {
  Serial.begin(9600);

  for (int i = 0; i < NUM_SOLENOIDS; i++) {
    pinMode(SOLENOID_PINS[i], OUTPUT);
    digitalWrite(SOLENOID_PINS[i], LOW); // Close solenoid (energize)
    Serial.print("Solenoid on pin ");
    Serial.print(SOLENOID_PINS[i]);
    Serial.println(" → CLOSED");
  }

  Serial.println("All solenoids closed. Water system ready.");
}

void loop() {
  // Nothing — solenoids stay closed indefinitely
}
