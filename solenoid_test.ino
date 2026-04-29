// solenoid_test_board1.ino
const int SOLENOID_PINS[] = {14, 15, 16, 17, 18, 19};
const int NUM_SOLENOIDS = 6;
const int PUMP_PIN = 50;

void setup() {
  Serial.begin(9600);

  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);

  for (int i = 0; i < NUM_SOLENOIDS; i++) {
    pinMode(SOLENOID_PINS[i], OUTPUT);
  }

  // Step 1 — Close solenoids one by one with 5 second delay
  Serial.println("Closing solenoids...");
  for (int i = 0; i < NUM_SOLENOIDS; i++) {
    digitalWrite(SOLENOID_PINS[i], LOW);
    Serial.print("Solenoid on pin ");
    Serial.print(SOLENOID_PINS[i]);
    Serial.println(" → CLOSED");
    delay(5000);
  }
  Serial.println("All solenoids closed.");

  // Step 2 — Run pump for 90 seconds
  Serial.println("Pump ON...");
  digitalWrite(PUMP_PIN, HIGH);
  delay(90000);
  digitalWrite(PUMP_PIN, LOW);
  Serial.println("Pump OFF.");

  // Step 3 — Open solenoids one by one with 5 second delay
  Serial.println("Opening solenoids...");
  for (int i = 0; i < NUM_SOLENOIDS; i++) {
    digitalWrite(SOLENOID_PINS[i], HIGH);
    Serial.print("Solenoid on pin ");
    Serial.print(SOLENOID_PINS[i]);
    Serial.println(" → OPEN");
    delay(5000);
  }
  Serial.println("All solenoids open. Holding for 5 minutes...");

  // Step 4 — Hold open for 5 minutes
  delay(300000);

  // Step 5 — Close solenoids one by one with 5 second delay
  Serial.println("Closing solenoids...");
  for (int i = 0; i < NUM_SOLENOIDS; i++) {
    digitalWrite(SOLENOID_PINS[i], LOW);
    Serial.print("Solenoid on pin ");
    Serial.print(SOLENOID_PINS[i]);
    Serial.println(" → CLOSED");
    delay(5000);
  }
  Serial.println("All solenoids closed. Test complete.");
}

void loop() {
  // Nothing — test runs once in setup
}
